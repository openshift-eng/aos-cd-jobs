LEGACY METHOD. This README is left for reference only. This legacy method used a dist-git repo for each and
every Jenkins plugin we wanted to include for the openshift-jenkins image. Since the number of Jenkins plugins 
continues to grow, a new method has been implemented. The new method has a single repo that is populated with
all desired Jenkins plugins.


----------------------------------------------------------------------------------------------------------------

At the time of this writing (OCP 3.6), we ship jenkins-1 and jenkins-2 docker images for OpenShift. 
A number of plugins are baked into these images.

Each of these plugins is built into an independent RPM from a dist-git repository. When the jenkins-1
or jenkins-2 docker images build, these RPMs are installed via YUM.

Now here is where it gets fun - figuring out what plugins are required, what plugins those plugins
are dependent on, and finally, what version of Jenkins ALL of those plugins are compatible with.

So... the devex team gets a set of plugin versions they want to use and provides a file detailing those
plugin versions (see plugins.txt example in this directory). Each line of the file uses the format:
`plugin:version;attribute1;attribute2`

The devex team can create this list by downloading the desired plugins from a running version of
Jenkins/centos.

collect-jenkins-plugins.sh processes the input file and downloads the specified version of plugins. Each plugin
contains a manifest that specifies what version of Jenkins it requires and what other plugins
it depends on. The script proceeds as follows:
1. Downloads all plugins listed in the input file. For each plugin:
  a. Ensures that it does not require a version of Jenkins > the version specified on the command line.
2. For each dependency listed by the plugins from (1)
  a. Skips it if it has already been downloaded (e.g. by (1))
  b. Download the latest version of the plugin (Jenkins does not care about the version dependencies specified in by the dependent plugin).
  c. Ensures that it does not require a version of Jenkins > the version specified on the command line.
  d. Adds to the list of dependencies if the plugin has any.

If you hit a plugin that requests a version of Jenkins greater than will ship with jenkins-1 or jenkins-2,
you can do one of two things:
1. Update the input file and pin an older version of the plugin.
2. Test the plugin with the older version of Jenkins. If it works, specify the "jenkins-version-override" attribute in the file entry.

In the end, you will have a collection of hpi files in working/hpis/*.hpi which need to be tested with both Jenkins images.

Once you are happy with your collection of hpi files, use this directory as input to update-dist-git-plugins.sh. This process
will update each hpi in a Red Hat dist-git repo/branch. If a repo/branch does not exist, the process will tell warn you
and ask for you to work with the RCM to get them created.

Once update-dist-git-plugins.sh succeeds, you have dist-git updated and all associated RPMs built. Each RPM
contains an HPI, and when the jenkins-1 or jenkins-2 docker images build, they will pull in the updated RPMs.

Requirements
------
- brew and rhpkg must be installed and working.
- You must have a kerberos ticket with access to update the dist-git repos (e.g. ocp-build).