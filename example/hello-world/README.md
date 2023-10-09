# Hello World Workflow

Given that you've installed Kueue (see the main [README](../README.md)) and have snakemake locally, you can first create the local registry:

```bash
$ kubectl apply -f ../registry.yaml
```

This registry (local or otherwise) will be a temporary cache for you to push artifacts between steps.
We will use the registry running locally on our same cluster: `registry-0.r.default.svc.cluster.local:5000`.
Note that if you need an external registry, you likely need credentials or similar.

```bash
$ snakemake --cores 1 --executor kueue --kueue-registry registry-0:5000.r.default.svc.cluster.local:5000 --jobs 1 --kueue-insecure yes
```

STOPPED HERE - get hack for insecure working.

In the above note that:

 - we use the `kueue` executor
 - the registry is provided by the same headless service
 - we are asking for the registry to be insecure (we don't have https)


TODO

deploy reigstry
run example and check pods for labels
see if can exec into pod nad see registry
need a way to create a user/login associated with the job
run everything and cleanup at the end (give instruction to pull finished data)
would we need a starting pod to manage some final state of data?  Or to launch from it (and pull at end?)