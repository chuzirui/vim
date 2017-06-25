#!/bin/bash
echo "$(hostname -I | grep '[0-9]*\.[0-9]*\.[0-9]*\.[0-9]*' -o | head -1)  $(hostname)" >> /etc/hosts
echo "10.114.209.37   reg.yves.local " >> /etc/hosts
apt-get update -y

apt-get install -y curl
curl -s https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add -

cat <<EOF > /etc/apt/sources.list.d/kubernetes.list
deb http://apt.kubernetes.io/ kubernetes-xenial main
EOF

apt-get install -y docker.io docker-ce 
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
sed -i 's/insecure-port=0/insecure-port=8080/1' /etc/kubernetes/manifests/kube-apiserver.yaml

sed -i "/insecure-port/a\    - --insecure-bind-address=0.0.0.0" /etc/kubernetes/manifests/kube-apiserver.yaml
read -e -p 'Enter Your NSX IP:'  IP
read -e -p 'Enter Your NSX account:' -i 'admin' USER
read -e -p 'Enter Your NSX pwd:' -i 'Admin!23Admin' PWD
read -e -p 'Enter Your cluster name:'  CLUSTER
read -e -p 'Enter Your overlay interface:'  -i 'eth1' ETH

cat <<EOF > /tmp/ncp.ini
[DEFAULT]
[coe]
cluster = $CLUSTER
[k8s]
apiserver_host_ip = 127.0.0.1
apiserver_host_port = 8080
use_https = False
ingress_mode = nat
[nsx_v3]
nsx_api_user = $USER
nsx_api_password = $PWD
nsx_api_managers = $IP:443
insecure = True
subnet_prefix = 24
external_ip_pool_id = acfe5a81-29eb-4b4a-877b-cae2a6794027
default_external_ip = 10.114.209.193
EOF
mkdir -p /etc/nsx-ujo
cp -r /tmp/ncp.ini /etc/nsx-ujo
ovs-vsctl add-br br-int
ovs-vsctl set-fail-mode br-int standalone
ovs-vsctl add-port br-int $ETH
ovs-vsctl set Interface $ETH ofport=1
ln -s /usr/local/bin/nsx_cni.py /opt/cni/bin/nsx_cni
mkdir -p /etc/cni/net.d
cat <<EOF > /etc/cni/net.d/10-net.conf
{
    "name": "net",
        "type": "nsx_cni",
        "bridge": "br-int",
        "isGateway": true,
        "ipMasq": false,
        "ipam": {}
}
EOF
