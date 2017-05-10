#!/bin/sh
ssh-keygen -t rsa
apt install -y vim cscope xsel 
declare -x EDITOR='vim'
pip install flake8 tox
git clone ssh://git@git.eng.vmware.com/nsx-ujo.git
git config --global user.email "chul@vmware.com"
git config --global user.name "Leo"

cp -r .vim/ ~/
cp .vimrc ~/
 [ ! -d "$HOME/.vim/bundle"  ] && git clone https://github.com/VundleVim/Vundle.vim.git ~/.vim/bundle/Vundle.vim
cd nsx-ujo
find . -name "*.py" >> cscope.files
cscope -Rk

