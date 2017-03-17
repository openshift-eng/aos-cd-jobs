#!/bin/sh
# Tests the migration of the current branch structure in aos-cd-jobs to
# directories under the `jobs` directory on the master branch.
set -eu

DIR=${TMPDIR:-/tmp}/aos-cd-jobs
MULTIDIRECTORY_SH=$(realpath "$(dirname "$0")/multidirectory.sh")
GIT_AUTHOR_NAME=test
GIT_AUTHOR_EMAIL=test@example.com
GIT_COMMITTER_NAME=$GIT_AUTHOR_NAME
GIT_COMMITTER_EMAIL=$GIT_AUTHOR_EMAIL
export GIT_AUTHOR_NAME GIT_AUTHOR_EMAIL GIT_COMMITTER_NAME GIT_COMMITTER_EMAIL
mkdir -p "$DIR/"
[ -e "$DIR/mirror.git/" ] \
    || git clone --mirror \
        https://github.com/openshift/aos-cd-jobs.git "$DIR/mirror.git/"
rm -rf "$DIR/fake_origin.git/" "$DIR/clone/"
git clone --quiet --mirror "$DIR/mirror.git/" "$DIR/fake_origin.git/"
git clone --quiet "$DIR/fake_origin.git/" "$DIR/clone/"
cd "$DIR/clone/"
branches=$(git branch --list --remotes 'origin/*' \
    | awk '$1 ~ /^origin\/.*\// {print gensub("^origin/", "", 1, $1)}')
for x in $branches; do
    mkdir -p "jobs/$x"
    git archive "origin/$x" | tar -C "jobs/$x" -x
done
git add .
git commit --quiet --message 'branches -> jobs/'
git push --quiet
"$MULTIDIRECTORY_SH"
