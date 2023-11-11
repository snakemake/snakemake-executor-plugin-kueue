#!/bin/bash

echo "Expecting: <pull-from> <push-to>"
echo "Full provided set of arguments are $@"

# The command is the remainder of the script $@
pushto="${1}"
shift

# We will get an unknown number of inputs
pullfrom="${1}"
shift

echo "Artifact URI to push to is: ${pushto}"
echo "Artifact URI to pull from is: ${pullfrom}"

# Create inputs artifact directory
mkdir -p /mnt/oras/inputs /mnt/oras/outputs

mkdir -p /tmp/oras-pull-cache/
while [ "${pullfrom}" != "NA" ]; do
    echo "Artifact URI to retrieve is: ${pullfrom}"
    cd /mnt/oras/inputs
    # This will always be a directory name (but .tar.gz)
    oras pull ${pullfrom} --plain-http --output /tmp/oras-pull-cache
    archive=$(ls /tmp/oras-pull-cache/*)
    mv ${archive} ${archive}.tar.gz
    # Extract to /mnt/oras/inputs
    tar -xzvf ${archive}.tar.gz
    echo "Pulled ${pullfrom} to /mnt/oras/inputs"
    rm ${archive}.tar.gz
    pullfrom="${1}"
    shift
    if [[ "${pullfrom}" == "" ]]; then
        echo "Hit last artifact to pull."
        pullfrom="NA"
    fi
    ls -l
done

# indicate to application we are ready to run!
touch /mnt/oras/oras-operator-init.txt

# Wait for the application to finish, indicated by the file indicator we wait for
wget -q https://github.com/converged-computing/goshare/releases/download/2023-09-06/wait-fs
chmod +x ./wait-fs
mv ./wait-fs /usr/bin/goshare-wait-fs

# Wait for the indicator from the sidecar that artifact is ready
goshare-wait-fs -p /mnt/oras/oras-operator-done.txt

# If we don't have a place to push, we are done
if [[ "${pushto}" == "NA" ]]; then
    exit 0
fi

# Push the contents to the location
cd /mnt/oras/outputs
oras push ${pushto} --plain-http .