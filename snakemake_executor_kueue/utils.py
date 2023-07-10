
def write_file(content, filename):
    """
    Write content to file.
    """
    print(filename)
    with open(filename, 'w') as fd:
        fd.write(content)
