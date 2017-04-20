## Rebase OSE on Origin

### Abstract

OSE builds have been automated to run inside a Jenkins job. In short, a job fetches the
code from all upstream repositories (origin, origin-web-console), merges them into OSE,
creates a new tag using tito and sends the code to `brew` for the actual build. Because
of merging, OSE-specific changes are scattered across the repo and it is hard to reason
about any conflicts between OSE and Origin.

This doc proposes switching from merges to rebases and moving all the changes in OSE that
diverge from Origin into a set of commits that will sit on top of the Origin code. Rebases
will continue to happen only for the master branch so the rest of this doc does not touch
on updates in release branches.

### Naming requirements

There are different types of commits that need to be carried on top of Origin master:
* a long-term carry related to Oauth template branding
* a long-term carry related to release tooling
* a commit that is generated in every build of OSE and holds the web console branding
* a long-term carry that includes all the generated diff from old tito commits
* a tito generated commit that tags the latest build of OSE

In order to properly handle the additional commits, we need to set naming requirements
for the messages of those commits. In particular:

1. long-term carries should start with a `[CARRY]` prefix followed by a prefix that denotes
the type of the commit, eg.
```
[CARRY][BUILD] Tooling updates
```
The above example denotes that this commit needs to be carried long-term and is specific
to the building process of the repo.

2. updates to any existing `[CARRY]` commit should start with a `[SQUASH]` prefix followed
by the type of the commit that they are supposed to squash to. For example, if the commit
from the example above needs to be updated, a developer can simply create a commit that
starts with `[SQUASH][BUILD]` followed by any message, eg.
```
[SQUASH][BUILD] More tooling updates
```
You can have mutliple `[SQUASH]` commits with the same type scattered between the carries.
All of them will be squashed in their original commit order, into their respective
`[CARRY]` commits.

3. commits that are not going to be carried long-term but are necessary until the next
rebase lands, should use a `[DROP]` prefix, eg.
```
[DROP] web console bump commit
```
Unlike `[CARRY]` or `[SQUASH]` commits, `[DROP]` commits are not required to use types.
Note that these commits are going to be dropped automatically by the rebase process so you
should be sure when to use this prefix.

Based on the aforementioned requirements, developers need to take into account pre-existing
commits that are carried already and structure the messages for any additional long-term
carries appropriately.

4. `[SQUASH]` commits with a type different from the pre-existing types found in the
`[CARRY]` commits are not allowed.

5. `[CARRY]` commits with a type that is already found in pre-existing `[CARRY]`
commits are not allowed.

You can find out what commits are carried on top of Origin by executing the following
steps:
```sh
$ pwd
/home/developer/go/src/github.com/openshift/ose
$ git remote -v
origin	git@github.com:developer/ose (fetch)
origin	git@github.com:developer/ose (push)
public	https://github.com/openshift/origin (fetch)
public	https://github.com/openshift/origin (push)
upstream	git@github.com:openshift/ose (fetch)
upstream	git@github.com:openshift/ose (push)
# Find out what commits are carried on top of Origin
$ git log $(git merge-base master public/master)..HEAD --oneline
aaed106 Automatic commit of package [atomic-openshift] release [3.6.17-1].
6a27890 [CARRY][BUILD_GEN] Specfile updates
9bcbe1d [CARRY][BUILD] Tooling updates
1abdc18 [CARRY][BRANDING] Branding updates
```

### Scenarios

