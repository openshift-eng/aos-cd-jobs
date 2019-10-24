#!/usr/bin/env bash

FROM_TAG=$1
TO_TAG=$2

if [[ -z "$FROM_TAG" || -z "$TO_TAG" ]]; then
    echo "Syntax: $0 from-tag to-tag"
    echo "Example: $0  rhaos-4.2-rhel-7-candidate  rhaos-4.3-rhel-7-candidate"
    exit 1
fi

EF="tagging-errors-${TO_TAG}.txt"
echo "Unable to tag into ${TO_TAG}:" > $EF

for p in $(brew list-tagged --quiet --latest $FROM_TAG | awk '{print $1}' | grep -vE '(apb|container)-v4'); do
    echo
    echo "Tagging $p"
    OUTPUT=$(brew tag-build $TO_TAG $p 2>&1)
    if [[ "$?" != "0" ]]; then
        echo "$OUTPUT" | grep "already tagged" > /dev/null
        if [[ "$?" != "0" ]]; then
            echo | tee -a $EF
            echo "Error tagging $p" | tee -a $EF
            echo $OUTPUT | tee -a $EF
        fi
    fi
done

echo "Any errors have been recorded in: $EF"
echo "Please work with RCM to have these packages tagged in $TO_TAG"