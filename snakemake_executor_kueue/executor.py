import os
import shlex
from collections import namedtuple

from kubernetes import client, config
from snakemake.common import async_lock, get_container_image
from snakemake.exceptions import WorkflowError
from snakemake.executors import ClusterExecutor, sleep
from snakemake.logging import logger
from snakemake.resources import DefaultResources

import snakemake_executor_kueue.custom_resource as custom_resource

# Make sure your cluster is running!
config.load_kube_config()
crd_api = client.CustomObjectsApi()
api_client = crd_api.api_client

KueueJob = namedtuple("KueueJob", "crd jobspec submit_result, callback error_callback")


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

    def cancel(self):
        """
        cancel execution, usually by way of control+c. Cleanup is done in
        shutdown (deleting cached workdirs in Google Cloud Storage
        """
        batch_api = client.BatchV1Api()
        for job in self.active_jobs:
            resp = batch_api.delete_namespaced_job(
                name=job.crd.jobname,
                body=job.jobpsec,
                namespace=self.executor_args.namespace,
            )
            print(resp)
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
        command = shlex.split(command)

        # Not sure if this is the right way to get container in Snakefile
        container = (
            job.resources.get("container")
            or self.executor_args.container
            or get_container_image()
        )

        # TODO HOW TO WRITE LOGS TO FILE
        # fluxjob.stderr = flux_logfile
        # note that we pass forward the job to allow for custom resources

        # Determine which CRD / operator to generate
        operator_type = job.resources.get("kueue.operator") or "job"
        if operator_type == "job":
            crd = custom_resource.BatchJob(job, self.executor_args)
        else:
            raise WorkflowError(
                "Currently only kueue.operator: job is supported under resources."
            )

        # Generate the job first
        spec = crd.generate(
            image=container,
            command=command[0],
            args=command[1:],
            # TODO memory needs to be retrieved and set to string
            working_dir=self.workdir,
            # Don't pass local environment for now
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
                crd,
                spec,
                result,
                callback,
                error_callback,
            )
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

                # TODO need to get kueue status here
                # contribute PR there first for how to do that.
                # STOPPED HERE
                if j.flux_future.done():
                    # The exit code can help us determine if the job was successful
                    try:
                        exit_code = j.flux_future.result(0)
                    except RuntimeError:
                        # job did not complete
                        self.print_job_error(j.job, jobid=j.jobid)
                        j.error_callback(j.job)

                    else:
                        # the job finished (but possibly with nonzero exit code)
                        if exit_code != 0:
                            self.print_job_error(
                                j.job, jobid=j.jobid, aux_logs=[j.flux_logfile]
                            )
                            j.error_callback(j.job)
                            continue

                        # Finished and success!
                        j.callback(j.job)

                # Otherwise, we are still running
                else:
                    still_running.append(j)
            async with async_lock(self.lock):
                self.active_jobs.extend(still_running)

            # Sleeps for 10 seconds
            await sleep()
