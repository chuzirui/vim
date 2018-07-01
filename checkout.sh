#!/bin/sh
mkdir -p ~/.ssh
cp id_rsa* ~/.ssh
chmod 0400 ~/.ssh/id_rsa
cp .bashrc ~/
source .bashrc
git config --global user.email "chuzirui@gmail.com"
git config --global user.name "Leo Chu"


