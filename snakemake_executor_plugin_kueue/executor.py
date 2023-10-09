import os
import shlex
from typing import Generator, List

import oras.client
from jinja2 import Template
from kubernetes import client, config
from kubernetes.client.api import core_v1_api
from snakemake.common import get_container_image
from snakemake_interface_common.exceptions import WorkflowError  # noqa

from snakemake_interface_executor_plugins.executors.base import SubmittedJobInfo
from snakemake_interface_executor_plugins.executors.remote import RemoteExecutor
from snakemake_interface_executor_plugins.jobs import JobExecutorInterface
from snakemake_interface_executor_plugins.logging import LoggerExecutorInterface
from snakemake_interface_executor_plugins.workflow import WorkflowExecutorInterface

import snakemake_executor_plugin_kueue.custom_resource as cr
from .template import install_oras, pull_oras, push_oras

# Make sure your cluster is running!
config.load_kube_config()
crd_api = client.CustomObjectsApi()
api_client = crd_api.api_client


class KueueExecutor(RemoteExecutor):
    def __init__(
        self,
        workflow: WorkflowExecutorInterface,
        logger: LoggerExecutorInterface,
    ):
        super().__init__(
            workflow,
            logger,
            # configure behavior of RemoteExecutor below
            # whether arguments for setting the remote provider shall  be passed to jobs
            pass_default_remote_provider_args=True,
            # whether arguments for setting default resources shall be passed to jobs
            pass_default_resources_args=True,
            # whether environment variables shall be passed to jobs
            pass_envvar_declarations_to_cmd=True,
            # specify initial amount of seconds to sleep before checking for job status
            init_seconds_before_status_checks=0,
        )

        # Attach variables for easy access
        self.workdir = os.path.realpath(os.path.dirname(self.workflow.persistence.path))
        self.envvars = list(self.workflow.envvars) or []
        self._core_v1 = None

    @property
    def core_v1(self):
        """
        Instantiate a core_v1 api (if not done yet)

        We have this here to interact with Kubernetes.
        """
        if self._core_v1 is not None:
            return self._core_v1

        self.c = client.Configuration.get_default_copy()
        self.c.assert_hostname = False
        client.Configuration.set_default(self.c)
        self._core_v1 = core_v1_api.CoreV1Api()
        return self._core_v1

    def get_snakefile(self):
        """
        This gets called by format_job_exec, so we want to return
        the relative path in the container.
        """
        return "/snakemake_workdir/Snakefile"

    def get_envvar_declarations(self):
        """
        Temporary workaround until:
        https://github.com/snakemake/snakemake-interface-executor-plugins/pull/31
        is able to be merged.
        """
        if self.pass_envvar_declarations_to_cmd:
            return " ".join(
                f"{var}={repr(os.environ[var])}"
                for var in self.workflow.remote_execution_settings.envvars or {}
            )
        else:
            return ""

    def get_original_snakefile(self):
        assert os.path.exists(self.workflow.main_snakefile)
        return self.workflow.main_snakefile

    def run_job(self, job: JobExecutorInterface):
        # Implement here how to run a job.
        # You can access the job's resources, etc.
        # via the job object.
        # After submitting the job, you have to call
        # self.report_job_submission(job_info).
        # with job_info being of type
        # snakemake_interface_executor_plugins.executors.base.SubmittedJobInfo.
        # If required, make sure to pass the job's id to the job_info object, as keyword
        # argument 'external_job_id'.
        logfile = job.logfile_suggestion(os.path.join(".snakemake", "kueue_logs"))
        os.makedirs(os.path.dirname(logfile), exist_ok=True)

        # The entire snakemake command to run, etc
        command = self.format_job_exec(job)
        self.logger.debug(command)

        # First preference to job container, then executor settings, then default
        container = (
            job.resources.get("container")
            or self.executor_settings.container
            or get_container_image()
        )

        # Determine which CRD / operator to generate
        operator_type = job.resources.get("kueue_operator") or "job"
        if operator_type == "job":
            crd = cr.BatchJob(
                job,
                settings=self.executor_settings,
                snakefile=self.get_original_snakefile(),
            )
        else:
            raise WorkflowError(
                "Currently only kueue_operator: job is supported under resources."
            )

        # Store job container with job so we can pull as we go
        job_container = f"snakemake/{job.name}:latest"

        # The command needs to be prefixed with downloading oras
        push_command = Template(push_oras).render(
            insecure=self.executor_settings.insecure,
            registry=self.executor_settings.registry,
            container=job_container,
        )
        pre_command = " && ".join(install_oras)

        # These are the dependent jobs we need to download
        deps = list(job.dag.dependencies[job.name].keys())
        for dep in deps:
            pre_command += " && " + (
                Template(pull_oras).render(
                    insecure=self.executor_settings.insecure,
                    registry=self.executor_settings.registry,
                    container=f"snakemake/{dep}:latest",
                )
            )

        # Hard coding for now because of compatbility.
        # container = "snakemake/snakemake:v7.30.1"

        # Add the run and push command
        command = " && ".join(
            [
                f"echo '{pre_command} {command}'",
                pre_command,
                command,
                f"echo {push_command}",
                push_command,
            ]
        )

        # Generate the job first
        # TODO will need to pass some cleaned environment or scoped
        spec = crd.generate(
            image=container,
            command="/bin/bash",
            args=["-c", command],
            environment={},
        )

        # We don't technically need to get it back, but
        # now we can explicitly submit it
        result = crd.submit(spec)

        # Tell the user how to debug or interact with kubectl
        namespace = (
            ""
            if self.executor_settings.namespace == "default"
            else f"--namespace {self.executor_settings.namespace} "
        )
        self.logger.info(
            f'Use:\n"kubectl get {namespace}queue" to see queue assignment\n"kubectl get {namespace} jobs" to see jobs'
        )

        # Save aux metadata and report job submission
        aux = {
            "crd": crd,
            "kueue_logfile": logfile,
            "job_container": job_container,
            "spec": spec,
            "result": result,
        }
        self.report_job_submission(
            SubmittedJobInfo(job, external_jobid=crd.jobname, aux=aux)
        )

    def update_workdir(self, job):
        """
        Update the working directory with a pull of the container
        from the registry. We need to port forward to access the service.
        """
        here = os.path.abspath(self.workdir)

        # Container associated with last job
        container = job.aux['job_container']
        registry = self.executor_settings.pull_registry

        # We can't rely on a port forward here, is in an asyncio function
        print(f"Pulling {registry}{container} to {here}")
        client = oras.client.OrasClient(insecure=self.executor_settings.insecure)
        client.pull(
            allowed_media_type=[],
            overwrite=True,
            outdir=os.path.join(here, "res"),
            target=registry + container,
         )

    async def check_active_jobs(
        self, active_jobs: List[SubmittedJobInfo]
    ) -> Generator[SubmittedJobInfo, None, None]:
        # Loop through active jobs and act on status
        for j in active_jobs:
            # Unwrap variables from auxiliary metadata
            crd = j.aux["crd"]
            logfile = j.aux["kueue_logfile"]
            aux_logs = [logfile]

            self.logger.debug("Checking status for job {}".format(crd.jobname))
            status = crd.status()
            print(status)

            if status == cr.JobStatus.FAILED:
                # Retrieve the job log and write to file
                crd.write_log(logfile)
                crd.cleanup()

                # Tell the user about it
                msg = f"Kueue job '{j.external_jobid}' failed. "
                self.report_job_error(j, msg=msg, aux_logs=aux_logs)
                continue

            # Finished and success!
            elif status == cr.JobStatus.SUCCEEDED:
                crd.write_log(logfile)
                self.update_workdir(j)

                # Finished and success!
                self.report_job_success(j)
                crd.cleanup()

            # Otherwise, we are still running
            else:
                yield j

    def cancel_jobs(self, active_jobs: List[SubmittedJobInfo]):
        """
        cancel execution, usually by way of control+c. Cleanup is done in
        shutdown (deleting cached workdirs in Google Cloud Storage
        """
        for job in self.active_jobs:
            crd = job.aux["crd"]
            crd.cleanup()
        self.shutdown()
