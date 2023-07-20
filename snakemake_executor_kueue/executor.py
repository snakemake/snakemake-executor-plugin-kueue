import os
from collections import namedtuple

import oras.client
import portforward
from jinja2 import Template
from kubernetes import client, config
from kubernetes.client.api import core_v1_api
from snakemake.common import async_lock, get_container_image
from snakemake.exceptions import WorkflowError
from snakemake.executors import ClusterExecutor, sleep
from snakemake.logging import logger
from snakemake.resources import DefaultResources

import snakemake_executor_kueue.custom_resource as cr

# Make sure your cluster is running!
config.load_kube_config()
crd_api = client.CustomObjectsApi()
api_client = crd_api.api_client

KueueJob = namedtuple(
    "KueueJob",
    "job crd container jobspec submit_result, kueue_logfile, callback error_callback",
)

install_oras = [
    "VERSION=1.0.0",
    "curl -LO https://github.com/oras-project/oras/releases/download/v${VERSION}/oras_${VERSION}_linux_amd64.tar.gz",
    "mkdir -p oras-install/",
    "tar -zxf oras_${VERSION}_*.tar.gz -C oras-install/",
    "mv oras-install/oras /usr/local/bin/",
    "rm -rf oras_${VERSION}_*.tar.gz oras-install/",
]

# This assumes the workflow is in the PWD, and we populate the push/pull with workflow step
pull_oras = "oras pull {{ registry }}/{{ container }} . {% if insecure %}--plain-http{% endif %}"
push_oras = "oras push {{ registry }}/{{ container }} . {% if insecure %}--plain-http{% endif %}"

# oras pull registry-0.r.default.svc.cluster.local:5000/vanessa/container:latest --plain-http
# oras pull registry-0.r.default.svc.cluster.local:5000/snakemake/workflow:latest --plain-http


