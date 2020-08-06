#!/bin/bash
set -exo pipefail

# Where to put this on the mirror, such as '4.2' or 'pre-release':
RHCOS_MIRROR_PREFIX=
ARCH=x86_64
# RHCOS version, like 42.80.20190828.2:
BUILDID=
# release version, like 4.2.0:
VERSION=
FORCE=0
TEST=0
BASEDIR=
NOLATEST=0
NOMIRROR=0

function usage() {
    cat <<EOF
usage: ${0} [OPTIONS]

This script will create directories under
https://mirror.openshift.com/pub/openshift-v4/dependencies/rhcos/{--PREFIX}/{--VERSION}/
containing the items provided in --synclist as well as a sha256sum.txt
file generated from those items.

Required Options:

  --version        The RHCOS version to mirror (ex: 4.2.0, 4.2.0-0.nightly-2019-08-28-152644)
  --prefix         The parent directory to mirror to (ex: 4.1, 4.2, pre-release)
  --synclist       Path to the file of items (URLs) to mirror (whitespace separated)
  --basedir        Base filesystem path in which the --PREFIX/--VERSION directories exist

Optional Options:

  --force          Overwrite existing contents if destination already exists
  --test           Test inputs, but ensure nothing can ever go out to the mirrors
  --nolatest       Do not update the 'latest' symlink after downloading
  --nomirror       Do not run the push.pub script after downloading

Don't get tricky! --force and --test have no predictable result if you
combine them. Just don't try it.

When using --test files will be downloaded to an alternative location
under /tmp/. The downloaded items and the sha256sum.txt file will be
printed and then the temporary directory will be erased.
EOF
}


function checkDestDir() {
    if [ -d "${DESTDIR}" ]; then
	# Is this forced?
	if [ $FORCE -eq 0 ]; then
	    echo "ERROR: Destination directory already exists and --force was not given"
	    echo "ERROR: Run this script again with the --force option to continue"
	    exit 1
	else
	    echo "INFO: Destination dir exists, will overwrite contents because --force was given"
	fi
    else
	echo "INFO: Destination dir does not exist, will create it"
	mkdir -p $DESTDIR
    fi
}

function downloadImages() {
    for img in $(<${SYNCLIST}); do
	curl -L --fail --retry 5 -O $img
    done
    # rename files to indicate the release they match (including arch suffix by tradition).
    # also create an unversioned symlink to enable consistent incoming links.
    release="$VERSION"
    [[ $release == *${ARCH}* ]] || release="$release-$ARCH"
    for name in *; do
        # name like "rhcos-buildid-qemu..."
        file="${name/$BUILDID/$release}"  # rhcos-release-qemu...
        link="${name/-$BUILDID/}"         # rhcos-qemu...
        [[ $name == $file ]] && continue  # skip files that aren't named that way
        mv "$name" "$file"
        ln -s "$file" "$link"
    done
}

function genSha256() {
    sha256sum * > sha256sum.txt
    ls -lh
    cat sha256sum.txt
}

function updateSymlinks() {
    MAJOR_MINOR=$(echo ${VERSION} |awk -F '[.-]' '{print $1 "." $2}')  # e.g. 4.3.0-0.nightly-2019-11-08-080321 -> 4.3
    # We also need to know what Y stream comes after this one.
    MAJOR_NEXT_MINOR=$(echo ${MAJOR_MINOR} |awk -F '[.-]' '{print $1 "." $2+1}')  # e.g. 4.3 -> 4.4

    if [[ "${RHCOS_MIRROR_PREFIX}" == "pre-release" ]]; then
        MAJOR_MINOR_LATEST="latest-${MAJOR_MINOR}"
        ln -sfvn $VERSION $MAJOR_MINOR_LATEST   # e.g. latest-4.3 =links_to=>  4.3.0-0.nightly-2019-11-08-080321

        # Is this major.minor the latest Y stream? If it is, we need to set
        # the overall 'latest'. We already calculated MAJOR_NEXT_MINOR  (e.g. "4.5") so see if that
        # exists someone on the mirror.
        if ls -d "${MAJOR_NEXT_MINOR}".*/ > /dev/null  2>&1; then
            echo "This is not the highest Y pre-release -- will not set overall latest"
            return 0
        fi

    else

        # Similar logic to pre-release latest link above, but for non-pre-release, the directory is just
        # 4.x  (not 4.x.0.....)
        if ls -d "${MAJOR_NEXT_MINOR}"/ > /dev/null  2>&1; then
            echo "This is not the highest Y release -- will not set overall latest"
            return 0
        fi

    fi

    ln -svfn ${VERSION} latest
    echo "Overall latest now points to ${RELEASE} in ${client_base_dir}"
    return 0
}

function mirror() {
    # Run mirroring push
    PUSHARG=`echo ${BASEDIR} | cut -d/ -f4-`
    echo "PUSH ARGUMENT: ${PUSHARG}"
    /usr/local/bin/push.pub.sh ${PUSHARG}/${RHCOS_MIRROR_PREFIX} -v
}

######################################################################
# Begin main script

if [ "${#}" -lt "8" ]; then
    # Not the best check, but basic enough
    echo "You are missing some required options"
    usage
    exit 1
fi

while [ $1 ]; do
    case "$1" in
	"--prefix")
	    shift
	    RHCOS_MIRROR_PREFIX=$1;;
	"--arch")
	    shift
	    ARCH=$1;;
	"--buildid")
	    shift
	    BUILDID=$1;;
	"--version")
	    shift
	    VERSION=$1;;
	"--synclist")
	    shift
	    SYNCLIST=$1;;
        "--basedir")
	    shift
	    BASEDIR=$1;;
	"--force")
	    FORCE=1;;
	"--test")
	    TEST=1;;
	"--nolatest")
	    NOLATEST=1;;
	"--nomirror")
	    NOMIRROR=1;;
	"-h" | "--help")
	    usage
	    exit 0;;
	*)
	    echo "Unrecognized option provided: '${1}', perhaps you need --help"
	    exit 1;;
    esac
    shift
done

if [ $TEST -eq 1 ]; then
    TMPDIR=`mktemp -d /tmp/rhcossync.XXXXXXXXXX`
    DESTDIR="${TMPDIR}/${RHCOS_MIRROR_PREFIX}/${VERSION}"
    mkdir -p ${DESTDIR}
else
    # Put the items into this directory, we might have to make it
    DESTDIR="${BASEDIR}/${RHCOS_MIRROR_PREFIX}/${VERSION}"
    checkDestDir
fi

cat <<EOF
Dest Dir: ${DESTDIR}
RHCOS OCP Version: ${VERSION}
MIRROR Prefix: ${RHCOS_MIRROR_PREFIX}
Sync List: ${SYNCLIST}
Force: ${FORCE}
Test: ${TEST}
Basedir: ${BASEDIR}
EOF

pushd $DESTDIR
downloadImages
genSha256
cd ..
if [ $NOLATEST -eq 0 ]; then
    updateSymlinks
else
    echo "INFO: Not updating 'latest' symlink because --nolatest was given"
fi
popd
if [ $TEST -eq 0 ]; then
    if [ $NOMIRROR -eq 0 ]; then
	mirror
    else
	echo "INFO: Not running push.pub command because --nomirror was given"
    fi
else
    echo "INFO: Not running sync script because --test was given"
    echo "INFO: Cleaning up temporary dir now"
    rm -fR $TMPDIR
fi
rm -f $SYNCLIST
