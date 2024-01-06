from enum import Enum

from kubernetes import client, config
from snakemake.logging import logger

import snakemake_executor_plugin_kueue.utils as utils

config.load_kube_config()


class JobStatus(Enum):
    ACTIVE = 1
    FAILED = 3
    READY = 2
    SUCCEEDED = 4
    UNKNOWN = 5
    PENDING = 6


class KubernetesObject:
    """
    Shared class and functions for Kubernetes object.
    """

    def __init__(self, job, snakefile, settings):
        self.job = job
        self.snakefile = snakefile
        self.settings = settings
        self.jobname = None
        self.snakefile_dir = "/snakemake_workdir"

    def write_log(self, logfile):
        pass

    def cleanup(self):
        pass

    def delete_pods(self, name):
        """
        Delete namespaced pods.
        """
        with client.ApiClient() as api_client:
            api = client.CoreV1Api(api_client)
            pods = api.list_namespaced_pod(
                namespace=self.settings.namespace,
                label_selector=f"job-name={name}",
            )
            for pod in pods.items:
                api.delete_namespaced_pod(
                    namespace=self.settings.namespace,
                    name=pod.metadata.name,
                )

    @property
    def snakefile_configmap(self):
        return self.jobprefix + "-snakefile"

    def delete_snakemake_configmap(self):
        """
        Delete the config map.
        """
        with client.ApiClient() as api_client:
            api = client.CoreV1Api(api_client)
            api.delete_namespaced_config_map(
                namespace=self.settings.namespace, name=self.snakefile_configmap
            )

    def prepare_annotations(self):
        """
        Given a set of input uris and a container, prepare annotations
        """
        annotations = {}
        return annotations

    def create_snakemake_configmap(self):
        """
        Create a config map for the Snakefile
        """
        cm = client.V1ConfigMap(
            api_version="v1",
            kind="ConfigMap",
            metadata=client.V1ObjectMeta(
                name=self.snakefile_configmap, namespace=self.settings.namespace
            ),
            data={"snakefile": utils.read_file(self.snakefile)},
        )
        with client.ApiClient() as api_client:
            api = client.CoreV1Api(api_client)
            api.create_namespaced_config_map(namespace=self.settings.namespace, body=cm)

    @property
    def jobprefix(self):
        """
        Derive the jobname from the associated job.
        """
        return ("snakejob-%s-%s" % (self.job.name, self.job.jobid)).replace("_", "-")

    @property
    def job_artifact(self):
        """
        Artifact name for job to push and pull to.

        This likely needs to be more intelligent to associate with a specific step.
        Right now we use one global identifier.
        """
        return ("snakejob-%s-%s" % (self.job.name, self.job.jobid)).replace("_", "-")


