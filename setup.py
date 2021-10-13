#!/usr/bin/env python3

import pathlib
import setuptools

HERE = pathlib.Path(__file__).parent
README = (HERE / "README.md").read_text()

setuptools.setup(
    name="AnICA",
    version="0.0.1",
    description="Analyzing Inconsistencies of Code Analayzers",
    long_description=README,
    long_description_content_type="text/markdown",
    author="Fabian Ritter",
    author_email="fabian.ritter@cs.uni-saarland.de",
    # license="MIT",
    # classifiers=[
    #     "License :: OSI Approved :: MIT License",
    #     "Programming Language :: Python"
    # ],
    packages=setuptools.find_packages(),
    python_requires=">=3"
)
