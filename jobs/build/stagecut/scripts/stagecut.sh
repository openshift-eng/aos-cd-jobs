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
            git push origin stage --force

        else
            echo "Stage branch did not yet exist; creating it..."
            git checkout -b stage
            git push origin stage
        fi

        # If this is the openshift-ansible repository, we need to take an extra
        # step to ensure CI continues working. During the installer CI job,
        # master is extracted and tito tag is run. The tag created must be unique. Prior
        # to stagecut, this is always true. During stagecut, however,
        # openshift-ansible.spec in master falls behind the tags being created
        # by builds in stage.
        # To resolve this, during stagecut, openshift-ansible.spec in master
        # is tweaked to have four fields instead of 3 so that CI tito tags
        # won't conflict with tags created by stage builds.
        if [ -f "openshift-ansible.spec" ]; then
            git checkout master
            export VERSION="$(grep Version: openshift-ansible.spec | awk '{print $2}')"
            if [ ! -z "$(echo ${VERSION} | cut -d . -f 4)" ]; then
                echo "openshift-ansible already contains a 4 field Version in spec file. Something is wrong, so refusing to proceed."
                echo "Performing a standard openshift-ansible build after stagecut ended should have restored a three field version."
                exit 1
            fi
            VERSION="${VERSION}.0" # Add another field
            sed -i "s/Version:.*/Version:        ${VERSION}/" openshift-ansible.spec
            git add openshift-ansible.spec
            git commit -m "Adding version field for stagecut"
            git push origin master
        fi

    popd

    rm -rf "${d}"

done
