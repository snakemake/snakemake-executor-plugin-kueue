# Flux Operator Workflow

Given that you've installed Kueue (see the main [README](../README.md)) and have snakemake locally, you can
first install the Flux Operator. Note that we are installing a [development branch](https://github.com/flux-framework/flux-operator/issues/211):

```bash
kubectl apply -f https://raw.githubusercontent.com/flux-framework/flux-operator/test-refactor-modular/examples/dist/flux-operator-refactor.yaml
```

You will still need to choose a storage provider (for lammps output files). Note in the [Snakefile](Snakefile) that we are using the container
as a launcher, meaning that our command is going to need to have flux commands in it (e.g., submit, run). This allows you more freedom to
customize how you want the job to be. When you are ready:

```bash
snakemake --cores 2 --executor kueue --jobs 1 --default-storage-provider s3 --default-storage-prefix s3://snakemake-testing-llnl --kueue-working-dir /home/flux/examples/reaxff/HNS
```
```console
Building DAG of jobs...
Uploading source archive to storage provider...
Using shell: /usr/bin/bash
Provided remote nodes: 1
Job stats:
job       count
------  -------
all           1
lammps        1
total         2

Select jobs to execute...
Execute 1 jobs...

[Sat Jan  6 14:13:26 2024]
rule lammps:
    output: s3://snakemake-testing-llnl/iter-1/lammps.out (send to storage)
    jobid: 1
    reason: Missing output files: s3://snakemake-testing-llnl/iter-1/lammps.out (send to storage)
    wildcards: iter=iter-1
    resources: tmpdir=<TBD>, kueue_operator=flux-operator, kueue_tasks=4, kueue_memory=600Mi, container=vanessa/snakemake:lammps

Use:
'kubectl get queue' to see queue assignment 'kubectl get jobs' to see jobs'
JobStatus.ACTIVE
JobStatus.ACTIVE
JobStatus.ACTIVE
JobStatus.ACTIVE
JobStatus.ACTIVE
JobStatus.ACTIVE
JobStatus.ACTIVE
JobStatus.ACTIVE
JobStatus.ACTIVE
JobStatus.SUCCEEDED
[Sat Jan  6 14:15:12 2024]
Finished job 1.
1 of 2 steps (50%) done
Select jobs to execute...
Execute 1 jobs...

[Sat Jan  6 14:15:12 2024]
localrule all:
    input: s3://snakemake-testing-llnl/iter-1/lammps.out (retrieve from storage), s3://snakemake-testing-llnl/iter-2/lammps.out (retrieve from storage)
    jobid: 0
    reason: Input files updated by another job: s3://snakemake-testing-llnl/iter-1/lammps.out (retrieve from storage)
    resources: tmpdir=/tmp

[Sat Jan  6 14:15:12 2024]
Finished job 0.
2 of 2 steps (100%) done
Complete log: .snakemake/log/2024-01-06T141325.960322.snakemake.log
```

Note that we can set the global working directory because there is just one step with lammps (that uses that). If you needed this on the level of the step, you
could define it as a kueue attribute instead in the Snakefile. Also note that the container here is built from the [Dockerfile](Dockerfile):

```bash
docker build -t vanessa/snakemake:lammps .
```

At the time of development, the steps provided by snakemake to install are not flexible to different (older) versions of Python. Also note that we are using the flux refactor branch (not merged yet).
Here is the first successful run!

![first-successful-run.png](first-successful-run.png)

When you are done, clean up:

```bash
kind delete cluster
```
