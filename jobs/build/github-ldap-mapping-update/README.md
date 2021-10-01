# github-ldap-mapping-update

github-ldap-mapping-update extracts the mapping `m(github_login)=kerberos_id` from Red Hat LDAP server and exports it to a configMap on `app.ci`.

## Dependencies:

- `oc` and `ldapsearch` are available already on the host.
- `ldap-users-from-github-owners-files`: a [CI tool](https://github.com/openshift/ci-tools/tree/master/cmd/ldap-users-from-github-owners-files) that generates the mapping file.

    ```console
    $ oc image extract registry.ci.openshift.org/ci/ldap-users-from-github-owners-files:latest --path /usr/bin/ldap-users-from-github-owners-files:.
    ```
- `sa.github-ldap-mapping-updater.app.ci.config`: A [service account](https://github.com/openshift/release/blob/9b99d73667b1fdcb300bcd641e6de11e665b5a09/clusters/app.ci/assets/admin_github-ldap-mapping-updater_rbac.yaml#L6-L7)'s `kubeconfig` file to update the configMap on `app.ci`.

    ```console
    $ context=app.ci
    $ sa=github-ldap-mapping-updater
    $ config="sa.${sa}.${context}.config"
    $ oc --context "${context}" sa create-kubeconfig -n ci "${sa}" > "${config}"
    $ sed -i "s/${sa}/${context}/g" "${config}"
    ```

