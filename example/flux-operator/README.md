# Flux Operator Workflow

Given that you've installed Kueue (see the main [README](../README.md)) and have snakemake locally, you can
first install the Flux Operator. Note that we are installing a [development branch](https://github.com/flux-framework/flux-operator/issues/211):

```bash
kubectl apply -f https://raw.githubusercontent.com/flux-framework/flux-operator/test-refactor-modular/examples/dist/flux-operator-refactor.yaml
```

You will still need to choose a storage provider (for lammps output files).
And then:

```bash
snakemake --cores 1 --executor kueue --jobs 1 --default-storage-provider s3 --default-storage-prefix s3://snakemake-testing-llnl
```

Note that this is a WIP - I currently have a hello world (with variables) almost working, and after will tweak to have lammps run instead.