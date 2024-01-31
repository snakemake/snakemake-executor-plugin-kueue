FROM python:3.12.0-bookworm

# This is building the testing container
# docker build -t vanessa/snakemake:kueue .

RUN apt-get update \
    && apt-get install -y --no-install-recommends git openssh-client openssh-server

RUN pip3 install -U git+https://github.com/snakemake/snakemake-interface-common@main && \
    pip3 install -U git+https://github.com/snakemake/snakemake-interface-executor-plugins && \
    pip3 install -U git+https://github.com/snakemake/snakemake-interface-storage-plugins@main && \
    pip3 install -U git+https://github.com/snakemake/snakemake-storage-plugin-s3@main && \
    pip3 install -U git+https://github.com/snakemake/snakemake-storage-plugin-gcs@main && \
    pip3 install -U git+https://github.com/snakemake/snakemake@main
    
# Add priviledge separation directoy to run sshd as root.
RUN mkdir -p /var/run/sshd

# Allow OpenSSH to talk to containers without asking for confirmation
# by disabling StrictHostKeyChecking.
# mpi-operator mounts the .ssh folder from a Secret. For that to work, we need
# to disable UserKnownHostsFile to avoid write permissions.
# Disabling StrictModes avoids directory and files read permission checks.
ARG port=22
RUN sed -i "s/[ #]\(.*StrictHostKeyChecking \).*/ \1no/g" /etc/ssh/ssh_config \
    && echo "    UserKnownHostsFile /dev/null" >> /etc/ssh/ssh_config \
    && sed -i "s/[ #]\(.*Port \).*/ \1$port/g" /etc/ssh/ssh_config \
    && sed -i "s/#\(StrictModes \).*/\1no/g" /etc/ssh/sshd_config \
    && sed -i "s/#\(Port \).*/\1$port/g" /etc/ssh/sshd_config && \
    ssh-keygen -A && \
    service ssh --full-restart

# Wrappers to ensure we source the mamba environment!
WORKDIR /workflow