These instructions assume we are moving from release X.A to X.B and that origin#master contains X.A's deisred content.

- Have RCM create a new "Release" in the Errata Tool so that Advisories can be created for it. 

- Have RCM start creating new tags for X.B and new dist-git branches for X.B

- Have RCM create product listings for X.B from X.A. Product Listings are apparently "just a for loop" on RCM's end. It might be possible to get this automated. Though there might be bookkeeping steps as well.

- origin will create a new branch release-X.A and begin including changes for X.B in origin#master

- Create a new branch ose#enterprise-X.A from ose#master

- Create a new branch openshift-ansible#release-X.A from openshift-ansible#master

- Create a new branch in openshift/jenkins: openshift-X.B

- In ose#master, set origin.spec "Version: X.B.0" and "Release: "0.0.0%{?dist}"

- In openshift-anisble#master spec file specify version X.B.0 and Release "0.0.0%{?dist}"

- In ose#enterprise-X.A, make sure the release is to to "1%{?dist}" (unless it has already been changed to a non 0. value)

- Create a new origin-web-console#enterprise-X.B from origin-web-console#master. At this point, the origin-web-console team will start merging X.A changes into origin-web-console#X.A  and changes for X.B into origin-web-console#master .

- Add a X.B .tito/releasers.conf to ose#master and openshift-ansible#master

- In aos-cd-jobs:build-scripts/puddle-conf, create new puddle configuration files for X.B:
  - atomic_openshift-X.B.conf   (you can copy the content of the X.A file, but several changes are required inside)
  - errata-puddle-X.B.conf
  - errata-puddle-X.B-signed.conf
  
- In aos-cd-jobs
  - Change build/ocp Jenkinsfile:
    - Add X.B as a choice in the build options
  - Change build/ose Jenkinsfile:
    - OSE_MASTER=X.B
  - Change ose_images.sh
    - MASTER_RELEASE=X.B
    - Add 3.8 to version_trim_list
    - Assess whether anything in base group needs to change for X.B

- Copy dist-git data from last version branches into new version branches using oit distgits:copy

- In enterprise-images github repo:
  - Copy groups/openshift-X.A to groups/openshift-X.B
  - Edit group.yml' name to "openshift-X.B"
  - Change group.yml's branch and repos from X.A to X.B
  - *Search the new openshift-X.B directory for X.A . At the moment, there is one hard coded reference in the jenkins image base to help migrate away from ose_image.sh.*
  
- Create a new build/ose-X.B job to enable single click invocation of a build/ocp for the version
