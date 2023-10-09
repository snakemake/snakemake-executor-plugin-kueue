install_oras = [
    "VERSION=1.1.0",
    "curl -LO https://github.com/oras-project/oras/releases/download/v${VERSION}/oras_${VERSION}_linux_amd64.tar.gz",
    "mkdir -p oras-install/",
    "tar -zxf oras_${VERSION}_*.tar.gz -C oras-install/",
    "mv oras-install/oras /usr/local/bin/",
    "rm -rf oras_${VERSION}_*.tar.gz oras-install/",
]


# oras push --insecure --plain-http registry-0.r.default.svc.cluster.local:5000/snakemake/hello_world:latest . 
# This assumes the workflow is in the PWD, and we populate the push/pull with workflow step
pull_oras = "oras pull {{ registry }}/{{ container }} . {% if insecure %}--plain-http --insecure{% endif %}"
push_oras = "oras push {{ registry }}/{{ container }} . {% if insecure %}--plain-http --insecure{% endif %}"
