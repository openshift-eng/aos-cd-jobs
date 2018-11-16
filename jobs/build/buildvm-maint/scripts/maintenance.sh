#!/usr/bin/env bash

set -o xtrace
set -e

echo "====Cleaning up old tito files===="
# leaving default tito tmp in case it is used manually
if [ -e /tmp/tito ]; then
    sudo find /tmp/tito -type f -mtime +1 -exec rm -rf {} \;
fi
# new runs will use this as tito tmp
sudo find /home/jenkins/workspace/tito_tmp -type f -mtime +1 -exec rm -rf {} \;

set +e   # docker rmi -f can fail if an image is in use, so ignore errors

echo "====Cleaning up older docker images===="
# Buildvm pulls images from brew/pulp constantly in order to push them to registry.ops .
# If we don't clean out the docker images, it will fill up any drive over time.
# If we clean them all, image pulls from pulp will be extremely slow because we won't
# have any layers cached.
#
# The theory here is that we should wipe older images so that newer layers can
# stick around and speed up pulls.
#
# Number of images to leave around is dependent on the amount of space available for docker
# images on buildvm. The more you can leave around, the faster pulls can be when synchronizing
# images between brew/pulp & registry.ops.
#
# List all images and print "<create_date> <image_id>"
#       | sort by date
#       | awk out only the image id
#       | uniq so that images ids aren't duplicates
#       | pass through all but newest (head -n -100 prints everything but last 100 lines)
#       | pass everything remaining to docker rmi using xargs
{
        for image in $( docker images -q ); do
                sudo docker inspect --format='{{.Created}} {{.Id}}' --type=image ${image}
        done
} | sort | awk '{ print $2 }' | uniq | head -n -100 | xargs --no-run-if-empty sudo docker rmi -f

# Clean up exited containers - this also contributes to docker storage use
docker rm $(docker ps -qa --no-trunc --filter "status=exited")

FINAL_EXIT=0

echo "====Docker statistics===="
# Print out a report for the Jenkins job
sudo docker info

exit $FINAL_EXIT
