FROM ubuntu:jammy

# This is building the testing container
# docker build -t vanessa/snakemake:lammps .

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
        libfftw3-dev libfftw3-bin pdsh libfabric-dev libfabric1 \
        dnsutils telnet strace cmake git g++ openmpi-bin \
        openmpi-common wget curl unzip libopenmpi-dev \
        software-properties-common gpg-agent build-essential

RUN add-apt-repository ppa:deadsnakes/ppa && apt-get update && \
    apt install -y python3.12 python3.12-dev

RUN update-alternatives --install /usr/bin/python3 python /usr/bin/python3.12 1 && \
    update-alternatives --install /usr/bin/python python3 /usr/bin/python3.12 1

RUN wget https://bootstrap.pypa.io/get-pip.py && \
    python3 get-pip.py

RUN pip3 install -U git+https://github.com/snakemake/snakemake-interface-common@main && \
    pip3 install -U git+https://github.com/snakemake/snakemake-interface-executor-plugins && \
    pip3 install -U git+https://github.com/snakemake/snakemake-interface-storage-plugins@main && \
    pip3 install -U git+https://github.com/snakemake/snakemake-storage-plugin-s3@main && \
    pip3 install -U git+https://github.com/snakemake/snakemake-storage-plugin-gcs@main && \
    pip3 install -U git+https://github.com/snakemake/snakemake@main

# install laamps
WORKDIR /opt/
RUN git clone --depth 1 --branch stable_29Sep2021_update2 https://github.com/lammps/lammps.git /opt/lammps && \
    cd /opt/lammps && \
    mkdir build && \
    cd build && \
    . /etc/profile && \ 
    cmake ../cmake -DCMAKE_INSTALL_PREFIX:PATH=/usr -DPKG_REAXFF=yes -DBUILD_MPI=yes -DPKG_OPT=yes -D FFT=FFTW3 -DCMAKE_PREFIX_PATH=/usr/include/x86_64-linux-gnu/mpi -DCMAKE_PREFIX_PATH=/usr/lib/x86_64-linux-gnu && \
    make && \
    make install
    
WORKDIR /opt/lammps/examples/reaxff/HNS