#!/usr/bin/env bash
apt update -y
apt install -y vim cscope xsel git-review exuberant-ctags
apt install -y python-pip autojump
pip install -y thefuck
apt install -y libssl-dev python-openssl silversearcher-ag
apt-get -y install build-essential cmake python-dev python3-dev
pip install flake8 tox
export EDITOR=vim
cp -r .vim/ ~/
cp .vimrc.python ~/.vimrc
#cp .bashrc ~/
 [ ! -d "$HOME/.vim/bundle"  ] && git clone https://github.com/VundleVim/Vundle.vim.git ~/.vim/bundle/Vundle.vim
vim +PluginInstall +qall
cd ~/.vim/bundle/YouCompleteMe
./install.py --clang-completer
git remote set-url origin ssh://git@github.com/chuzirui/vim.git
git config --global user.email "chuzirui@gmail.com"
git config --global user.name "Leo Chu"
sudo add-apt-repository ppa:hzwhuang/ss-qt5
sudo apt-get update
sudo apt-get install shadowsocks-qt5
