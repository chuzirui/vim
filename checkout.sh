#!/bin/sh
ssh-keygen -t rsa
apt install -y vim cscope xsel 
export EDITOR=vim
pip install flake8 tox
git clone ssh://git@git.eng.vmware.com/nsx-ujo.git
git config --global user.email "chul@vmware.com"
git config --global user.name "Leo"
export EDITOR=vim

cp -r .vim/ ~/
cp .vimrc ~/
 [ ! -d "$HOME/.vim/bundle"  ] && git clone https://github.com/VundleVim/Vundle.vim.git ~/.vim/bundle/Vundle.vim
 vim +PluginInstall +qall
cd nsx-ujo
find . -name "*.py" >> cscope.files
cscope -Rk

