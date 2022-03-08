#!/bin/bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

cd $SCRIPT_DIR

set -ex

MY_ENV_PATH=./env/anica

echo "Setting up the virtual environment..."
python3 -m venv $MY_ENV_PATH
# virtualenv $MY_ENV_PATH

source $MY_ENV_PATH/bin/activate

echo "Installing requirements..."
pip install -r requirements.txt

echo "Installing AnICA..."
pip install -e .

# just for convenience
pip install ipython


