#!/bin/bash

MY_ENV_PATH=./env/devidisc

echo "Setting up the virtual environment..."
python3 -m venv $MY_ENV_PATH

source $MY_ENV_PATH/bin/activate

echo "Installing requirements..."
pip install -r requirements.txt


