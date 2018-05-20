#!/usr/bin/env bash
sudo apt update -y
sudo apt install -y vim cscope xsel git-review exuberant-ctags
sudo apt install -y python-pip autojump software-properties-common
sudo pip install thefuck
sudo apt install -y libssl-dev python-openssl silversearcher-ag curl
sudo apt-get -y install build-essential cmake python-dev python3-dev
sudo dnf -y install cmake python-devel python3-devel
sudo pip install flake8 tox
export EDITOR=vim
cp -r .vim/ ~/
cp .vimrc.python ~/.vimrc
#cp .bashrc ~/
 [ ! -d "$HOME/.vim/bundle"  ] && git clone https://github.com/VundleVim/Vundle.vim.git ~/.vim/bundle/Vundle.vim
vim +PluginInstall +qall
git remote set-url origin ssh://git@github.com/chuzirui/vim.git
curl -o- -L https://raw.githubusercontent.com/TakeshiTseng/vim-language-p4/master/install.sh | bash
git config --global user.email "chuzirui@gmail.com"
git config --global user.name "Leo Chu"
sudo add-apt-repository -y ppa:hzwhuang/ss-qt5
sudo apt-get -y  update
sudo apt-get -y  install shadowsocks-qt5
