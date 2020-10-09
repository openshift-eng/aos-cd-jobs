Creates a directory with RPMs satisfying rhel-7 worker nodes dependencies 
for a given 4.x release: https://issues.redhat.com/browse/ART-1188

On buildvm (adjust 4.7 to reflect current release):

`$ ./collect-deps.sh 4.7`

This will create a directory `4.7-beta` in the current directory 
 
`$ scp -r 4.7-beta/ use-mirror-upload:/srv/pub/openshift-v4/dependencies/rpms/4.7-beta`

This will populate the files on the mirror.

`$ ssh use-mirror-upload`
```
use-mirror-upload$ cd /srv/pub/openshift-v4/dependencies/rpms/4.7-beta
use-mirror-upload$ createrepo --database `pwd`
use-mirror-upload$ /usr/local/bin/push.pub.sh openshift-v4/dependencies/rpms/4.7-beta -v
```
