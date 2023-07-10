from dataclasses import dataclass, field

from snakemake_executor_plugin_interface import CommonSettings, ExecutorSettingsBase

from .executor import KueueExecutor as Executor  # noqa


# Optional:
# define additional settings for your executor
# They will occur in the Snakemake CLI as --<executor-name>-<param-name>
# Omit this class if you don't need any.
@dataclass
class ExecutorSettings(ExecutorSettingsBase):
    queue_name: str = field(
        default="user-queue",
        metadata={
            "help": "The name of the user queue to submit to (defaults to user-queue)"
        },
    )
    container: str = field(
        default=None,
        metadata={"help": "Container base to use for Kubernetes cluster pods."},
    )
    namespace: str = field(
        default="default",
        metadata={"help": "The namespace to submit jobs to (must exist)"},
    )


# Optional:
# specify common settings shared by various executors.
# Omit this statement if you don't need any and want
# to rely on the defaults (highly recommended unless
# you are very sure what you do).
common_settings = CommonSettings(use_threads=True, non_local_exec=True)
