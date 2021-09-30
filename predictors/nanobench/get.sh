#!/bin/bash

set -ex

echo Make sure that you have installed msr-tools!

git clone https://github.com/andreas-abel/nanoBench.git repo

cd repo
make user

./setup.sh

