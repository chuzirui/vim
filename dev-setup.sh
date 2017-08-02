#!/usr/bin/env bash
apt update -y
apt install -y vim cscope xsel git-review exuberant-ctags | dnf install -y vim cscope xsel git-review ctags 
apt install -y python-pip autojump thefuck | dnf -y install python-pip autojump thefuck
apt install -y libssl-dev python-openssl | dnf -y install  openssl-devel
apt-get -y install build-essential cmake python-dev python3-dev
dnf -y install cmake python-devel python3-devel 
pip install flake8 tox
export EDITOR=vim
cp -r .vim/ ~/
cp .vimrc.python ~/.vimrc
#cp .bashrc ~/
 [ ! -d "$HOME/.vim/bundle"  ] && git clone https://github.com/VundleVim/Vundle.vim.git ~/.vim/bundle/Vundle.vim
vim +PluginInstall +qall
cd ~/.vim/bundle/YouCompleteMe
yum -y install gcc-c++
./install.py --clang-completer
