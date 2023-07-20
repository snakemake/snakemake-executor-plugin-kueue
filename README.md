# Snakemake Executor Kueue

This is a [snakemake executor plugin](https://github.com/snakemake/snakemake-executor-plugin-interface/)
that enables interaction with [Kueue](https://kueue.sigs.k8s.io/docs/overview/). The plugin will
install Python dependencies that are needed, and it's assumed that you have [installed Kueue and have queues configured](https://kueue.sigs.k8s.io/docs/tasks/run_jobs/#before-you-begin).

**under development** not read for use! I am working on doing PRs to Kueue to add examples for Python
interaction in parallel with the work here. I've written the code but largely have not tested / developed fully yet!

## Usage

### Setup

You will need to create a cluster first. For local development we recommend [kind](https://kind.sigs.k8s.io/docs/user/quick-start/#installing-from-source):

```bash
$ kind create cluster
```

You will then need to [install Kueue](https://kueue.sigs.k8s.io/docs/installation/) and
[create your local queues](https://kueue.sigs.k8s.io/docs/tasks/administer_cluster_quotas/) with cluster quotas.

E.g., here is an example:

```bash
VERSION=v0.4.0
kubectl apply -f https://github.com/kubernetes-sigs/kueue/releases/download/$VERSION/manifests.yaml
kubectl apply -f https://raw.githubusercontent.com/kubernetes-sigs/kueue/main/site/static/examples/single-clusterqueue-setup.yaml
```

You'll also need kubernetes python installed. We recommend a virtual environment (also with snakemake)

```bash
python -m venv env
source env/bin/activate
pip install kubernetes requests snakemake
```

And of course install the plugin! From the cloned repository you can do:

```bash
pip install .
```

### Job Resources

#### Operator

By default, Kueue will use a batchv1/Job for each step. However, you can
customize this to a different operator with the job [resources](https://snakemake.readthedocs.io/en/stable/snakefiles/rules.html#resources)
via the kueue.operator attribute:

**Note this does not work yet, as the resource names are checked**

```yaml
rule a:
    input:     ...
    output:    ...
    resources:
        kueue.operator=flux-operator
    shell:
        "..."
```

We currently support the following `operator`s:

 - flux-operator: deploy using the [Flux Operator](https://github.com/flux-framework/flux-operator)
 - mpi-operator: deploy using the [MPI Operator](https://github.com/kubeflow/mpi-operator/)
 - job: (the default) either unset, or set to "job"

Note that you are in charge of installing and configuring the various operators on your cluster!
See the [Kueue tasks](https://kueue.sigs.k8s.io/docs/tasks/) for more details.

#### Container

If you are using the Flux operator, you need a container with Flux and your
software! We have prepared a container with Flux, Snakemake, and Mamba for you to get started.
The [Dockerfile is here](https://github.com/rse-ops/flux-hpc/blob/main/snakemake/mamba/Dockerfile) and you can use our build as follows:

```yaml
rule a:
    input:     ...
    output:    ...
    resources:
        container=ghcr.io/rse-ops/mamba:app-mamba
    shell:
        "..."
```

#### Memory

The memory defined for Kubernetes is in a string format, and while we could ideally
do a conversion for now we are lazy and ask you to define it directly:

```yaml
rule a:
    input:     ...
    output:    ...
    resources:
        kueue.memory=200M1
    shell:
        "..."
```

#### Tasks

The Flux Operator can handle tasks for MPI, so you can set them as follows:

```yaml
rule a:
    input:     ...
    output:    ...
    resources:
        kueue.tasks=1
    shell:
        "..."
```


For examples, check out the [example](example) directory.

## Want to write a plugin?

If you are interested in writing your own plugin, instructions are provided via the [snakemake-executor-plugin-interface](https://github.com/snakemake/snakemake-executor-plugin-interface).

## License

HPCIC DevTools is distributed under the terms of the MIT license.
All new contributions must be made under this license.

See [LICENSE](https://github.com/converged-computing/cloud-select/blob/main/LICENSE),
[COPYRIGHT](https://github.com/converged-computing/cloud-select/blob/main/COPYRIGHT), and
[NOTICE](https://github.com/converged-computing/cloud-select/blob/main/NOTICE) for details.

SPDX-License-Identifier: (MIT)

LLNL-CODE- 842614