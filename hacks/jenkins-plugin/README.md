jenkins-plugin-rpm-update
=====
Update and/or create jenkins-plugins in brew.

So, what does the script do?

You give it a name of a jenkins plugin, and it checks to make sure
that plugin is in rpm form and at the latest version.  It also makes
sure all it's dependencies are also at their latest versions too.
If there isn't an rpm for your plugin, or one of it's dependencies, it
creates an rpm for it if it can.

If there isn't an rpm, and it isn't in dist-git, then it tells you
what packages you need to ask release engineering to create dist-git
repo's for, and what branch.

Help
-----

Usage: jenkins-plugin-rpm-update <jenkins-plugin> [release]

Example: jenkins-plugin-rpm-update openshift-sync 3.6

Requirements
-----
brew and rhscl must be installed and working.
You must have a kerberos ticket

Known Bugs
-----
 * I cannot figure out how to consistently get what type of license the plugins are.  So for now, it chooses ASL 2.0 by default.