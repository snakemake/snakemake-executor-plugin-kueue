from dataclasses import dataclass, field
from typing import Optional
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
    container: Optional[str] = field(
        default=None,
        metadata={
            "help": "Container base to use for Kubernetes cluster pods.",
            "env_var": False,
            "required": False,
        },
    )
    working_dir: Optional[str] = field(
        default=None,
        metadata={
            "help": "Working directory for job (defaults to unset)",
            "env_var": False,
            "required": False,
        },
    )
    pull_always: Optional[str] = field(
        default=None,
        metadata={
            "help": "For operators that allow it, always pull the container",
            "env_var": False,
            "required": False,
        },
    )
    interactive: Optional[str] = field(
        default=None,
        metadata={
            "help": "Set interactive to True to debug your MiniCluster containers",
            "env_var": False,
            "required": False,
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
    nodes: Optional[int] = field(
        default=1,
        metadata={
            "help": "Number of nodes (size) for the Flux MiniCluster (defaults to 1)",
            "env_var": False,
            "required": False,
        },
    )
    flux_container: Optional[str] = field(
        default="ghcr.io/converged-computing/flux-view-ubuntu:tag-jammy",
        metadata={
            "help": "Flux view container (see converged-computing/flux-views).",
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
    job_deploy_sources=True,
    non_local_exec=True,
    pass_default_storage_provider_args=True,
    implies_no_shared_fs=True,
)
