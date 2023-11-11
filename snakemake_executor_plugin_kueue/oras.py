from snakemake_interface_common.exceptions import WorkflowError  # noqa

import portforward
import oras.client
import os


class OrasRegistry:
    def __init__(
        self, settings, workdir, local_port=5000, local_registry="http://localhost"
    ):
        """
        Handle interactions with the oras registry

        The working directory does not change, and we assume port forwarding
        """
        self.settings = settings
        self.workdir = os.path.abspath(workdir)
        self.local_registry = local_registry
        self.local_port = local_port

    @property
    def pod_name(self):
        return f"{self.settings.oras_cache_name}-0"

    @property
    def namespace(self):
        return self.settings.namespace

    @property
    def registry(self):
        """
        The local registry is always on localhost
        """
        return f"{self.local_registry}:{self.local_port}"

    @property
    def pod_port(self):
        return self.settings.oras_service_port

    @property
    def insecure(self):
        return self.local_registry.startswith("http://")

    @property
    def dirname(self):
        return os.path.basename(self.workdir)

    def pull(self, container):
        """
        Pull a step to the working directory.

        I'm not sure we should do this every time - I think we might just want
        to do it at the end once. But if a job fails, arguably we should get the
        last state and not run things again...
        """
        # No path to kube config provided - will use default from $HOME/.kube/config
        with portforward.forward(
            self.namespace, self.pod_name, self.local_port, self.pod_port
        ):
            print(f"Pulling current step from {container}")
            client = oras.client.OrasClient(insecure=self.insecure)
            response = client.pull(
                allowed_media_type=[],
                overwrite=True,
                outdir=self.workdir,
                target=f"{self.registry}/{container}",
            )
            if response.status_code not in [200, 201]:
                raise WorkflowError("Issue pushing to {container}: {response.reason}")

    def push(self, container):
        """
        Push a container to the local registry (via portforward)
        """
        # The starting container has the uid as the tag
        container = f"{self.registry}/{container}"

        # No path to kube config provided - will use default from $HOME/.kube/config
        with portforward.forward(
            self.namespace, self.pod_name, self.local_port, self.pod_port
        ):
            print(f"Pushing working directory {root} to {container}")
            client = oras.client.OrasClient(insecure=self.insecure)
            response = client.push(files=[self.dirname], target=container)
            if response.status_code not in [200, 201]:
                raise WorkflowError("Issue pushing to {container}: {response.reason}")
