#!/bin/sh
mkdir -p ~/.ssh
cp id_rsa* ~/.ssh
chmod 0400 ~/.ssh/id_rsa
cp .bashrc ~/
source .bashrc
git clone ssh://git@git.eng.vmware.com/nsx-ujo.git
git config --global user.email "chul@vmware.com"
git config --global user.name "Leo Chu"

cd nsx-ujo
pip install --upgrade pip
pip install .
find . -name "*.py" >> cscope.files
find . -name "nsx" >> cscope.files
cscope -Rk

