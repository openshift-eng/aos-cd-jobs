This job invokes the [script to update the jenkins base RPM](../../hacks/update-jenkins/README.MD).

It needs the following parameters:

- Jenkins version. Version to upgrade to

- OCP branch. Used to determine the target dist-git branch

- plugin list, one plugin per line, in the form pluginname:version (see scripts for more details)

- email notification targets

- jenkins slave where builds happen. This has to have access to krb credentials to access dist-git/brew
