# Snakemake Executor Kueue

This is a [snakemake executor plugin](https://github.com/snakemake/snakemake-executor-plugin-interface/)
that enables interaction with [Kueue](https://kueue.sigs.k8s.io/docs/overview/). The plugin will
install Python dependencies that are needed, and it's assumed that you have [installed Kueue and have queues configured](https://kueue.sigs.k8s.io/docs/tasks/run_jobs/#before-you-begin).

**under development** note that the base container is a custom build under my namespace (`vanessa`)
that has clones from main branches (as opposed to releases).

## Overview

[Kueue](https://kueue.sigs.k8s.io/docs/overview/) is (in simple terms) a job queueing system for Kubernetes. It doesn't just hold the queue, however, it also manages resource groups and decides when a job should be admitted (the pods allowed to be created so a job can run) and when they should be deleted. If you have used high performance computing workload managers, this would correpond to the queue of jobs. 

[Snakemake](https://snakemake.readthedocs.io/en/stable/) is a workflow management system. It is not concerned with a queue of work, but rather preparing steps from a directed acyclic graph (DAG) and then submitting the steps as jobs to a workload manager. Traditionally, many successful workflow tools have been developed for the biosciences, meaning that individual steps come down to running tools like bwa or samtools, and with little integration of high performance computing technologies like MPI.

While you may not traditionally think of Kubernetes as a place to run MPI, with the movement for converged computing, this is changing. Technologies like the [Flux Operator](https://github.com/flux-framework/flux-operator) and [MPI Operator](https://github.com/kubeflow/mpi-operator) make it possible to run MPI workflows in Kubernetes. Since they are deployed as modular jobs (one or more pods working together) by an operator, this presents another opportunity for convergence - bringing together traditional workflow tools to submit not steps as jobs to an HPC system, but as [operator custom resource definitions](https://kubernetes.io/docs/concepts/extend-kubernetes/operator/) (CRD) to Kubernetes. This would allow simple steps to co-exist alongside steps that warrant more complex MPI. This is something I have been excited about for a while, and am (also) excited to share the first prototype here of that vision.  Let's talk about what this might look like with a simple example, below.

![docs/kueue-snakemake.png](docs/kueue-snakemake.png)

In the above, we start with a workflow tool. In this case we are using Snakemake. The workflow tool is able to take a specification file, which in this case is the [Snakefile](https://snakemake.readthedocs.io/en/stable/snakefiles/rules.html), a human understandable definition of a workflow, and convert it into a directed acyclic graph, or DAG, which is essentially a directed graph. In this graph, each step can be thought of as a single job in the workflow that will receive it's own inputs, environment, and even container (especially in the case of Kubernetes) and then is expected to produce some output files. The modularity of a DAG also makes it amenable to operators. For example, if we have a step that runs LAMMPS simulations and needs MPI, we might submit a step to the Flux Operator to run a Flux Framework cluster in Kubernetes. If we just need to run a bash script for some analysis and don't need that complexity, we might choose a job instead. To go back to our picture, we see that the DAG generated for this faux workflow has 5 steps, and each of them is going to be given (by Snakemake) to our queueing software, which in this case is Kueue. The snakemake kueue executor knows how to read the Snakefile and see what CRDs are desired for each step, and then prepare those custom resource definitions (yaml definitions) that are going to be given to Kueue. Importantly, it's also the workflow software that manages timing of things and inputs and outputs. For example, Snakemake will be looking for the input for step 2 from step 1, and will throw an error if it's not there. Speaking of inputs and outputs, for this kind of setup where there isn't a shared filesystem, the common strategy in bioinformatics is to use object or remote storage, and this is [also built into Snakemake](https://snakemake.readthedocs.io/en/stable/snakefiles/storage.html). When all is said and done, Snakemke is creating jobs to run in Kubernetes that know how to find their inputs and send back their outputs, and the Snakemake Kueue executor here orchestrates the entire thing! 

Is that cool, or what? Note that this is just a prototype - I haven't even finished with the MPI Operator yet (or other types that might be of interest). For some additional background, this ability came with [Snakemake 8.0](https://github.com/snakemake/snakemake/issues/2409) where we introduced modules for executors, giving a developer like myself the freedom to prototype without needing to formally add to the Snakemake codebase.

- [Excalidraw](https://excalidraw.com/#json=GxNYIdV0njBCQQ8Sq4laz,3R0qBW7_l5sntn0flqm3bw)

## Usage

### Setup

You will need to create a cluster first. For local development we recommend [kind](https://kind.sigs.k8s.io/docs/user/quick-start/#installing-from-source):

```bash
kind create cluster
```

#### Install Kueue

You will then need to [install Kueue](https://kueue.sigs.k8s.io/docs/installation/) and
[create your local queues](https://kueue.sigs.k8s.io/docs/tasks/administer_cluster_quotas/) with cluster quotas

E.g., here is an example:

```bash
VERSION=v0.4.0
kubectl apply -f https://github.com/kubernetes-sigs/kueue/releases/download/$VERSION/manifests.yaml
```

Then (wait a few minutes until the jobset controller is running.) and:

```bash
kubectl  apply -f example/cluster-queue.yaml 
kubectl  apply -f example/resource-flavor.yaml 
kubectl  apply -f example/user-queue.yaml 
```
```console
clusterqueue.kueue.x-k8s.io/cluster-queue created
resourceflavor.kueue.x-k8s.io/default-flavor created
localqueue.kueue.x-k8s.io/user-queue created
```

You'll also need kubernetes python installed, and of course Snakemake! Assuming you have snakemake and the plugin here installed, you should be good to go.
Here is how I setup a local or development environment.

```bash
python -m venv env
source env/bin/activate
pip install .
```

### Container

Note that while Snakemake still has a lot of moving pieces, the default container is built from the [Dockerfile](Dockerfile) here and provided as `vanessa/snakemake:kueue` in the executor code. Next go into an [example](example) directory to test out the Kueue executor.

### Job Resources

For the different options below, each is exposed as a step option (as shown) or a flag, which would be applied globally and take the format:

```console
--kueue-<option>

# E.g., for pull_always:
--kueue-pull-always yes
```

not all are supported for every operator. E.g., interactive mode is just for the Flux Operator,
and some features are possible for other operators (but not implemented yet)! If there is a feature you want implemented or exposed,
please [open an issue](https://github.com/snakemake/snakemake-executor-plugin-kueue/issues).

#### Operator

By default, Kueue will use a batchv1/Job for each step. However, you can
customize this to a different operator with the job [resources](https://snakemake.readthedocs.io/en/stable/snakefiles/rules.html#resources)
via the kueue_operator attribute:

```yaml
rule a:
    input:     ...
    output:    ...
    resources:
        kueue_operator=flux-operator
    shell:
        "..."
```

Along with a standard batchv1 Job, We currently support the following `operator`s:

 - flux-operator: deploy using the [Flux Operator](https://github.com/flux-framework/flux-operator)
 - job: (the default) either unset, or set to "job"

And likely coming soon (or when someone requests it):

 - mpi-operator: deploy using the [MPI Operator](https://github.com/kubeflow/mpi-operator/)

Note that you are in charge of installing and configuring the various operators on your cluster!
See the [Kueue tasks](https://kueue.sigs.k8s.io/docs/tasks/) for more details.

#### Container

You can customize the container you are using, which should have minimally Snakemake and your application
software. We have prepared a container with Flux, Snakemake, and the various other plugins for you to get started.
The [Dockerfile](Dockerfile) is packaged here if you'd like to tweak it, e.g.,

```yaml
rule hello_world:
    output:
        "...",
    resources: 
        container="ghcr.io/rse-ops/mamba:snakemake",
        kueue_operator="job"
    shell:
        "..."
```

See the [lammps](./example/flux-operator/lammps) example with the Flux Operator for a custom container.

#### Working Directory

The working directory will be where the container starts, and if you don't define it, it will use the container default.
This can be defined globally with `--kueue-working-dir` or as a step attribute:

```yaml
rule hello_world:
    output:
        "...",
    resources: 
        kueue_working_dir="/path/to/important/things"
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
        kueue_memory=200M1
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
        kueue_tasks=1
    shell:
        "..."
```


#### Nodes

This should be the number of nodes (size) for the MiniCluster.

```yaml
rule a:
    input:     ...
    output:    ...
    resources:
        kueue_nodes=4
    shell:
        "..."
```


#### Pull Always

This tells the Flux Operator to freshly pull containers. Note that this is only exposed for this operator, but is easy to add to the others too as
the `imagePullPolicy` -> Always.

```yaml
rule a:
    input:     ...
    output:    ...
    resources:
        kueue_pull_always=yes
    shell:
        "..."
```


#### Flux Container Base

It's important that the flux view (where Flux is installed from) has a view that matches the operating system you are using. By default we use an ubuntu:kammy image. You can see the views and containers available in [this repository](https://github.com/converged-computing/flux-views). 

```yaml
rule a:
    input:     ...
    output:    ...
    resources:
        kueue_flux_container="ghcr.io/converged-computing/flux-view-rocky:tag-9"
        container="myname/myrockylinux:9"
    shell:
        "..."
```

The above would be used if you container is some rocky base.

#### Interactive

This attribute is specific to the flux operator (for now). If set to true, we will turn interactive mode to true, meaning
that the entire flux instance will start in an interactive mode (with a sleep command) so you can shell into the container
and look around.

```yaml
rule hello_world:
    output:
        "...",
    resources: 
        kueue_interactive=true
    shell:
        "..."
```

Note that your script is written to `/tmp/run-job.sh` and you can connect to your flux instance as follows:

```console
. /mnt/flux/flux-view.sh
flux proxy $fluxsocket /bin/bash
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
