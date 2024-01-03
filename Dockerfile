FROM python:3.12.0-bookworm

# This is building the testing container
# docker build -t vanessa/snakemake:kueue .

RUN apt-get update \
    && apt-get install -y --no-install-recommends git

RUN pip3 install -U git+https://github.com/snakemake/snakemake-interface-common@main && \
    pip3 install -U git+https://github.com/snakemake/snakemake-interface-executor-plugins && \
    pip3 install -U git+https://github.com/snakemake/snakemake-interface-storage-plugins@main && \
    pip3 install -U git+https://github.com/snakemake/snakemake-storage-plugin-s3@main && \
    pip3 install -U git+https://github.com/snakemake/snakemake-storage-plugin-gcs@main && \
    pip3 install -U git+https://github.com/snakemake/snakemake@main
    
# Wrappers to ensure we source the mamba environment!
WORKDIR /workflow