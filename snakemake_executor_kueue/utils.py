def write_file(content, filename):
    """
    Write content to file.
    """
    print(filename)
    with open(filename, "w") as fd:
        fd.write(content)


def read_file(filename):
    """
    Read a file by filename.
    """
    with open(filename, "r") as fd:
        return fd.read()
