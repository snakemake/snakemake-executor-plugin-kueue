# MPI Operator Workflow

Given that you've installed Kueue (see the main [README](../README.md)) and have snakemake locally, you can
first install the MPI Operator. Note that we are installing release and you can [check the repository](https://github.com/kubeflow/mpi-operator) for newer 
versions.

```bash
kubectl apply -f https://raw.githubusercontent.com/kubeflow/mpi-operator/v0.4.0/deploy/v2beta1/mpi-operator.yaml
```

You'll need to [install kubeflow-mpi](https://github.com/kubeflow/mpi-operator/tree/master/sdk/python/v2beta1), the Python SDK for the MPI Operator.

```bash
git clone --depth 1 https://github.com/kubeflow/mpi-operator/ /tmp/mpijob
cd /tmp/mpijob/sdk/python/v2beta1
pip install .
```

You will still need to choose a storage provider for output files. And then:

```bash
snakemake --cores 1 --executor kueue --jobs 1 --default-storage-provider s3 --default-storage-prefix s3://snakemake-testing-llnl --kueue-working-dir=/tmp
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
hello         1
total         2

Select jobs to execute...
Execute 1 jobs...

[Sat Jan  6 10:40:28 2024]
rule hello:
    output: s3://snakemake-testing-llnl/iter-1/hello-operator.out (send to storage)
    jobid: 1
    reason: Missing output files: s3://snakemake-testing-llnl/iter-1/hello-operator.out (send to storage)
    wildcards: iter=iter-1
    resources: tmpdir=<TBD>, kueue_operator=flux-operator

Use:
'kubectl get queue' to see queue assignment 'kubectl get jobs' to see jobs'
JobStatus.ACTIVE
JobStatus.ACTIVE
JobStatus.ACTIVE
JobStatus.SUCCEEDED
[Sat Jan  6 10:41:13 2024]
Finished job 1.
1 of 2 steps (50%) done
Select jobs to execute...
Execute 1 jobs...

[Sat Jan  6 10:41:13 2024]
localrule all:
    input: s3://snakemake-testing-llnl/iter-1/hello-operator.out (retrieve from storage), s3://snakemake-testing-llnl/iter-2/hello-operator.out (retrieve from storage)
    jobid: 0
    reason: Input files updated by another job: s3://snakemake-testing-llnl/iter-1/hello-operator.out (retrieve from storage)
    resources: tmpdir=/tmp

[Sat Jan  6 10:41:13 2024]
Finished job 0.
2 of 2 steps (100%) done
Complete log: .snakemake/log/2024-01-06T104027.307126.snakemake.log
```