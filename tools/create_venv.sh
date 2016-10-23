#!/usr/bin/env bash

echo "Removing any old artefacts"
rm -rf dev_venv

echo "Creating new virtual environment"
python3.5 -m venv dev_venv

echo "Entering new virtual environment"
source dev_venv/bin/activate

echo "Upgrading pip"
pip install pip --upgrade

echo "Installing dependencies"
pip install -r ../requirements.dev.txt

echo "Exiting new virtual environment"
deactivate
