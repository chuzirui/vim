#!/usr/bin/env bash

git config --global user.email "chuzirui@gmail.com"
git config --global user.name "leo chu"
apt install -y vim cscope xsel git-review exuberant-ctags
apt install -y python-pip autojump thefuck
apt-get -y install build-essential cmake python-dev python3-dev
pip install flake8 tox
export EDITOR=vim
cp -r .vim/ ~/
cp .vimrc.python ~/.vimrc
cp .bashrc ~/
 [ ! -d "$HOME/.vim/bundle"  ] && git clone https://github.com/VundleVim/Vundle.vim.git ~/.vim/bundle/Vundle.vim
vim +PluginInstall +qall
cd ~/.vim/bundle/YouCompleteMe
./install.py --clang-completer
