#!/bin/bash
echo "$(hostname -I | grep '[0-9]*\.[0-9]*\.[0-9]*\.[0-9]*' -o | head -1)  $(hostname)" >> /etc/hosts
echo "10.114.209.37   reg.yves.local " >> /etc/hosts
curl -s https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add -

cat <<EOF > /etc/apt/sources.list.d/kubernetes.list
deb http://apt.kubernetes.io/ kubernetes-xenial main
EOF

apt-get update

apt-get install -y docker.io
apt-get install -y kubelet kubeadm kubectl kubernetes-cni
cat <<EOF > /etc/docker/daemon.json
{
     "insecure-registries": ["reg.yves.local"]
}
EOF

service docker restart
systemctl enable docker.service
kubeadm init
sed -i 's/insecure-port=0/insecure-port=8080/1' /etc/kubernetes/manifests/kube-apiserver.yaml
sed -i "/insecure-port/a\    - --insecure-bind-address=0.0.0.0" /etc/kubernetes/manifests/kube-apiserver.yaml
cat <<EOF > /tmp/ncp.ini
[DEFAULT]
[coe]
cluster = $4
[k8s]
apiserver_host_ip = 127.0.0.1
apiserver_host_port = 8080
use_https = False
ingress_mode = nat
[nsx_v3]
nsx_api_user = $2
nsx_api_password = $3
nsx_api_managers = $1:443
insecure = True
subnet_prefix = 24
external_ip_pool_id = acfe5a81-29eb-4b4a-877b-cae2a6794027
default_external_ip = 10.114.209.193
EOF

