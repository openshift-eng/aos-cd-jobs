
bugerrata
=====
List openshift bugs that are not in errata.

Before you get the right output you must
 1 Update ERRATA.list with the current errata
 2 Run "bugerrata update_bugs"
 3 Run "bugerrata update_errata"

AFter you do those steps, you can then start using the other commands to find those elusive bugs.
Don't forget to update the ERRATA.list as new errata are added.
Don't forget to refresh the bug and errata info after you've update bugs and errata (steps 2 and 3)

Help
-----
Usage: bugerrata [action] <options>

Actions:
  ub | update_bugs | update_bugzilla
      Update all the bugzilla data
  ue | update_errata | update_errata_bugs
      Update the list of bugs attached to errata
  cv | check_verified 
      Check that verified bugs are in errata
  cq | check_qa | check_on_qa
      Check that on_qa bugs are in errata
  cp | check_post 
      Check that post bugs are in errata
  cm | check_modified 
      Check modified bugs are not in errata
  -d | --details 
      Output: Show bug details
  -b | --bug 
      Output: Show bug number only (default)
  -u | --url 
      Output: Show full bugzilla url
  -f | --firefox 
      Output: Show firefox command to display the buzilla url
  --target [target version]
      Sort: Only show bugs with that target. Ex: 3.5.0
  test
      Test to make sure script runs

Options:
  -h, --help          :: Show this options menu
  -v, --verbose       :: Be verbose


Requirements
-----
bugzilla must be installed and working
 - yum install python-bugzilla
 et-info must be installed and working
 - yum install rcm-errata
 