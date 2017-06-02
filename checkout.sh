#!/bin/sh
mkdir -p ~/.ssh
scp root@10.39.1.2:/root/.ssh/id_rsa ~/.ssh/
scp root@10.39.1.2:/root/.ssh/id_rsa.pub ~/.ssh/
apt install -y vim cscope xsel git-review exuberant-ctags
apt install -y autojump thefuck
pip install flake8 tox
git clone ssh://git@git.eng.vmware.com/nsx-ujo.git
git config --global user.email "chul@vmware.com"
git config --global user.name "Leo Chu"
export EDITOR=vim

cp -r .vim/ ~/
cp .vimrc ~/
cp .bashrc ~/
 [ ! -d "$HOME/.vim/bundle"  ] && git clone https://github.com/VundleVim/Vundle.vim.git ~/.vim/bundle/Vundle.vim
vim +PluginInstall +qall
apt-get -y install build-essential cmake python-dev python3-dev
cd ~/.vim/bundle/YouCompleteMe
./install.py --clang-completer

cd nsx-ujo
find . -name "*.py" >> cscope.files
find . -name "nsx" >> cscope.files
find "nsx_ujo/bin" -name "nsx" >> cscope.files
cscope -Rk

