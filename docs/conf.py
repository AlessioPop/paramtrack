# Sphinx configuration, styled after the orbitize documentation.

import os
import sys
from importlib.metadata import version as package_version

sys.path.insert(0, os.path.abspath("../src"))  # location of paramtrack with docstrings

extensions = [
    "sphinx_rtd_theme",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",  # renders the NumPy-style docstrings
    "sphinx.ext.viewcode",
]

source_suffix = ".rst"
master_doc = "index"

project = "paramtrack"
copyright = "2026, Alessio Popovic"
author = "Alessio Popovic"
version = release = package_version("paramtrack")

exclude_patterns = ["_build"]
pygments_style = "sphinx"

html_theme = "sphinx_rtd_theme"
htmlhelp_basename = "paramtrackdoc"
