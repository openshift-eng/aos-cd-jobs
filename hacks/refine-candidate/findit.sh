#!/bin/bash
#set -o xtrace

TAG=$1

if [[ -z "$TAG" ]]; then
    echo "Run only after running download-logs.sh. Specify a the same tag to find RPMs being used by container builds."
    echo "e.g. $0 rhaos-4.2-rhel-7-candidate"
    exit 1
fi


parse_rpm() {
	# Extract NVRA components from rpm filename
	RPM=$1;B=${RPM##*/};B=${B%.rpm};A=${B##*.};B=${B%.*};R=${B##*-};B=${B%-*};V=${B##*-};B=${B%-*};N=$B
}

brew list-tagged --quiet --latest $TAG | awk '{print $1}' | grep -vE '(apb|container)-v?[0-9]' > rpm-builds

KEEP="cri-o cri-tools openshift-clients openshift-hyperkube"

# retrieve a list of all the non-source RPMs in those builds
rm -f rpm-report
rm -f rpm-names
for build in $(cat rpm-builds); do
	rpms=$(brew buildinfo $build | grep -oE '[^/]+\.(noarch|x86_64|ppc64le)\.rpm')
	found=0
	bases=""
	for rpm in $rpms; do
		echo "Found $rpm in $build" >> rpm-report
		parse_rpm $rpm
		base=$(basename --suffix=.rpm $rpm)

		if [[ "$KEEP" == *"$N"* ]]; then
			found=1
			break
		fi

		bases="$base $bases"
		grep "Installing :.*$N" kojilogs/*/*.log  > /dev/null
		if [[ "$?" == "0" ]]; then
			found=1
			break
	  	fi
	done

	if [[ "$found" == "0" ]]; then
		echo "Unable to find any rpm from $build : $bases"
	fi
done


