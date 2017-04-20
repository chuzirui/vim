#!/bin/sh
ssh-keygen -t rsa
apt install -y cscope xsel 
pip install flake8 tox
git clone ssh://git@git.eng.vmware.com/nsx-ujo.git
cp -r .vim/ ~/
cp .vimrc ~/
cd nsx-ujo
find . -name "*.py" >> cscope.files
cscope -Rk

