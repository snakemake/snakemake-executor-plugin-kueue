from dataclasses import dataclass, field
from typing import List, Generator, Optional
from snakemake_interface_executor_plugins.settings import (
    CommonSettings,
    ExecutorSettingsBase,
)
from .executor import KueueExecutor as Executor  # noqa


# Optional:
# Define additional settings for your executor.
# They will occur in the Snakemake CLI as --<executor-name>-<param-name>
# Omit this class if you don't need any.
# Make sure that all defined fields are Optional and specify a default value
# of None or anything else that makes sense in your case.
@dataclass
class ExecutorSettings(ExecutorSettingsBase):
    queue_name: Optional[str] = field(
        default="user-queue",
        metadata={
            "help": "The name of the user queue to submit to (defaults to user-queue)",
            "env_var": False,
            "required": False,
        },
    )

    registry: Optional[str] = field(
        default="oras-0.oras.default.svc.cluster.local:5000",
        metadata={
            "help": "Registry URI to push and pull workflow caches to and from.",
            "env_var": False,
            "required": False,
        },
    )

    oras_service_port: Optional[int] = field(
        default=5000,
        metadata={
            "help": "ORAS service name (defaults to oras)",
            "env_var": False,
            "required": False,
            "type": int,
        },
    )

    oras_cache_name: Optional[str] = field(
        default="oras",
        metadata={
            "help": "Name of oras cache deployed as stateful set (defaults to oras, pod name oras-0)",
            "env_var": False,
            "required": False,
        },
    )

    # mpitune configurations are validated on c2 and c2d instances only.
    container: Optional[str] = field(
        default=None,
        metadata={
            "help": "Container base to use for Kubernetes cluster pods.",
            "env_var": False,
            "required": False,
        },
    )

    disable_oras_cache: Optional[bool] = field(
        default=False,
        metadata={
            "help": "Disable using the ORAS Operator artifact cache (you will need another remote)",
            "env_var": False,
            "required": False,
            "type": bool,
        },
    )

    namespace: Optional[str] = field(
        default="default",
        metadata={
            "help": "The namespace to submit jobs to (must exist)",
            "env_var": False,
            "required": False,
        },
    )


# Required:
# Common settings shared by various executors.
common_settings = CommonSettings(
    # define whether your executor plugin executes locally
    # or remotely. In virtually all cases, it will be remote execution
    # (cluster, cloud, etc.). Only Snakemake's standard execution
    # plugins (snakemake-executor-plugin-dryrun, snakemake-executor-plugin-local)
    # are expected to specify False here.
    non_local_exec=True,
    pass_default_storage_provider_args=False,
    # Kueue typically doesn't have a shared local filesystem. We use a trick here to
    # save steps via artifacts and then pull down, but likely need something better.
    implies_no_shared_fs=False,
)
