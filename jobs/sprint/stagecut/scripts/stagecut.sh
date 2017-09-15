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
            if [ "$DESTRUCTIVE_SYNCH" != "true" ]; then
                BACKUP_BRANCH="stage-${LAST_SPRINT_NUMBER}"
                if git checkout "$BACKUP_BRANCH"; then
                    echo "Backup branch $BACKUP_BRANCH already exists in $repo ; unable to proceed"
                    exit 1
                fi
            
                git checkout -b "stage-${LAST_SPRINT_NUMBER}"
                if [ "${TEST_MODE}" != "true" ]; then
                    git push origin "stage-${LAST_SPRINT_NUMBER}"
                else
                    echo "In test mode; would have run: git push origin stage-${LAST_SPRINT_NUMBER}"
                fi
                git checkout stage
            fi

            if [ -z "${SOURCE_VERSION}" ]; then
                # By default, master is pushed into master
                git reset --hard master
            else
                if [ ! -z "$(git ls-remote ${repo} release-${SOURCE_VERSION})" ]; then
                    git reset --hard "origin/release-${SOURCE_VERSION}"
                elif [ ! -z "$(git ls-remote ${repo} enterprise-${SOURCE_VERSION})" ]; then
                    git reset --hard "origin/enterprise-${SOURCE_VERSION}"
                else
                    echo "Unable to find source version (${SOURCE_VERSION}) branch in repository for git repo: $repo"
                    exit 1
                fi
            fi

            if [ "${TEST_MODE}" != "true" ]; then
                git push origin stage --force
            else
                echo "In test mode; would have run: git push origin stage --force"
            fi

        else
            echo "Stage branch did not yet exist; creating it..."
            git checkout -b stage
            if [ "${TEST_MODE}" != "true" ]; then
                git push origin stage
            else
                echo "In test mode; would have run: git push origin stage"
            fi
        fi

    popd

    rm -rf "${d}"
done
