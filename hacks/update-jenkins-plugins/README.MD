At the time of this writing (OCP 3.7), we ship a jenkins-2 docker image for OpenShift. A number of plugins
are baked into this image.

All of these plugins are built into a single RPM from a dist-git repo: jenkins-2-plugins. For future versions of
Jenkins, may have a "jenkins-3-plugins" and so on. In order to populate the plugins into dist-git:

1. Create a list of plugins and the desired version (see plugins.txt as an example). The devex team can create 
this list by downloading the desired plugins from a running version of Jenkins/centos.

2. Run collection-jenkins-plugins.sh. It processes the input file and downloads the specified version of plugins. Each plugin
contains a manifest that specifies what version of Jenkins it requires and what other plugins
it depends on. The script proceeds as follows:
  1. Downloads all plugins listed in the input file. For each plugin:
    a. Ensures that it does not require a version of Jenkins > the version specified on the command line.
  2. For each dependency listed by the plugins from (1)
    a. Skips it if it has already been downloaded (e.g. by (1))
    b. Download the latest version of the plugin (Jenkins does not care about the version dependencies specified in by the dependent plugin).
    c. Ensures that it does not require a version of Jenkins > the version specified on the command line.
    d. Adds to the list of dependencies if the plugin has any.

If you hit a plugin that requests a version of Jenkins greater than will ship with jenkins-2,
you can do one of two things:
1. Update the input file and pin an older version of the plugin.
2. Test the plugin with the older version of Jenkins. If it works, specify the "jenkins-version-override" attribute in the file entry.

In the end, you will have a collection of hpi files in working/hpis/*.hpi which need to be tested with the target Jenkins version.

Once you are happy with your collection of hpi files, use this directory as input to update-dist-git.sh. This process will
update the jenkins-2-plugin dist-git repo with all of the HPIs that have been retrieved. 


Requirements
------
- brew and rhpkg must be installed and working.
- You must have a kerberos ticket with access to update the dist-git repos (e.g. ocp-build).