#!/usr/bin/env python3

import pathlib
import setuptools

HERE = pathlib.Path(__file__).parent
README = (HERE / "README.md").read_text()
LICENSE = (HERE / "LICENSE").read_text()

setuptools.setup(
    name="AnICA",
    version="0.1.0",
    description="Analyzing Inconsistencies of Code Analayzers",
    long_description=README,
    long_description_content_type="text/markdown",
    author="Fabian Ritter",
    author_email="fabian.ritter@cs.uni-saarland.de",
    license=LICENSE,
    packages=setuptools.find_packages(exclude=('test',)),
    install_requires=[
            "iwho",
            "pytest",
            "graphviz",
            "editdistance",
            "pandas",
            "seaborn",
            "python-sat",
        ],
    scripts=["tool/anica-discover", "tool/anica-generalize"],
    python_requires=">=3"
)