class KueueExecutor(ClusterExecutor):
    """
    The Kueue Executor will submit jobs to Kueue.
    """

    def __init__(
        self,
        workflow,
        dag,
        cores,
        jobname="snakejob.{name}.{jobid}.sh",
        printreason=False,
        quiet=False,
        printshellcmds=False,
        executor_args=None,
    ):
        super().__init__(
            workflow,
            dag,
            None,
            jobname=jobname,
            printreason=printreason,
            quiet=quiet,
            printshellcmds=printshellcmds,
            assume_shared_fs=False,
            max_status_checks_per_second=10,
        )

        # Attach variables for easy access
        self.workdir = os.path.realpath(os.path.dirname(self.workflow.persistence.path))
        self.envvars = list(self.workflow.envvars) or []
        self.executor_args = executor_args
        self._core_v1 = None

    def cancel(self):
        """
        cancel execution, usually by way of control+c. Cleanup is done in
        shutdown (deleting cached workdirs in Google Cloud Storage
        """
        for job in self.active_jobs:
            job.crd.cleanup()
        self.shutdown()

    def _set_job_resources(self, job):
        """
        Given a particular job, generate the resources that it needs,
        including default regions and the virtual machine configuration
        """
        self.default_resources = DefaultResources(
            from_other=self.workflow.default_resources
        )

    def get_snakefile(self):
        """
        This gets called by format_job_exec, so we want to return
        the relative path in the container.
        """
        return "/snakemake_workdir/Snakefile"

    def get_original_snakefile(self):
        assert os.path.exists(self.workflow.main_snakefile)
        return self.workflow.main_snakefile

    def run(self, job, callback=None, submit_callback=None, error_callback=None):
        """
        Submit a job to flux.
        """
        super()._run(job)
        logfile = job.logfile_suggestion(".snakemake/kueue_logs")
        os.makedirs(os.path.dirname(logfile), exist_ok=True)

        # Prepare job resourcces
        self._set_job_resources(job)

        # The entire snakemake command to run, etc
        command = self.format_job_exec(job)
        logger.debug(command)

        # Not sure if this is the right way to get container in Snakefile
        container = (
            job.resources.get("container")
            or self.executor_args.container
            or get_container_image()
        )

        # Hard coding for now because of compatbility.
        container = "snakemake/snakemake:v7.30.1"

        # Determine which CRD / operator to generate
        operator_type = job.resources.get("kueue.operator") or "job"
        if operator_type == "job":
            crd = cr.BatchJob(
                job,
                executor_args=self.executor_args,
                snakefile=self.get_original_snakefile(),
            )
        else:
            raise WorkflowError(
                "Currently only kueue.operator: job is supported under resources."
            )

        # Store job container with job so we can pull as we go
        job_container = f"snakemake/{job.name}:latest"

        # The command needs to be prefixed with downloading oras
        push_command = Template(push_oras).render(
            insecure=self.executor_args.insecure,
            registry=self.executor_args.registry,
            container=job_container,
        )
        pre_command = " && ".join(install_oras)

        # These are the dependent jobs we need to download
        deps = list(job.dag.dependencies[job.name].keys())
        for dep in deps:
            pre_command += " && " + (
                Template(pull_oras).render(
                    insecure=self.executor_args.insecure,
                    registry=self.executor_args.registry,
                    container=f"snakemake/{dep}:latest",
                )
            )

        # Add the run and push command
        command = " && ".join([pre_command, command, push_command])
        print(command)

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
            if self.executor_args.namespace == "default"
            else f"--namespace {self.executor_args.namespace} "
        )
        logger.info(
            f'Use:\n"kubectl get {namespace}queue" to see queue assignment\n"kubectl get {namespace} jobs" to see jobs'
        )

        # Waiting for the jobid is a small performance penalty, same as calling flux.job.submit
        self.active_jobs.append(
            KueueJob(
                job,
                crd,
                job_container,
                spec,
                result,
                logfile,
                callback,
                error_callback,
            )
        )

    @property
    def core_v1(self):
        """
        Instantiate a core_v1 api (if not done yet)

        We have this here because we typically need to create the MiniCluster
        first. For a custom core_v1_api, provide core_c1_api to the FluxOperator
        init function.
        """
        if self._core_v1 is not None:
            return self._core_v1

        self.c = client.Configuration.get_default_copy()
        self.c.assert_hostname = False
        client.Configuration.set_default(self.c)
        self._core_v1 = core_v1_api.CoreV1Api()
        return self._core_v1

    def update_workdir(self, job):
        """
        Update the working directory with a pull of the container
        from the registry. We need to port forward to access the service.
        """
        namespace = self.executor_args.namespace
        pod_name = "r"
        local_port = 5000  # from port
        pod_port = 5000  # to port
        here = os.path.abspath(self.workdir)

        # No path to kube config provided - will use default from $HOME/.kube/config
        with portforward.forward(namespace, pod_name, local_port, pod_port):
            print(f"Pulling {job.container} to {here}")
            client = oras.client.OrasClient(insecure=self.executor_args.insecure)
            client.pull(
                allowed_media_type=[],
                overwrite=True,
                outdir=os.path.join(here, "res"),
                target="http://localhost:5000/" + job.container,
            )

    async def _wait_for_jobs(self):
        """
        Wait for jobs to complete. This means requesting their status,
        and then marking them as finished when a "done" parameter
        shows up. Even for finished jobs, the status should still return
        """
        while True:
            # always use self.lock to avoid race conditions
            async with async_lock(self.lock):
                if not self.wait:
                    return
                active_jobs = self.active_jobs
                self.active_jobs = list()
                still_running = list()

            # Loop through active jobs and act on status
            for j in active_jobs:
                logger.debug("Checking status for job {}".format(j.crd.jobname))
                status = j.crd.status()
                print(status)

                if status == cr.JobStatus.FAILED:
                    # Retrieve the job log and write to file
                    j.crd.write_log(j.kueue_logfile)
                    j.crd.cleanup()
                    # Tell user about it
                    j.error_callback(j.job)
                    continue

                # Finished and success!
                elif status == cr.JobStatus.SUCCEEDED:
                    j.crd.write_log(j.kueue_logfile)
                    self.update_workdir(j)
                    j.crd.cleanup()
                    j.callback(j.job)

                # Otherwise, we are still running
                else:
                    still_running.append(j)

            async with async_lock(self.lock):
                self.active_jobs.extend(still_running)

            # Sleeps for 10 seconds
            await sleep()
