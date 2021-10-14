#!/bin/bash

INVENV=$(python -c 'import sys ; print( 0 if sys.prefix == sys.base_prefix else 1 )')

if [ "$INVENV" -ne 1 ]; then
    echo "Not running in a virtual environment!"
    exit 1
fi

set -ex

git clone https://github.com/RRZE-HPC/OSACA.git repo

pip install networkx ruamel.yaml

cd repo
git checkout v0.4.6

./setup.py install

