#!/usr/bin/env bash

apt install -y vim cscope xsel git-review exuberant-ctags
apt install -y autojump thefuck
pip install flake8 tox
export EDITOR=vim
cp -r .vim/ ~/
cp .vimrc.python ~/.vimrc
cp .bashrc ~/
 [ ! -d "$HOME/.vim/bundle"  ] && git clone https://github.com/VundleVim/Vundle.vim.git ~/.vim/bundle/Vundle.vim
vim +PluginInstall +qall
apt-get -y install build-essential cmake python-dev python3-dev
cd ~/.vim/bundle/YouCompleteMe
./install.py --clang-completer
