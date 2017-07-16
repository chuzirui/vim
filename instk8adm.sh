#!/bin/bash
echo "$(hostname -I | grep '[0-9]*\.[0-9]*\.[0-9]*\.[0-9]*' -o | head -1)  $(hostname)" >> /etc/hosts
echo "10.114.209.37   reg.yves.local " >> /etc/hosts
apt-get update -y

apt-get install -y curl
curl -s https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add -

cat <<EOF > /etc/apt/sources.list.d/kubernetes.list
deb http://apt.kubernetes.io/ kubernetes-xenial main
EOF

apt-get update -y
apt-get install -y docker.io
apt-get install -y kubelet kubeadm kubectl kubernetes-cni
apt-get install -f -y
cat <<EOF > /etc/docker/daemon.json
{
    "insecure-registries": ["reg.yves.local"]
}
EOF
service docker restart
systemctl enable docker.service
kubeadm init
sudo cp /etc/kubernetes/admin.conf $HOME/
sudo chown $(id -u):$(id -g) $HOME/admin.conf
export KUBECONFIG=$HOME/admin.conf
secret=`kubectl get serviceaccount default -o yaml | grep -A1 secrets |  tail -n1 | awk {'print $3'}`
kubectl get secret $secret -o yaml | grep "token:" | awk {'print $2'} |  base64 -d > /etc/nsx-ujo/default_token
kubectl taint nodes --all node-role.kubernetes.io/master-

