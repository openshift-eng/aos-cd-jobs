#!/bin/bash
# Create the latest puddle
puddle -b -d /mnt/rcm-guest/puddles/RHAOS/conf/extras-docker.conf -n
# Add that puddle to the everything repo
rsync -av /mnt/rcm-guest/puddles/RHAOS/Docker/1.9/latest/ /mnt/rcm-guest/puddles/RHAOS/Docker/1.9/everything/
createrepo -d /mnt/rcm-guest/puddles/RHAOS/Docker/1.9/everything/x86_64/os
# Push everything up to the mirrors
rsync -aHv --delete-after --progress --no-g --omit-dir-times --chmod=Dug=rwX -e "ssh -o StrictHostKeyChecking=no" /mnt/rcm-guest/puddles/RHAOS/Docker/1.9/everything/ use-mirror-upload.ops.rhcloud.com:/srv/enterprise/rhel/dockerextra/
ssh -o StrictHostKeychecking=no use-mirror-upload.ops.rhcloud.com /usr/local/bin/push.enterprise.sh rhel -v

