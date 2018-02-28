#!/bin/bash -e

MERGE_TO="$1"

if [[ "$MERGE_TO" != "3."* ]]; then
	echo "You must specify the release you want master to merge into."
	echo "e.g. $0 3.9"
	exit 1
fi

echo "READ!"
echo "About to merge origin-web-console master branch into enterprise-$MERGE_TO branch."
echo "This is only appropriate during at release cut. Do not run this without knowing why."
read -r -p "Enter OK to continue. " response

if [[ "$response" != "OK" ]]; then
	echo "$reponse != OK"
	exit 1
fi

BASE_DIR=/tmp/web-console-merge-finalizer
rm -rf "$BASE_DIR"

mkdir -p $BASE_DIR

cd $BASE_DIR

git clone git@github.com:openshift/origin-web-console.git

cd origin-web-console

# Ignore generated resources during merge
git config merge.ours.driver true
echo 'dist/** merge=ours' >> .gitattributes

git checkout -b enterprise-$MERGE_TO origin/enterprise-$MERGE_TO
git merge master --no-commit --no-ff
./hack/install-deps.sh
grunt build
git add dist
git commit -m "Merge master into enterprise-${MERGE_TO}" --allow-empty

git push

