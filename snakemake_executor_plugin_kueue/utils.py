def write_file(content, filename, mode="w"):
    """
    Write content to file.
    """
    with open(filename, mode) as fd:
        fd.write(content)


def append_file(content, filename):
    """
    Append content to file.
    """
    return write_file(content, filename, "a")


def read_file(filename):
    """
    Read a file by filename.
    """
    with open(filename, "r") as fd:
        return fd.read()


def write_script(content, path, hashbang="#!/bin/bash"):
    """
    Return code to write a file
    """
    return f"""cat <<EOF > {path}
{hashbang}
{content}
EOF
"""
