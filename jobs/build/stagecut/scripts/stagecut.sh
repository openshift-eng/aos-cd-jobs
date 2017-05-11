#!/usr/bin/env bash

set -o xtrace
set -e

if [ "$1" == "" ]; then
    echo "Syntax: $0 <last_sprint_number>"
    echo "Example: $0 130"
    exit 1
fi

LAST_SPRINT_NUMBER="$1"
shift 1

if [ "$1" == "" ]; then
    echo "At least one repository must be specified"
    exit 1
fi

for repo in $@; do
    echo "Processing git repository: ${repo}"
    d=$(mktemp -d)
    git clone "${repo}" "${d}"

    pushd "${d}"
        git fetch --all

        if git checkout stage; then
            BACKUP_BRANCH="stage-${LAST_SPRINT_NUMBER}"

            if git checkout "$BACKUP_BRANCH"; then
                echo "Backup branch $BACKUP_BRANCH already exists in $repo ; unable to proceed"
                exit 1
            fi

            git checkout -b "stage-${LAST_SPRINT_NUMBER}"
            git push origin "stage-${LAST_SPRINT_NUMBER}"
            git checkout stage
            git reset --hard master
            #git push origin stage --force
            echo "TEST RUN - PUSHING IS NOT CURRENTLY ENABLED."
        else
            echo "Stage branch did not yet exist; creating it..."
            git checkout -b stage
            #git push origin stage
            echo "TEST RUN - PUSHING IS NOT CURRENTLY ENABLED."
        fi
    popd

    rm -rf "${d}"

done
