# Hello World Workflow

Given that you've installed Kueue (see the main [README](../README.md)) and have snakemake locally, you can first create the local registry:

```bash
$ kubectl apply -f ../registry.yaml
```

And run the workflow:

```bash
$ snakemake --cores 1 --executor kueue --kueue-registry registry-0
```

TODO

deploy reigstry
run example and check pods for labels
see if can exec into pod nad see registry
need a way to create a user/login associated with the job
run everything and cleanup at the end (give instruction to pull finished data)
would we need a starting pod to manage some final state of data?  Or to launch from it (and pull at end?)