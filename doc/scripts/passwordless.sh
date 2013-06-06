#!/usr/bin/env bash
if [ ! $#  -eq 1 ]; then
	echo "Virtual Machine ssh port is needed (Default 2222). Type 2222"
	exit
fi

PORT=$1

if [ ! -f ~/.ssh/id_rsa.pub ]; then
	echo "Generating local ssh keys"
	ssh-keygen -t rsa -b 2048	
fi

#copying identity to authorized keys
echo "Copying local identity to authorized keys"
cat ~/.ssh/id_rsa.pub | ssh -p $PORT vagrant@localhost "cat >> ~/.ssh/authorized_keys"

#copying deploy keys for GoChatServer project
echo "Copying deploy keys of GoChatServer"
scp -P$PORT ~/.ssh/id_rsa* vagrant@localhost:~/.ssh
ssh -p$PORT vagrant@localhost "chmod 0600 .ssh/id_rsa*"

#config ssh to authorized key
ssh -p$PORT vagrant@localhost "echo \"StrictHostKeyChecking no\" >> ~/.ssh/config"

#copying config files
echo "Applying config changes"

scp -P$PORT conf_files/rc.local vagrant@localhost:/tmp
ssh -p$PORT vagrant@localhost "sudo cp -f /tmp/rc.local /etc/rc.local"

scp -P$PORT conf_files/hosts vagrant@localhost:/tmp
ssh -p$PORT vagrant@localhost "sudo cp -f /tmp/hosts /etc/hosts"

scp -P$PORT conf_files/limits.conf vagrant@localhost:/tmp
ssh -p$PORT vagrant@localhost "sudo cp -f /tmp/limits.conf /etc/security"

scp -P$PORT conf_files/30-stress-tests-tcp-fin-timeout.conf vagrant@localhost:/tmp
ssh -p$PORT vagrant@localhost "sudo cp -f /tmp/30-stress-tests-tcp-fin-timeout.conf /etc/sysctl.d"

ssh -p$PORT vagrant@localhost "sudo reboot"
sleep 5

