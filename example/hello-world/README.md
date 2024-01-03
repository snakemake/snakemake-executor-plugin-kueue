# Hello World Workflow

Given that you've installed Kueue (see the main [README](../README.md)) and have snakemake locally, you need
to choose a storage provider, and then:

```bash
snakemake --cores 1 --executor kueue --jobs 1 --default-storage-provider s3 --default-storage-prefix s3://snakemake-testing-llnl
```
```console
Building DAG of jobs...
Uploading source archive to storage provider...
Using shell: /usr/bin/bash
Provided remote nodes: 1
Job stats:
job            count
-----------  -------
all                1
hello_world        2
total              3

Select jobs to execute...
Execute 1 jobs...

[Tue Jan  2 23:08:51 2024]
rule hello_world:
    output: s3://snakemake-testing-llnl/hola1/world.txt (send to storage)
    jobid: 2
    reason: Missing output files: s3://snakemake-testing-llnl/hola1/world.txt (send to storage)
    wildcards: greeting=hola1
    resources: tmpdir=<TBD>, kueue_operator=job

Use:
'kubectl get queue' to see queue assignment 'kubectl get jobs' to see jobs'
JobStatus.ACTIVE
JobStatus.ACTIVE
JobStatus.ACTIVE
JobStatus.SUCCEEDED
[Tue Jan  2 23:09:32 2024]
Finished job 2.
1 of 3 steps (33%) done
Select jobs to execute...
Execute 1 jobs...

[Tue Jan  2 23:09:32 2024]
rule hello_world:
    output: s3://snakemake-testing-llnl/hello1/world.txt (send to storage)
    jobid: 1
    reason: Missing output files: s3://snakemake-testing-llnl/hello1/world.txt (send to storage)
    wildcards: greeting=hello1
    resources: tmpdir=<TBD>, kueue_operator=job

Use:
'kubectl get queue' to see queue assignment 'kubectl get jobs' to see jobs'
JobStatus.ACTIVE
JobStatus.ACTIVE
JobStatus.ACTIVE
JobStatus.SUCCEEDED
[Tue Jan  2 23:10:12 2024]
Finished job 1.
2 of 3 steps (67%) done
Select jobs to execute...
Execute 1 jobs...

[Tue Jan  2 23:10:12 2024]
localrule all:
    input: s3://snakemake-testing-llnl/hello1/world.txt (retrieve from storage), s3://snakemake-testing-llnl/hola1/world.txt (retrieve from storage)
    jobid: 0
    reason: Input files updated by another job: s3://snakemake-testing-llnl/hello1/world.txt (retrieve from storage), s3://snakemake-testing-llnl/hola1/world.txt (retrieve from storage)
    resources: tmpdir=/tmp

[Tue Jan  2 23:10:12 2024]
Finished job 0.
3 of 3 steps (100%) done
Complete log: .snakemake/log/2024-01-02T230850.765184.snakemake.log
```

In the above we take advantage of Snakemake's ability to use remotes to get around the issue that Kubernetes isn't great with storage. :)