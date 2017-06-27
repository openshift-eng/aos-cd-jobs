- yum install
  - go
  - docker
  - git
  - puddle
  - rhpkg  
  - brew
  - tito
  - rhtools  (required for sign_unsigned.py)
  - rh-signing-tools  (required for sign_unsigned.py)
  - npm (needed for origin-web-console asset compilation)
- Setup "jenkins" user
  - Create user
  - Ensure user has at least 100GB in home directory (Jenkins server will run as jenkins user and workspace will reside here).
  - Add `jenkins    ALL=(ALL)    NOPASSWD: ALL` to the bottom of /etc/sudoers (https://serverfault.com/questions/160581/how-to-setup-passwordless-sudo-on-linux)
  - Create "docker" group and add "jenkins" user to enable docker daemon operations without sudo.
- Configure git
  - `git config user.name "Jenkins CD Merge Bot"`
  - `git config user.email smunilla@redhat.com`  (or current build point-of-contact)
  - `git config push.default simple`
- Configure docker 
  - You should use a production configuration of devicemapper/thinpool for docker with at least 150GB of storage in the VG
  - Edit /etc/sysconfig/docker and set the following: `INSECURE_REGISTRY='--insecure-registry brew-pulp-docker01.web.prod.ext.phx2.redhat.com:8888 --insecure-registry rcm-img-docker01.build.eng.bos.redhat.com:5001 --insecure-registry registry.access.stage.redhat.com'`
- Configure tito
  - Populate ~/.titorc with `RHPKG_USER=ocp-build`
- In a temporary directory
  - git clone https://github.com/openshift/origin-web-console.git
  - cd origin-web-console
  - ./hack/install_deps.sh  (necessary for pre-processing origin-web-console files)
  - npm install -g grunt-cli bower
- Establish known hosts (and accept fingerprints):
  - ssh to github.com
  - ssh to rcm-guest.app.eng.bos.redhat.com
  - ssh to pkgs.devel.redhat.com
- Credentials
  - Copy /home/jenkins/.ssh/id_rsa from existing buildvm into place on new buildvm. This is necessary to ssh as ocp-build to rcm-guest. Ideally, this credential will be pulled into Jenkins credential store soon.

- Setup host as a Jenkins agent 
  - Copy /home/jenkins/swarm-client-2.0-jar-with-dependencies.jar off old buildvm and into place on new buildvm.
  - Populate /etc/systemd/system/swarm.service (ensure that -name parameter is unique and -labels are the desired ones):
```
[Unit]
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/usr/bin/nohup /usr/bin/java -Xmx2048m -jar /home/jenkins/swarm-client-2.0-jar-with-dependencies.jar -master https://atomic-e2e-jenkins.rhev-ci-vms.eng.rdu2.redhat.com/ -name buildvm-devops.usersys.redhat.com -executors 10 -labels "buildvm-devops" -fsroot /home/jenkins -mode exclusive -disableSslVerification -disableClientsUniqueId
Restart=on-failure
User=jenkins
Group=jenkins

[Install]
WantedBy=multi-user.target
```
 - Reload systemctl daemon (`sudo systemctl daemon-reload`)
  - Set swarm to autostart (`sudo systemctl enable swarm`)

- Create the following repos on buildvm
```
[root@buildvm-devops-new ~]# cat /etc/yum.repos.d/dockertested.repo 
[dockertested]
name=Latest tested version of Docker
baseurl=https://mirror.openshift.com/enterprise/rhel/dockertested/x86_64/os/
failovermethod=priority
enabled=0
priority=40
gpgcheck=0
sslverify=0
sslclientcert=/var/lib/yum/client-cert.pem
sslclientkey=/var/lib/yum/client-key.pem



[root@buildvm-devops-new ~]# cat /etc/yum.repos.d/rhel7next.repo 
[rhel7next]
name=Prerelease version of Enterprise Linux 7.x
baseurl=https://mirror.openshift.com/enterprise/rhel/rhel7next/os/
failovermethod=priority
enabled=0
priority=40
gpgcheck=0
sslverify=0
sslclientcert=/var/lib/yum/client-cert.pem
sslclientkey=/var/lib/yum/client-key.pem

[rhel7next-optional]
name=Prerelease version of Enterprise Linux 7.x
baseurl=https://mirror.openshift.com/enterprise/rhel/rhel7next/optional/
failovermethod=priority
enabled=0
priority=40
gpgcheck=0
sslverify=0
sslclientcert=/var/lib/yum/client-cert.pem
sslclientkey=/var/lib/yum/client-key.pem

[rhel7next-extras]
name=Prerelease version of Enterprise Linux 7.x
baseurl=https://mirror.openshift.com/enterprise/rhel/rhel7next/extras/
failovermethod=priority
enabled=0
priority=40
gpgcheck=0
sslverify=0
sslclientcert=/var/lib/yum/client-cert.pem
sslclientkey=/var/lib/yum/client-key.pem
```
