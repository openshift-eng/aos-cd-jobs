These instructoins assume we are moving from release X.A to X.B and that origin#master contains X.A's deisred content.

- Have RCM start creating new tags for 3.7 and new dist-git branches for 3.7

- origin will create a new branch release-X.A and begin including changes for X.B in origin#master

- Create a new branch ose#enterprise-X.A from ose#master

- Create a new branch openshift-ansible#release-X.A from openshift-ansible#master

- In ose#master, set origin.spec "Version: X.B" and "Release: 0"

- Create a new origin-web-console#enterprise-X.B from origin-web-console#master. At this point, the origin-web-console team will start merging X.A changes into origin-web-console#X.A  and changes for X.B into origin-web-console#master .

- Add a X.B .tito/releasers.conf to ose#master and openshift-ansible#master

TODO: describe RCM process. Product listings?

TODO: process to populate new dist-git branches with content from old?

TODO: RCM process for setting up tags?
