#!/bin/sh
# Creates/removes/updates branches according the `jobs/` directory on the
# master branch.  Local files and branches will be modified, so this script
# should be executed on a clean, dedicated clone.
set -eu

set_difference() {
    printf '%s\n%s\n%s\n' "$1" "$1" "$2" | sort | uniq -u
}

list_branches() {
    git branch --list --remotes 'origin/*' \
        | awk '$1 ~ /^origin\/.*\// {print gensub("^origin/", "", 1, $1)}'
}

list_jobs() {
    [ -e jobs/ ] || return 0
    (cd jobs/ && find * -name Jenkinsfile | sed 's,/Jenkinsfile$,,')
}

filter_unchanged() {
    local msg x
    msg="Auto-generated from $1:"
    shift
    for x; do echo "$x $(git show --format=%s --no-patch "origin/$x")"; done \
        | awk -v "m=$msg" '$0 !~ m {print $1}'
}

create_branches() {
    local rev x
    rev=$1
    shift
    for x; do
        git checkout --quiet --orphan "$x" "$rev"
        find "jobs/$x/" -mindepth 1 -maxdepth 1 -exec mv -t . {} +
        rm -rf jobs/
        git add .
        git commit --quiet --message "Auto-generated from $rev:jobs/$x"
    done
}

master_rev=$(git rev-parse --short master)
branches=$(list_branches | sort)
jobs=$(list_jobs | sort)
create=$(set_difference "$branches" "$jobs")
delete=$(set_difference "$jobs" "$branches")
update=$(filter_unchanged "$master_rev" $(set_difference "$create" "$jobs"))
create_branches "$master_rev" $create $update
git checkout --quiet master
if [ "$create" -o "$delete" ]; then
    { echo "$create";  printf %s "$delete" | sed 's/^/:/'; } \
        | xargs git push $([ "${VERBOSE:-}" ] || echo --quiet) origin
fi
if [ "$update" ]; then
    echo "$update" \
        | xargs git push $([ "${VERBOSE:-}" ] || echo --quiet) --force origin
fi
