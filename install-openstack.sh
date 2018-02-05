#!/bin/bash
yum install -y ntp openssh-server wget	
wget -O /etc/yum.repos.d/CentOS-Base.repo http://mirrors.aliyun.com/repo/Centos-7.repo
yum -y update
yum install -y epel-release centos-release-openstack-pike vim git 
yum update -y
yum install -y openstack-packstack tmux
systemctl disable NetworkManager.service
systemctl stop NetworkManager.service
chkconfig network
sudo systemctl restart network
packstack --allinone --provision-demo=n --os-neutron-ovs-bridge-mappings=extnet:br-ex --os-neutron-ovs-bridge-interfaces=br-ex:`ip link | egrep -o '\w{2,10}[0-9]:' | sed -e 's/://g'` --os-neutron-ml2-type-drivers=vxlan,flat,vlan --os-neutron-ml2-flat-networks=extnet  --os-neutron-lbaas-install=y --os-heat-install=y --os-cinder-install=n
