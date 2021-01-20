#!/bin/bash

TAG="${TAG:-${1:-}}"

if [[ -z "$TAG" ]]; then
    echo "Specify a tag to download logs for"
    echo "e.g. $0 rhaos-4.2-rhel-7-candidate"
    exit 1
fi

for build in $(brew list-tagged --quiet --latest $TAG | awk '{print $1}' | grep -E '(apb|container)-v?[0-9]');
do
    {
        task=$(brew buildinfo $build | grep Extra: | sed -n  's/.*container_koji_task_id...\([0-9]\+\).*/\1/p')
        if [ -z "$task" ]; then
                echo "Could not find task for: $build"
        else
                brew download-logs -r $task
        fi
    }&
done
wait
echo "done"