class BatchJob(KubernetesObject):
    """
    A default kubernetes batch job.
    """

    def status(self):
        """
        Get the status of the batch job.

        This should return one of four JobStatus. Note
        that we likely need to tweak the logic here.
        """
        batch_api = client.BatchV1Api()

        # This is providing the name, and namespace
        try:
            job = batch_api.read_namespaced_job(self.jobname, self.settings.namespace)
        except Exception as e:
            logger.debug(str(e))
            return JobStatus.PENDING

        # Any failure consider the job a failure
        if job.status.failed is not None and job.status.failed > 0:
            return JobStatus.FAILED

        # Any jobs either active or ready, we aren't done yet
        if job.status.active:
            return JobStatus.ACTIVE
        if job.status.ready:
            return JobStatus.READY

        # Have all completions succeeded?
        succeeded = job.status.succeeded
        if succeeded and succeeded == job.spec.completions:
            return JobStatus.SUCCEEDED
        return JobStatus.UNKNOWN

    def cleanup(self):
        """
        Cleanup, usually the job and config map.

        We do an extra check for the pods, sometimes I don't
        see them deleted with the batch job.
        """
        batch_api = client.BatchV1Api()
        batch_api.delete_namespaced_job(
            name=self.jobname,
            namespace=self.settings.namespace,
        )
        self.delete_pods(self.jobname)
        self.delete_snakemake_configmap()

    def submit(self, job):
        """
        Receive the job back and submit it.

        This could easily be one function, but instead we are allowing
        the user to get it back (and possibly inspect) and then submit.
        """
        batch_api = client.BatchV1Api()

        # Create a config map for the Snakefile
        self.create_snakemake_configmap()
        result = batch_api.create_namespaced_job(self.settings.namespace, job)
        self.jobname = result.metadata.name
        return result

    def write_log(self, logfile):
        """
        Write the job output to a logfile.

        Pods associated with a job will have a label for "jobname"
            metadata:
            labels:
               job-name: tacos46bqw
        """
        with client.ApiClient() as api_client:
            api = client.CoreV1Api(api_client)
            pods = api.list_namespaced_pod(
                namespace=self.settings.namespace,
                label_selector=f"job-name={self.jobname}",
            )
            # Write new file for the job if existed
            utils.write_file(f"==== Job {self.jobname}\n", logfile)
            for pod in pods.items:
                utils.append_file(f"==== Pod {pod.metadata.name}\n", logfile)
                log = api.read_namespaced_pod_log(
                    name=pod.metadata.name,
                    namespace=self.settings.namespace,
                    container=self.jobprefix,
                )
                logger.debug(f"Writing output for {pod.metadata.name} to {logfile}")
                utils.append_file(log, logfile)

    def generate(
        self,
        image,
        command,
        args,
        deadline=None,
        environment=None,
    ):
        """
        Generate a CRD for a snakemake Job to run on Kubernetes.

        This function is intended for batchv1/Job, and we will eventually
        support others for the MPI Operator and Flux Operator.
        """
        deadline = self.job.resources.get("runtime")
        nodes = self.job.resources.get("_nodes")
        cores = self.job.resources.get("_cores")
        memory = self.job.resources.get("kueue_memory", "200Mi") or "200Mi"

        # Prepare annotations for the job spec
        annotations = self.prepare_annotations()

        metadata = client.V1ObjectMeta(
            generate_name=self.jobprefix,
            labels={
                "kueue.x-k8s.io/queue-name": self.settings.queue_name,
            },
            annotations=annotations,
        )

        environment = environment or {}
        environ = []
        for key, value in environment.items():
            environ.append({"name": key, "value": value})

        # Job container
        container = client.V1Container(
            image=image,
            name=self.jobprefix,
            command=[command],
            args=args,
            working_dir=self.settings.working_dir,
            volume_mounts=[
                client.V1VolumeMount(
                    mount_path=self.snakefile_dir,
                    name="snakefile-mount",
                ),
                client.V1VolumeMount(
                    mount_path="/workdir",
                    name="workdir-mount",
                    read_only=False,
                ),
            ],
            env=environ,
            resources={
                "requests": {
                    "cpu": cores,
                    "memory": memory,
                }
            },
        )

        if deadline:
            container.active_deadline_seconds = deadline

        # Prepare volumes (with config map)
        # TODO add volume to minicluster
        volumes = [
            client.V1Volume(
                name="snakefile-mount",
                config_map=client.V1ConfigMapVolumeSource(
                    name=self.snakefile_configmap,
                    items=[
                        client.V1KeyToPath(
                            key="snakefile",
                            path="Snakefile",
                        )
                    ],
                ),
            ),
            client.V1Volume(
                name="workdir-mount", empty_dir=client.V1EmptyDirVolumeSource()
            ),
        ]

        # Job template (this has the selector hard coded, should be a variable)
        template = {
            "metadata": {
                "labels": {"app": "registry"},
            },
            "spec": {
                "containers": [container],
                "restartPolicy": "Never",
                "volumes": volumes,
                "setHostnameAsFQDN": True,
                "subdomain": "r",
            },
        }

        return client.V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=metadata,
            spec=client.V1JobSpec(
                parallelism=nodes, completions=3, suspend=False, template=template
            ),
        )


