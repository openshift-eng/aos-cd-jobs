# Jenkins Master Setup
If the build system is to run a Jenkins master (https://wiki.jenkins.io/display/JENKINS/Installing+Jenkins+on+Red+Hat+distributions):
  - sudo wget -O /etc/yum.repos.d/jenkins.repo http://pkg.jenkins-ci.org/redhat-stable/jenkins.repo
  - sudo rpm --import https://jenkins-ci.org/redhat/jenkins-ci.org.key
  - sudo yum install jenkins
  - firewall-cmd --permanent --add-port=8443/tcp
  - firewall-cmd --reload
  - create a certificate for the server: keytool -genkeypair -keysize 2048 -keyalg RSA -alias jenkins -keystore keystore (https://wiki.jenkins.io/display/JENKINS/Starting+and+Accessing+Jenkins)
  - configure /etc/sysconfig/jenkins
    - JENKINS_HTTPS_LISTEN_ADDRESS="0.0.0.0"
    - JENKINS_HTTPS_KEYSTORE_PASSWORD="...set during keystore creation..."
    - JENKINS_HTTPS_KEYSTORE="/home/jenkins/keystore"
    - JENKINS_HTTPS_PORT="8443"
    - JENKINS_PORT="-1"
    - JENKINS_JAVA_OPTIONS="-Djava.awt.headless=true -Djava.net.preferIPv4Stack=true -Djenkins.branch.WorkspaceLocatorImpl.PATH_MAX=0"
      - The PATH_MAX value ensures the branch plugin does not create extremely long paths which interefere with virtualenv
  - Create a client certificate and import it into Java keystore:
    - keytool -export -alias jenkins -file client.crt -keystore keystore   (https://www.sslshopper.com/article-most-common-java-keytool-keystore-commands.html )
    - keytool -import -trustcacerts -alias jenkins -file client.crt -keystore client.keystore
    - You will need to specify this keystore on the agents for the master (e.g. "-Djavax.net.ssl.trustStore=/home/jenkins/client.keystore").
  - sudo chkconfig jenkins on
  - sudo systemctl start jenkins
  - Setup smtp mail server in Jenkins configuration
  - Install plugins
    - UpdateSites Manager plugin
    - Common ones jenkins suggests on first login
    - SSH Agent Plugin
    - Role Based Authentication
    - Pipeline Utility Steps
    - Extra Columns Plugin (to disable projects)
    - Parameter Separator Plugin
    - ANSI Color Plugin
    - Install Red Hat CI messaging plugin: https://docs.engineering.redhat.com/display/CentralCI/Jenkins+CI+Plugin#JenkinsCIPlugin-InstallingtheCIPlugin  . Added update center manager plugin and then installed. For our old version of Jenkins, I actually had to download hpi from artifactory: http://artifactory.rhev-ci-vms.eng.rdu2.redhat.com:8081/artifactory/ci-ops-releases-local/com/redhat/jenkins/plugins/redhat-ci-plugin/ (grabbing 1.5.5 at the time of this writing). 

# Jenkins Agent Setup
- Copy slave.jar into place onto agent at /home/jenkins/slave.jar (e.g. wget --no-check-certificate https://buildvm.openshift.eng.bos.redhat.com:8443/jnlpJars/slave.jar )
- Use the Jenkins UI to add a new node. It will create a command line to execute and a secret. This should be used to populate /etc/systemd/system/jenkins-agent.service:

```
[Unit]
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/bin/java -Djavax.net.ssl.trustStore=/home/jenkins/client.keystore -jar /home/jenkins/slave.jar -jnlpUrl  https://..../slave-agent.jnlp -secret 25dd40...........04c1a6e
Restart=on-failure
User=jenkins
Group=jenkins

[Install]
WantedBy=multi-user.target
```
- chkconfig jenkins-agent on
- systemctl start jenkins-agent

# Core System Setup
- Ensure /tmp is a tmpfs mount
  - systemctl status tmp.mount
  - If service disabled:
    - systemctl enable tmp.mount
    - reboot
- Enable RPM repos:
  - Most packages will need this: https://gitlab.cee.redhat.com/platform-eng-core-services/internal-repos/raw/master/rhel/rhel-7.repo
  - For puddle, rhpkg, rhtools, rh-signing-tools: http://download.devel.redhat.com/rel-eng/RCMTOOLS/rcm-tools-rhel-7-server.repo
  - For tito and npm, install EPEL:
    - wget http://dl.fedoraproject.org/pub/epel/7/x86_64/e/epel-release-7-10.noarch.rpm
    - rpm -ivh epel-release-7-10.noarch.rpm
- yum install
  - go
  - atomic
  - docker
  - git
  - puddle
  - rhpkg
  - brew (yum install koji)
  - tito
  - rhtools  (required for sign_unsigned.py)
  - rh-signing-tools  (required for sign_unsigned.py)
  - npm (needed for origin-web-console asset compilation)
  - pip (`yum install python-pip`)
  - virtualenv (`pip install virtualenv`)
  - python-devel
- Install depdendencies for sprint_tools
  - Copy https://github.com/openshift/li/blob/master/misc/client-key.pem to /var/lib/yum/client-key.pem
  - Copy https://github.com/openshift/li/blob/master/misc/client-cert.pem to /var/lib/yum/client-cert.pem
  - yum install ruby
  - yum install gcc-c++ patch readline readline-devel zlib zlib-devel libyaml-devel libffi-devel openssl-devel make bzip2 autoconf automake libtool bison iconv-devel ruby-devel libxml2 libxml2-devel libxslt libxslt-devel
  - gem install bundler
  - yum install ImageMagick-devel ImageMagick
  - git clone https://github.com/openshift/sprint_tools.git
  - Run "bundler install" in sprint_tools clone
- Install oc client compatible with Ops registry (https://console.reg-aws.openshift.com/console/)
  - wget https://mirror.openshift.com/pub/openshift-v3/clients/3.6.170/linux/oc.tar.gz
  - extract 'oc' binary in /usr/bin
- Install an oc binary compatible with 3.7
  - https://mirror.openshift.com/pub/openshift-v3/clients/3.7.0-0.126.6/linux/oc.tar.gz
  - extract 'oc' binary to /usr/bin/oc-3.7   (used by sprint-control job)
- Mounts in fstab
  - ntap-bos-c01-eng01-nfs01a.storage.bos.redhat.com:/devops_engarchive2_nfs /mnt/engarchive2 nfs tcp,ro,nfsvers=3 0 0
  - ntap-bos-c01-eng01-nfs01b.storage.bos.redhat.com:/devops_engineering_nfs/devarchive/redhat /mnt/redhat nfs tcp,ro,nfsvers=3 0 0
- /mnt/brew should be a symlink to /mnt/redhat/brewroot
- Installing atomic scan dependency: atomic install registry.access.redhat.com/rhel7/openscap
- Enabling RPM signing
  - RPM signing is limited by hostname. Presently, only openshift-build-1.lab.eng.rdu.redhat.com as ocp-build kerberos id has this authority. The hostname is tied to the MAC of the server.
  - The system must be plugged into a lab Ethernet port. Port 16W306A was joined to the engineering network for this purpose.
- Setup "jenkins" user
  - Create user
    - If user home must be in anywhere non-default (such as on an NFS share) advanced steps will be required:
      - \# Assuming a mount at /mnt/nfs
      - mkdir /mnt/nfs/home
      - semanage fcontext -a -e /home /mnt/nfs/home/jenkins # Tell SELinux this path is allowed
      - restorecon /mnt/nfs/home
      - useradd -m -d /mnt/nfs/home/jenkins jenkins
  - Ensure user has at least 100GB in home directory (Jenkins server will run as jenkins user and workspace will reside here).
  - Add `jenkins    ALL=(ALL)    NOPASSWD: ALL` to the bottom of /etc/sudoers (https://serverfault.com/questions/160581/how-to-setup-passwordless-sudo-on-linux)
  - Create "docker" group and add "jenkins" user to enable docker daemon operations without sudo.
  - Create the following .ssh/config for the jenkins user
```
Host rcm-guest rcm-guest.app.eng.bos.redhat.com
    Hostname                   rcm-guest.app.eng.bos.redhat.com
    ForwardAgent               yes
    User                       ocp-build
```
  - Set ssh config permissions: `chmod 600 ~/.ssh/config`
- Configure git
  - `git config --global user.name "Jenkins CD Merge Bot"`
  - `git config --global user.email smunilla@redhat.com`  (or current build point-of-contact)
  - `git config --global push.default simple`
- Configure docker
  - You should use a production configuration of devicemapper/thinpool for docker with at least 150GB of storage in the VG
  - Edit /etc/sysconfig/docker and set the following: `INSECURE_REGISTRY='--insecure-registry brew-pulp-docker01.web.prod.ext.phx2.redhat.com:8888 --insecure-registry rcm-img-docker01.build.eng.bos.redhat.com:5001 --insecure-registry registry.access.stage.redhat.com'`
- Configure tito
  - Create /home/jenkins/workspace/tito_tmp if it does not exist
  - Populate ~/.titorc with:
    ```
    RHPKG_USER=ocp-build
    RPMBUILD_BASEDIR=/home/jenkins/workspace/tito_tmp
    ```
- oct dependencies
  - Copy /home/jenkins/.aws/credentials from existing buildvm to target (needed for oct & dockertested job).
  - Copy libra.pem (from shared-secrets repo) to /home/jenkins/.ssh/devenv.pem .
- In a temporary directory
  - git clone https://github.com/openshift/origin-web-console.git
  - cd origin-web-console
  - ./hack/install-deps.sh  (necessary for pre-processing origin-web-console files)
  - sudo npm install -g grunt-cli bower
- Establish known hosts (and accept fingerprints):
  - ssh to github.com
  - ssh to rcm-guest.app.eng.bos.redhat.com
  - ssh to pkgs.devel.redhat.com
- Credentials
  - Copy /home/jenkins/.ssh/id_rsa from existing buildvm into place on new buildvm. This is necessary to ssh as ocp-build to rcm-guest. Ideally, this credential will be pulled into Jenkins credential store soon.
  - chmod 600 /home/jenkins/.ssh/id_rsa
- Setup chronyd time sycnrhonization on the server/agent
  - Set the following servers in /etc/chrony.conf
    - server clock.util.phx2.redhat.com iburst
    - server clock02.util.phx2.redhat.com iburst
- Install Red Hat certificates (required for rhpkg to submit builds): https://mojo.redhat.com/groups/release-engineering/blog/2017/02/07/tmlcochs-rcm-knowledge-sharing-5-installation-of-red-hat-ca-certs
- Create the following repos on buildvm

```
# /etc/yum.repos.d/dockertested.repo
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



# /etc/yum.repos.d/rhel7next.repo
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
