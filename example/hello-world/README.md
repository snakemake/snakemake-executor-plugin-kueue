# Hello World Workflow

Given that you've installed Kueue (see the main [README](../README.md)) and have snakemake locally, you need
to choose a storage provider, and then:

```bash
$ snakemake --cores 1 --executor kueue --jobs 1 --default-storage-provider s3 --default-storage-prefix s3://snakemake-testing-llnl
```