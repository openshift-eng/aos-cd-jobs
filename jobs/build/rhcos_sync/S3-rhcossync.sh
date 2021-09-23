#!/bin/bash
set -exo pipefail

# Where to put this on the s3 mirror, such as '4.2' or 'pre-release':
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

This script will create directories on the s3 mirror under
/pub/openshift-v4/x86_64/dependencies/rhcos/{--PREFIX}/{--VERSION}/
containing the items provided in --synclist as well as a sha256sum.txt
file generated from those items.

Required Options:

  --version        The RHCOS version to mirror (ex: 4.2.0, 4.2.0-0.nightly-2019-08-28-152644)
  --prefix         The parent directory to mirror to (ex: 4.1, 4.2, pre-release)
  --synclist       Path to the file of items (URLs) to mirror (whitespace separated)
  --basedir        Base filesystem path in which the --PREFIX/--VERSION directories exist

Optional Options:

  --nolatest       Do not update the 'latest' symlink after downloading
  --test           Test inputs, but ensure nothing can ever go out to the mirrors
  --nomirror       Do not run the push.pub script after downloading


EOF
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
        ln --symbolic "$file" "$link"
    done
    # Some customer portals point to the deprecated `rhcos-installer` names rather than `rhcos-live`.
    # Fix those links.
    for f in $(find . -maxdepth 1 -type l -name 'rhcos-live-*'); do
        ln -s "$(readlink $f)" "${f/rhcos-live-/rhcos-installer-}"
    done
}

function genSha256() {
    sha256sum * > sha256sum.txt
    ls -lh
    cat sha256sum.txt
}

function emulateSymlinks() {
    S3_SOURCE="$1"
    MAJOR_MINOR=$(echo ${VERSION} |awk -F '[.-]' '{print $1 "." $2}')  # e.g. 4.3.0-0.nightly-2019-11-08-080321 -> 4.3
    # We also need to know what Y stream comes after this one.
    MAJOR_NEXT_MINOR=$(echo ${MAJOR_MINOR} |awk -F '[.-]' '{print $1 "." $2+1}')  # e.g. 4.3 -> 4.4

    if [[ "${RHCOS_MIRROR_PREFIX}" == "pre-release" ]]; then
        MAJOR_MINOR_LATEST="latest-${MAJOR_MINOR}"
        aws s3 sync --delete "${S3_SOURCE}" s3://art-srv-enterprise${BASEDIR}/${RHCOS_MIRROR_PREFIX}/${MAJOR_MINOR_LATEST}/

        # Is this major.minor the latest Y stream? If it is, we need to set
        # the overall 'latest'.

        # List the all the other "latest-4.x" or "stable-4.x" directory names. s3 ls
        # returns lines lke:
        #                           PRE stable-4.1/
        #                           PRE stable-4.2/
        #                           PRE stable-4.3/
        # So we clean up the output to:
        # stable-4.1
        # stable-4.2
        # ...
        # Then we use sort | tac to order the versions and find the greatest '4.x' directory
        LATEST_LINK=$(aws s3 ls "s3://art-srv-enterprise${BASEDIR}/${RHCOS_MIRROR_PREFIX}/${MAJOR_NEXT_MINOR}." | grep PRE | awk '{print $2}' | tr -d '/' | sort -V | tac | head -n 1 || true)
        # LATEST_LINK will end up being something like 4.9.0-fc.0 if the next major exists or "" if it does not.

        if [[ -n "${LATEST_LINK}" ]]; then
            aws s3 sync --delete "${S3_SOURCE}" s3://art-srv-enterprise${BASEDIR}/${RHCOS_MIRROR_PREFIX}/latest/
        fi

    else

        # Similar logic to pre-release latest link above, but for non-pre-release, the directory is just
        # 4.x  (not 4.x.0.....). The query will be files within the directory OR nothing if the directory does not exist/is empty.
        LATEST_CONTENT=$(aws s3 ls "s3://art-srv-enterprise${BASEDIR}/${MAJOR_NEXT_MINOR}/" | grep PRE || true)

        if [[ -n "${LATEST_CONTENT}" ]]; then
            aws s3 sync --delete ./ s3://art-srv-enterprise${BASEDIR}/latest/
        fi
    fi

    return 0
}


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
    "--nolatest")
        NOLATEST=1;;
    "--test")
        TEST=1;;
    "--nomirror")
        NOMIRROR=1;;
    "--force")
        FORCE=1;;
    "-h" | "--help")
        usage
        exit 0;;
    *)
        echo "Unrecognized option provided: '${1}', perhaps you need --help"
        exit 1;;
    esac
    shift
done

DESTDIR="${PWD}/staging-${VERSION}"
mkdir -p "${DESTDIR}"

cat <<EOF
Dest Dir: ${DESTDIR}
RHCOS OCP Version: ${VERSION}
MIRROR Prefix: ${RHCOS_MIRROR_PREFIX}
Sync List: ${SYNCLIST}
Basedir: ${BASEDIR}
EOF

pushd $DESTDIR
downloadImages
genSha256

if [ $TEST -eq 1 -o $NOMIRROR -eq 1 ]; then
  echo Would have copied out:
  ls
  exit 0
fi

# Copy the files out to their main location
aws s3 sync --delete ./ "s3://art-srv-enterprise${BASEDIR}/${RHCOS_MIRROR_PREFIX}/${VERSION}/"
if [ $NOLATEST -eq 0 ]; then
    emulateSymlinks "s3://art-srv-enterprise${BASEDIR}/${RHCOS_MIRROR_PREFIX}/${VERSION}/"
else
    echo "INFO: Not updating 'latest' symlink because --nolatest was given"
fi
popd
rm -rf $DESTDIR
