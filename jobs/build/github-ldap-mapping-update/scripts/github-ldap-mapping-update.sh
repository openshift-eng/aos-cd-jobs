#!/usr/bin/env bash

set -x

ldapsearch -LLL -x -h ldap.corp.redhat.com -b ou=users,dc=redhat,dc=com '(rhatSocialURL=GitHub*)' rhatSocialURL uid 2>&1 | tee /tmp/out
ldap-users-from-github-owners-files --ldap-file /tmp/out --mapping-file /tmp/mapping.yaml
export KUBECONFIG=/home/jenkins/kubeconfigs/sa.github-ldap-mapping-updater.app.ci.config
oc -n ci create configmap github-ldap-mapping --from-file=mapping.yaml=/tmp/mapping.yaml --dry-run=client -o yaml | oc -n ci apply -f -