Bob wants to add a new commit that updates branding code so he sets off to create a new
commit on top of the commits found above:
```sh
$ git add foo.go
$ git commit -m "Updated branding code"
```
The new set of carries in Bob's branch is:
```
43dal4d Updated branding code
aaed106 Automatic commit of package [atomic-openshift] release [3.6.17-1].
6a27890 [CARRY][BUILD_GEN] Specfile updates
9bcbe1d [CARRY][BUILD] Tooling updates
1abdc18 [CARRY][BRANDING] Branding updates
```
Unfortunately for Bob, his commit message is invalid (see [rules #1, #2, and #3](#naming-requirements))
and the PR builder will not allow this commit to be merged. Bob is redirected to this doc,
skims through it, and returns back to his terminal to update the invalid commit message to:
```
[SQUASH][BRANDING] Updated branding code
```
This commit is valid since it abides to [rules #2 and #4](#naming-requirements) which are
related to `[SQUASH]` commits hence Bob's PR can be merged in OSE master.
```
fvda4fs [SQUASH][BRANDING] Updated branding code
aaed106 Automatic commit of package [atomic-openshift] release [3.6.17-1].
6a27890 [CARRY][BUILD_GEN] Specfile updates
9bcbe1d [CARRY][BUILD] Tooling updates
1abdc18 [CARRY][BRANDING] Branding updates
```
Shortly after Bob's PR is merged, Jane updates her fork and prepares an update for branding
code which also needs to be carried long-term:
```sh
$ git add pkg/bar.go pkg/baz.go
$ git commit -m "[CARRY][BRANDING] Branding changes in the oauth templates"
```
Now in Jane's branch, the following set of carries exist:
```
ratmats [CARRY][BRANDING] Branding changes in the oauth templates
fvda4fs [SQUASH][BRANDING] Updated branding code
aaed106 Automatic commit of package [atomic-openshift] release [3.6.17-1].
6a27890 [CARRY][BUILD_GEN] Specfile updates
9bcbe1d [CARRY][BUILD] Tooling updates
1abdc18 [CARRY][BRANDING] Branding updates
```
Notice that there are two `[CARRY]` commits with the same type (BRANDING). This change is
invalid based on [rule #5](#naming-requirements). Jane revisits this doc and updates her
commit message to:
```
[SQUASH][BRANDING] Branding changes in the oauth templates
```
The commit name is now valid and the PR can be merged thus resulting in the following set
of carried commits in OSE master:
```
sge53da [SQUASH][BRANDING] Branding changes in the oauth templates
fvda4fs [SQUASH][BRANDING] Updated branding code
aaed106 Automatic commit of package [atomic-openshift] release [3.6.17-1].
6a27890 [CARRY][BUILD_GEN] Specfile updates
9bcbe1d [CARRY][BUILD] Tooling updates
1abdc18 [CARRY][BRANDING] Branding updates
```
Note that you can have as many `SQUASH` commits with the same type as possible.

Bob, again, needs to check in a new script specific to OSE so he creates a new commit with
the script:
```sh
$ git add hack/set-foo.sh
$ git commit -m "[SQUASH][SCRIPT] script for setting OSE-specific envs"
```
The new set of carries in Bob's branch is:
```
d4sf5fg [SQUASH][SCRIPT] script for setting OSE-specific envs
sge53da [SQUASH][BRANDING] Branding changes in the oauth templates
fvda4fs [SQUASH][BRANDING] Updated branding code
aaed106 Automatic commit of package [atomic-openshift] release [3.6.17-1].
6a27890 [CARRY][BUILD_GEN] Specfile updates
9bcbe1d [CARRY][BUILD] Tooling updates
1abdc18 [CARRY][BRANDING] Branding updates
```
Bob realizes just before he starts the test job for his PR that he got it wrong based on
[rule #4](#naming-requirements). He steps back for a moment to think if his commit needs
to squash into a pre-exisiting `[CARRY]` commit or deserves to be its own `[CARRY]`. After
discussing it with Jane, they conclude that the new script can be squashed in the
`[CARRY][BUILD]` commit. Bob updates the commit message and his PR gets merged. The state
of master ends up being:
```
nphdbp9 [SQUASH][BUILD] script for setting OSE-specific envs
sge53da [SQUASH][BRANDING] Branding changes in the oauth templates
fvda4fs [SQUASH][BRANDING] Updated branding code
aaed106 Automatic commit of package [atomic-openshift] release [3.6.17-1].
6a27890 [CARRY][BUILD_GEN] Specfile updates
9bcbe1d [CARRY][BUILD] Tooling updates
1abdc18 [CARRY][BRANDING] Branding updates
```

Read below for the automated process that will collapse all the additional `[SQUASH]` commits
created by Bob and Jane.

### The process

OSE builds run weekly every Monday, Wednesday, and Friday with the possibility to switch into
daily builds. During an OSE build, the code is `git rebase`d on top of Origin master.
`GIT_SEQUENCE_EDITOR` is used by passing it a script that will automatically handle all the
logic of dropping and squashing commits in long-term carries as necessary. If merge conflicts
arise, they will need to be manually resolved as it already is the case today. In the future,
we will extend the conflict resolution mechanism in Jenkins to send an e-mail to the author
and committer of the conflicting commits.

The steps below will be followed to rebase OSE on top of Origin.
```sh
git clone git@github.com:openshift/ose.git
pushd ose
git remote add upstream git@github.com:openshift/origin.git
git fetch upstream
git checkout master

# Will be needed for creating the custom changelog for tito.
PREVIOUS_HEAD=$(git merge-base master upstream/master)

# rebase.py handles all the logic of squashing and dropping commits.
# The most common state of master is going to be the following but
# rebase.py shouldn't really care about the order but only make sure
# that all the additional commits on top of Origin master follow the
# naming requirements this proposal sets.
#
#
#          .-[CARRY][BUILD] Tooling updates
#         /  .-[CARRY][BRANDING] Branding updates
#        /  /  .-[CARRY][BUILD_GEN] Specfile updates
#       /  /  /  .-[DROP] webconsole bump
#      /  /  /  /  .-Tito tag commit
#     /  /  /  /  /
# m--c--c--c--w--t
#  \              \
#   \              `-ose/master/HEAD,v3.5.0.23
#    `-origin/master/HEAD
#
# WORKSPACE is meant to be the root of aos-cd-jobs
#
GIT_SEQUENCE_EDITOR=$WORKSPACE/jobs/build/ose/scripts/rebase.py git rebase -i upstream/master

# Will be needed for creating the custom changelog for tito.
CURRENT_HEAD=$(git merge-base master upstream/master)

# Create custom changelog for tito
declare -a changelog
for commit in $( git log "${PREVIOUS_HEAD}..${CURRENT_HEAD}" --pretty=%h --no-merges ); do
  changelog+=( "--changelog='$( git log -1 "${commit}" --pretty='%s (%ae)' )'" )
done

# Tag
tito tag --accept-auto-changelog "${changelog[@]}"

# Force-update master and push the latest tag
git push origin ${CURRENT_BRANCH} -f refs/tags/$(git describe)
```
### What changes for build cops

Common conflicts can rise when new changes step on branding or tooling code. Manual
resolution is the only thing we can do in such cases. Today when a conflict occurs, it is
resolved manually by simply using `git merge`, resolving any conflicts, and then kick off
a new build. The process of updating master with resolved conflicts needs to slightly
change because the changelog for tito needs to be constructed based on the previous and
the current HEAD of Origin that got pulled in with `git rebase`. All the steps above need to
run manually and then the build can be restarted in Jenkins.

We are also actively investigating whether we can stop checking in various code like tito
diffs, generated docs, bindata, and the ose-images script. Avoiding most of those diffs
will reduce even further the number of conflicts.

### What changes for developers

Apart from the [naming requirements](#naming-requirements) that we [walked through](#scenarios)
above, developers that want their OSE master branch updated, need to switch from using the
common `git fetch`+`git merge` flow to `git fetch`+`git reset`.
```
git checkout master
git fetch upstream
git reset --hard upstream/master
```
It should be rare to develop on OSE master so we do not expect this change to be too
disruptive.
