__version__ = "0.0.0"
AUTHOR = "Vanessa Sochat"
EMAIL = "vsoch@users.noreply.github.com"
NAME = "snakemake-executor-kueue"
PACKAGE_URL = "https://github.com/snakemake/snakemake-executor-kueue"
KEYWORDS = "snakemake, workflow, example, plugin"
DESCRIPTION = "An example external plugin to use with Snakemake"
LICENSE = "LICENSE"

################################################################################
# Global requirements

# Since we assume wanting Singularity and lmod, we require spython and Jinja2

INSTALL_REQUIRES = (
    ("oras", {"min_version": None}),
    ("snakemake", {"min_version": None}),
    ("Jinja2", {"min_version": None}),
    ("kubernetes", {"min_version": None}),
    ("portforward", {"min_version": None}),
    ("snakemake-executor-plugin-interface", {"min_version": None}),
)

TESTS_REQUIRES = (("pytest", {"min_version": "4.6.2"}),)

################################################################################
# Submodule Requirements (versions that include database)

INSTALL_REQUIRES_ALL = INSTALL_REQUIRES + TESTS_REQUIRES
