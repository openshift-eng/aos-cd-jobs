#!/usr/bin/env bash

set -o xtrace
set -e

echo "====Cleaning up old ose_images.sh temporary directories===="
find /var/tmp/ose_images* -maxdepth 0 -mtime +4 -exec rm -r {} \;

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
} | sort | awk '{ print $2 }' | uniq | head -n -100 | xargs --no-run-if-empty docker sudo rmi -f

echo "====Pushing logging and metrics images===="
ose_images.sh push_images --branch rhaos-3.4-rhel-7 --group logging --group metrics --nolatest
ose_images.sh push_images --branch rhaos-3.5-rhel-7 --group logging --group metrics --nolatest
ose_images.sh push_images --branch rhaos-3.6-rhel-7 --group logging --group metrics

set +e
ose_images.sh push_images --branch rhaos-3.7-rhel-7 --group logging --group metrics --nolatest
if [ "$?" == "0" ]; then
        echo "A new branch has been introduced, script needs to be updated."
fi
set -e

echo "====Docker statistics===="
# Print out a report for the Jenkins job
sudo docker info
