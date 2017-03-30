## Rebase OSE on Origin

### Abstract

Today, code in OSE lands by fetching and merging Origin manually. OSE-specific changes are
scattered across the repo and it is hard to reason about any conflicts. This doc proposes
moving all the changes in OSE that diverge from Origin into a set of commits that will sit
on top of the Origin code. A Jenkins job will be rebasing OSE master on top of Origin master
on a daily basis and rebases will continue to happen only for the master branch so the rest
of this doc does not touch on updates in release branches.


### Naming requirements

There are different types of commits that need to be carried on top of Origin master:
* a long-term carry related to Oauth template branding
* a long-term carry related to release tooling
* a commit that is generated in every build of OSE and holds the web console branding
* a long-term carry that includes all the generated diff from old tito commits
* a tito generated commit that tags the latest build of OSE

In order to properly handle the additional commits, we need to set naming requirements
for the messages of those commits. In particular:
* long-term carries should start with a `[CARRY]` prefix followed by a prefix that denotes
the type of the commit. For example, `[CARRY][BUILD] Tooling updates` denotes that this
commit needs to be carried long-term and is specific to the building process of the repo.
* updates to any existing [CARRY] commit should start with a `[SQUASH]` prefix followed
by the type of the commit that they are supposed to squash to. For example, if the commit
from the example above needs to be updated, a developer can simply create a commit that
starts with `[SQUASH][BUILD]` followed by any message.
* commits that are not going to be carried long-term but are necessary until the next rebase
lands, should use a `[DROP]` prefix. Note that these commits are going to be dropped
automatically by the rebase process so you should be sure when to use this prefix.

### The process

During the actual rebase, `GIT_SEQUENCE_EDITOR` is going to be used by passing it a script that
will automatically handle all the logic of dropping and squashing commits in long-term carries
as necessary. If merge conflicts arise, they will need to be manually resolved as it already is
the case today. In the future, we will extend the conflict resolution mechanism in Jenkins to
send an e-mail to the author and committer of the conflicting commits.

A nightly build of OSE should follow the steps below in order to rebase on top of Origin:
```sh
git clone git@github.com:openshift/ose.git
pushd ose
git remote add upstream git@github.com:openshift/origin.git
git fetch upstream
git checkout master

# Note down the current latest tag because squashing the tito commit into specfile updates
# will drop it and tito tag needs it further down the build process in order to determine
# the next (new) tag.
last_tag="$( git describe --abbrev=0 --tags )"

# rebase.py handles all the logic of squashing and dropping commits.
# The most common state of master is going to be the following but
# rebase.py shouldn't really care about the order but only make sure
# that all the additional commits on top of Origin master follow the
# naming requirements this proposal sets.
#
#
#          .-[CARRY][BUILD] Tooling updates
#         /  .-[CARRY][BRANDING] OAuth templates branding
#        /  /  .-[CARRY][BUILD_GEN] Specfile updates
#       /  /  /  .-[DROP] webconsole bump
#      /  /  /  /  .-Tito tag commit
#     /  /  /  /  /
# m--c--c--c--w--t
#  \              \
#   \              `-ose/master/HEAD,v3.5.0.23
#    `-origin/master/HEAD
#
GIT_SEQUENCE_EDITOR=rebase.py git rebase -i upstream/master

# We need to retag, because the rebase removed the latest tito tag.
# Needs to be forced because while the tag is removed from the branch,
# it still exists globally in the repository.
git tag -f "${last_tag}" HEAD
```

Common conflicts can rise when new changes step on branding or tooling code. Manual resolution is the
only thing we can do in such cases. Nothing should change from what happens today when a conflict needs
to be resolved but we can reduce the amount of conflicts by using build flags that will generate branding
code depending on the repository that is being built. We should also investigate whether we can stop
checking in various code like tito diffs, generated docs, bindata, and the ose-images script. Avoiding
those diffs will reduce even further the number of conflicts.


In case a new [CARRY] commit needs to be introduced or an existing one needs to be updated, developers
do not need to force-push to master. Instead, construct your commit messages using the naming requirements
specified [above](#naming-requirements) and the rebase process should be responsible for collapsing [SQUASH]
commits into existing [CARRY] commits.
