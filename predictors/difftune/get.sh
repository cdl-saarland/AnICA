#!/bin/bash

set -ex

git clone https://github.com/ithemal/DiffTune.git repo

cd repo

# Make sure that we have a clang available, since gcc didn't like to build it.
clang --version
clang++ --version

# This things were necessary to make the parametric llvm-mca version buildable
export CC=clang
export CXX=clang++
git apply ../difftune.patch

# download the pre-trained haswell parameters from their artifact
./download.sh

# build the modified llvm-mca (version 8.*). This can take a few minutes
cd llvm-mca-parametric
./build.sh

