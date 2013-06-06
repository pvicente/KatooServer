# KatooServer setup

# Introduction

KatooServer has been designed to support background tasks of [KatooIOS](https://bitbucket.org/gearsofdev/katooios) clients, storing
their messages to be retrieved in a near future and sending [push notifications](http://developer.apple.com/library/mac/#documentation/NetworkingInternet/Conceptual/RemoteNotificationsPG/Introduction/Introduction.html#//apple_ref/doc/uid/TP40008194-CH1-SW1).

It has been developed in Python 2.7 running in [Heroku](http://www.heroku.com/) with python 2.7.4. 

As backend message broker we are using [Redis](http://redis.io/) 2.4.15 and to permanent storage [MongoDB](http://www.mongodb.org/) 2.0.8

# Detailed documentation

There are more technical information about the project in the oficial [wiki](https://bitbucket.org/gearsofdev/katooserver/wiki/Home).

# Installation

 1. Clone the repo:

    ```git clone --recursive https://gearsofdev@bitbucket.org/gearsofdev/katooserver.git```

 2. Install [virtualbox](https://www.virtualbox.org/wiki/Downloads)

 3. Install [vagrant](http://downloads.vagrantup.com/)

 4. Install [heroku toolbet to deploy on Heroku](https://toolbelt.heroku.com/)

# Developing for KatooServer

To develop for KatooServer you will need to test in a controlled environment.

You can develop your code in your local machine with eclipse and the virtualenv installed **Generating a virtualenv** and
test it in the virtual machine (see **Working with virtual machine**).

If you prefer you can install all packages in your local machine but it is not advisable (see **Install and run redis on your local machine**)

## Working with the virtual machine

To test your code on a similar platform like **Heroku cedar stack** you will need to import the virtual machine
with [vagrant](http://downloads.vagrantup.com/) on [virtualbox](https://www.virtualbox.org/wiki/Downloads)

### Importing a standard virtual machine

In the root directory of KatooServer project type:

```vagrant up```

It will import the virtual machine from internet (600 MB aprox) and will take a while ...

When it finishes a new virtual machine will be added to your Virtualbox catalog. It will have forwarded ports
from local to virtual machine:

* **TCP 50000 to 5000** (on virtual machine). Application webserver port
* **TCP 6379 to 6379** (on virtual machine). Redis port

### Configuring the virtual machine for passwordless

Type

```cd doc/scripts```

```./passwordless.sh 2222```

( **Password**: vagrant)

Now you can access to your virtual machine with ```vagrant ssh``` in the root directory or
```ssh -p 2222 vagrant@localhost``` in any location

### Common actions with the virtual machine

While you ar working you could need halt, reboot or resume your virtual machine:

```vagrant [halt] [reboot] [resume]```


When you don't need the virtual machine:

```vagrant destroy```


### Updating virtual machine

It will be mandatory to remove cached box file **katoo-tsung-mongodb-redis-virtualmachine**

```vagrant box remove katoo-tsung-mongodb-redis-virtualmachine``` 

### Configuring automatic deploys

```git remote add test ssh://vagrant@localhost:2222/home/vagrant/test```

To test automatic deploy type:

```git push test HEAD:master```

### Testing with the virtual machine

You can test with the virtual machine with the automatic deploy feature. (see **Configuring automatic deploys**)

To deploy on your virtual machine type:

```git push test HEAD:master```

and follow the instructions.

###Configuring a performance test environment
In **doc/tests/machines** folder you have an example of virtual machines to import as a server and client.

It has been configured in the following way:

* **server**: 4 cores, 4096 MB, Hostname=server, 2 ethernet interfaces (eth0 NAT, eth1 bridged with virtual ip 11.0.0.1/8) 
* **clientX**: 2 cores, 2048 MB, Hostname=clientX (X can be 1-9), 2 ethernet interfaces (eth0 NAT, eth1 bridged with virtual ips 11.0.X.1-255/8

Virtual ips are not configured by default on booting. To configure it type:

```sudo /etc/init.d/rc.local start```

This structure can be used to launch performance tests with **tsung**.

## Generating a virtualenv

The application can run in Linux and MacOSX operating systems. For Linux we are using the same version than Heroku cedar stack  (Ubuntu 10.04 LTS x86_64), but any version is supported.
For each operating system it is necessary to make your [virtualenv](http://www.virtualenv.org/en/latest/index.html). Also is mandatory to have some compiler installed (gcc on Linux platforms, llvm on MacOSx)

To create your virtualenv you need to do the following steps:
  1. If you don't have virtualenv installed in your machine install it:

     ```sudo easy_install pip```
     
     ```sudo pip install virtualenv```

  2. In the root directory of KatooServer type:

     ```virtualenv --distribute venv```

  4. Enable your virtualenv:

     ```source venv/bin/activate```

  5. Install required libraries:

     ```pip install -r requirements.txt```

  6. Make it relocatable like on Heroku Platform:

     ```virtualenv --relocatable venv```

### Configuring your local app
By default ```foreman start```will run applications specified in Procfile.

Configuration changes can be applied defining ENV variables.
When you run an application with **foreman** this variables can be defined in **.env** file (on root directory).

Current ENV variables for configuration:

* **PORT**: web service port (default 5000)
* **REDISCLOUD_URL**:  redis url connection (default redis://localhost:6379)
* **MONGOLAB_URI**: mongo url connection (default mongodb://localhost:27017)
