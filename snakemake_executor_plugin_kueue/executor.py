import os
from typing import Generator, List

import time
import hashlib
from kubernetes import client, config
from kubernetes.client.api import core_v1_api
from snakemake.common import get_container_image
from snakemake_interface_common.exceptions import WorkflowError  # noqa

from snakemake_interface_executor_plugins.executors.base import SubmittedJobInfo
from snakemake_interface_executor_plugins.executors.remote import RemoteExecutor
from snakemake_interface_executor_plugins.jobs import JobExecutorInterface
from snakemake_interface_executor_plugins.logging import LoggerExecutorInterface
from snakemake_interface_executor_plugins.workflow import WorkflowExecutorInterface
from snakemake_interface_executor_plugins.utils import (
    encode_target_jobs_cli_args,
    format_cli_arg,
    join_cli_args,
)

import snakemake_executor_plugin_kueue.custom_resource as cr

# import snakemake_executor_plugin_kueue.oras as oras

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
        super().__init__(workflow, logger)

        # Attach variables for easy access
        self.workdir = os.path.realpath(os.path.dirname(self.workflow.persistence.path))
        # self.envvars = list(self.workflow.envvars) or []
        self._core_v1 = None

        # Upload the working directory to the oras cache
        self._workflow_uid = None
        # self.oras = oras.OrasRegistry(self.executor_settings, self.workdir)
        self.last_job = None
        # if not self.executor_settings.disable_oras_cache:
        #    self.upload_workdir()

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

    def format_job_exec(self, job: JobExecutorInterface) -> str:
        """
        Redefining this function to not add so many arguments.
        """
        prefix = self.get_job_exec_prefix(job)
        if prefix:
            prefix += " &&"
        suffix = self.get_job_exec_suffix(job)
        if suffix:
            suffix = f"&& {suffix}"

        pass_storage_args = self.common_settings.pass_default_storage_provider_args
        pass_resource_args = self.common_settings.pass_default_resources_args
        auto_deploy = self.common_settings.auto_deploy_default_storage_provider

        general_args = self.workflow.spawned_job_args_factory.general_args(
            pass_default_storage_provider_args=pass_storage_args,
            pass_default_resources_args=pass_resource_args,
        )
        precommand = self.workflow.spawned_job_args_factory.precommand(
            auto_deploy_default_storage_provider=auto_deploy
        )
        if precommand:
            precommand += " &&"
        args = join_cli_args(
            [
                prefix,
                self.get_envvar_declarations(),
                precommand,
                self.get_python_executable(),
                "-m snakemake",
                format_cli_arg("--snakefile", self.get_snakefile()),
                self.get_job_args(job),
                general_args,
                self.additional_general_args(),
                # format_cli_arg("--mode", self.get_exec_mode().item_to_choice()),
                format_cli_arg(
                    "--local-groupid",
                    self.workflow.group_settings.local_groupid,
                    skip=self.job_specific_local_groupid,
                ),
                suffix,
            ]
        )

        # These are bugs for the time being, the new storage plugins
        # have some work to do (Google Storage is my fault!)
        removes = [
            "--storage-s3-retries 5",
            "--storage-gs-keep-local False",
            "--storage-gs-stay-on-remote False",
            "--storage-gs-retries 5",
            "--shared-fs-usage 'none'",
        ]
        for remove in removes:
            args = args.replace(remove, "")
        return args

    def get_job_args(self, job: JobExecutorInterface, **kwargs):
        return join_cli_args(
            [
                format_cli_arg(
                    "--target-jobs", encode_target_jobs_cli_args(job.get_target_spec())
                ),
                # Restrict considered rules for faster DAG computation.
                # This does not work for updated jobs because they need
                # to be updated in the spawned process as well.
                format_cli_arg(
                    "--allowed-rules",
                    job.rules,
                    quote=False,
                    skip=job.is_updated,
                ),
                # Ensure that a group uses its proper local groupid.
                format_cli_arg("--local-groupid", job.jobid, skip=not job.is_group()),
                format_cli_arg("--cores", kwargs.get("cores", self.cores)),
                format_cli_arg("--attempt", job.attempt),
                format_cli_arg("--force-use-threads", not job.is_group()),
                self.get_resource_declarations(job),
            ]
        )

    def get_python_executable(self):
        """
        We assume running in a Kubernetes container, and target python3.

        We need to do this because we tell the executor that it's running on
        a shared filesystem only to avoid requiring the external storage provider.
        """
        return "python3"

    def get_original_snakefile(self):
        assert os.path.exists(self.workflow.main_snakefile)
        return self.workflow.main_snakefile

    def run_job(self, job: JobExecutorInterface):
        """
        Run the job. This is a terrible docstring.
        """
        logfile = job.logfile_suggestion(os.path.join(".snakemake", "kueue_logs"))
        os.makedirs(os.path.dirname(logfile), exist_ok=True)

        # The entire snakemake command to run, etc
        command = self.format_job_exec(job)

        # Not sure what this is, but doesn't exist in container
        # command = command.replace(" --mode 'remote'", "")
        self.logger.debug(command)

        # First preference to job container, then executor settings, then default
        # Hard coding in custom build as default for compatibility issues
        container = (
            job.resources.get("container")
            or self.executor_settings.container
            or "vanessa/snakemake:kueue"
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
        elif operator_type == "flux-operator":
            crd = cr.FluxMiniCluster(
                job,
                settings=self.executor_settings,
                snakefile=self.get_original_snakefile(),
            )
        else:
            raise WorkflowError(
                "Currently only kueue_operator: job or flux-operator are supported."
            )

        # Add the run and push command
        command = " && ".join(
            [
                f"echo '{command}'",
                command,
            ]
        )
        envars = self.workflow.spawned_job_args_factory.envvars()

        # Generate the job first
        spec = crd.generate(
            image=container,
            command="/bin/bash",
            args=["-c", command],
            environment=envars,
        )

        # We don't technically need to get it back, but
        # now we can explicitly submit it
        result = crd.submit(spec)

        # Tell the user how to debug or interact with kubectl
        namespace = (
            " "
            if self.executor_settings.namespace == "default"
            else f" --namespace {self.executor_settings.namespace} "
        )
        self.logger.info(
            f"Use:\n'kubectl get{namespace}queue' to see queue assignment "
            f"'kubectl get{namespace}jobs' to see jobs'"
        )

        # Save aux metadata and report job submission
        aux = {
            "crd": crd,
            "kueue_logfile": logfile,
            "spec": spec,
            "result": result,
        }
        self.report_job_submission(
            SubmittedJobInfo(job, external_jobid=crd.jobname, aux=aux)
        )

    @property
    def workflow_uid(self):
        """
        Generate a unique id for the workflow based on hashing the object.
        """
        if not self._workflow_uid:
            hasher = hashlib.md5()
            hasher.update(str(self.workflow).encode("utf-8"))
            self._workflow_uid = hasher.hexdigest()
        return self._workflow_uid

    async def check_active_jobs(
        self, active_jobs: List[SubmittedJobInfo]
    ) -> Generator[SubmittedJobInfo, None, None]:
        # Loop through active jobs and act on status
        for j in active_jobs:
            # Unwrap variables from auxiliary metadata
            crd = j.aux["crd"]
            logfile = j.aux["kueue_logfile"]
            aux_logs = [logfile]

            self.logger.debug(f"Checking status for job {crd.jobname}")
            status = crd.status()
            print(status)

            if status == cr.JobStatus.FAILED:
                # Retrieve the job log and write to file
                # An error usually means it's not done creating yet
                # We can likely better handle this under custom resources
                try:
                    crd.write_log(logfile)
                except Exception:
                    time.sleep(5)
                crd.cleanup()

                # Tell the user about it
                msg = f"Kueue job '{j.external_jobid}' failed.\n    See {logfile}. "
                self.report_job_error(j, msg=msg, aux_logs=aux_logs)
                continue

            # Finished and success!
            elif status == cr.JobStatus.SUCCEEDED:
                try:
                    crd.write_log(logfile)
                except Exception:
                    time.sleep(5)
                self.last_job = j

                # Finished and success!
                self.report_job_success(j)
                crd.cleanup()

            # Otherwise, we are still running
            else:
                yield j

    def cancel_jobs(self, active_jobs: List[SubmittedJobInfo]):
        """
        cancel execution, usually by way of control+c.
        """
        for job in self.active_jobs:
            crd = job.aux["crd"]
            crd.cleanup()
        self.shutdown()
