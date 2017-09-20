This job invokes the [scripts to update the jenkins plugin RPM](../../hacks/update-jenkins-plugins/README.MD).

It needs the following parameters:

- Jenkins version. Used by the scripts to determine dependencies, and also used to compute the name of the RPM (version X.Y -> jenkins-X-plugin)

- OCP release version. Used to determine the target dist-git branch

- plugin list, one plugin per line, in the form pluginname:version (see scripts for more details)

- email notification targets

- jenkins slave where builds happen. This has to have access to krb credentials to access dist-git/brew