class FluxMiniCluster(BatchJob):
    """
    A Flux MiniCluster CRD
    """

    version = "v1alpha2"
    group = "flux-framework.org"
    plural = "miniclusters"
    kind = "MiniCluster"

    @property
    def api_version(self):
        return f"{self.group}/{self.version}"

    def submit(self, job):
        """
        Receive the job back and submit it.
        """
        crd_api = client.CustomObjectsApi()
        self.create_snakemake_configmap()
        result = crd_api.create_namespaced_custom_object(
            group=self.group,
            version=self.version,
            namespace=self.settings.namespace,
            plural=self.plural,
            body=job,
        )
        self.jobname = result["metadata"]["name"]
        return result

    def cleanup(self):
        """
        Cleanup the minicluster
        """
        crd_api = client.CustomObjectsApi()
        result = crd_api.delete_namespaced_custom_object(
            name=self.jobname,
            group=self.group,
            version=self.version,
            namespace=self.settings.namespace,
            plural=self.plural,
        )
        self.delete_snakemake_configmap()
        return result

    def generate(
        self,
        image,
        command,
        args,
        deadline=None,
        environment=None,
    ):
        """
        Generate the MiniCluster crd.spec
        """
        deadline = self.job.resources.get("runtime")
        cores = self.job.resources.get("_cores")
        nodes = self.job.resources.get("_nodes")
        memory = self.job.resources.get("kueue_memory", "200Mi") or "200Mi"
        tasks = self.job.resources.get("kueue_tasks", 1) or 1

        # For the minicluster we split the command into sections
        # command is /bin/bash
        # args 0 is -c
        # args 1 is the snakemake string
        # We want to assemble into pre blocks and then the command
        parts = [x.strip() for x in args[1].split("&") if x.strip()]
        flux_submit = parts[-1]

        # write to this filename to make easier
        filename = "/tmp/run-job.sh"

        # Write the entire script to file to make it easier to run
        submit_file = utils.write_script(flux_submit, filename)
        source_flux = [". /mnt/flux/flux-view.sh", "export FLUX_URI=$fluxsocket"]
        parts = source_flux + parts[:-1] + [submit_file] + [f"cat {filename}"]

        # Try getting rid of /bin/bash -c
        container = {
            "command": f"/bin/bash {filename}",
            "pullAlways": self.settings.pull_always is not None,
            "commands": {"pre": "\n".join(parts)},
            "working_dir": self.settings.working_dir,
            "environment": environment,
            "launcher": True,
            "image": image,
            "volumes": {
                self.snakefile_configmap: {
                    "path": self.snakefile_dir,
                    "configMapName": self.snakefile_configmap,
                    "items": {"snakefile": "Snakefile"},
                }
            },
            "resources": {
                "limits": {
                    "cpu": cores,
                    "memory": memory,
                },
                "requests": {
                    "cpu": cores,
                    "memory": memory,
                },
            },
        }
        minicluster = {
            "apiVersion": self.api_version,
            "kind": self.kind,
            "metadata": {
                "generateName": self.jobprefix,
                "namespace": self.settings.namespace,
            },
            "spec": {
                "job_labels": {"kueue.x-k8s.io/queue-name": self.settings.queue_name},
                "flux": {"container": {"image": self.settings.flux_container}},
                "containers": [container],
                "interactive": self.settings.interactive is not None,
                "size": nodes,
                "tasks": int(tasks),
                "logging": {"quiet": False},
                "pod": {
                    "annotations": self.prepare_annotations(),
                    "labels": {"app": "registry"},
                },
            },
        }
        if deadline:
            minicluster["spec"]["deadline"] = deadline
        return minicluster
