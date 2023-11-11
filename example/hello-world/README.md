# Hello World Workflow

Given that you've installed Kueue (see the main [README](../README.md)) and have snakemake locally, you should
first install the ORAS Operator to create your local cache:

```bash
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.1/cert-manager.yaml
kubectl apply -f https://raw.githubusercontent.com/converged-computing/oras-operator/main/examples/dist/oras-operator.yaml
```

create your local cache:

```bash
kubectl apply -f oras.yaml
```

This registry will be a temporary cache for pushing and pulling artifacts between steps. You can use another storage remote if desired,
but I (vsoch) find this easier for Kubernetes (when the data isn't huge).

```bash
$ snakemake --cores 1 --executor kueue --kueue-registry oras-0:5000.oras.default.svc.cluster.local:5000 --jobs 1
```

In the above note that:

 - we use the `kueue` executor
 - the registry is provided by the same headless service, and it's exposed via a kind configuration and node port.

## Debugging

Try port forwarding:

```bash
$ kubectl port-forward oras-0 5000:5000
Forwarding from 127.0.0.1:5000 -> 5000
Forwarding from [::1]:5000 -> 5000
Handling connection for 5000
Handling connection for 5000
```

And then list:

```bash
oras pull localhost:5000/dinosaur/hello-world:latest --insecure
oras pull localhost:5000/dinosaur/hello-world:pancakes --insecure
Downloading d2164606501f .
Downloaded  d2164606501f .
Pulled [registry] localhost:5000/dinosaur/hello-world:latest
Digest: sha256:9efa0709ca99b09f68f2ed90a43aaf5feebe69d7158d40fc2025785811f166cb
```
