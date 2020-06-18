#!/bin/sh

yum -y install rpm-build make gcc openssl-devel autoconf automake rpm-build redhat-rpm-config python-devel openssl-devel kernel-devel kernel-debug-devel libtool wget
yum -y install python-six checkpolicy selinux-policy-devel python-sphinx
mkdir -p ~/rpmbuild/SOURCES
cp openvswitch-$1.tar.gz ~/rpmbuild/SOURCES/
tar xfz openvswitch-2.9.0.tar.gz
sed 's/openvswitch-kmod, //g' openvswitch-$1/rhel/openvswitch.spec > openvswitch-$1/rhel/openvswitch_no_kmod.spec
rpmbuild -bb --nocheck ~/openvswitch-$1/rhel/openvswitch_no_kmod.spec
ls -l ~/rpmbuild/RPMS/x86_64/
yum -y localinstall ~/rpmbuild/RPMS/x86_64/openvswitch-$1-1.x86_64.rpm
systemctl start openvswitch.service
chkconfig openvswitch on
ovs-vsctl -V

ovs-vsctl show

