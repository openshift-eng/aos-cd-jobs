#!/bin/bash

set -o xtrace
set -euo pipefail

usage() {
  echo >&2
  echo "Usage `basename $0` <jenkins-version> <rhaos-branch> <path-to-hpis-dir> " >&2
  echo >&2
  echo "Example: `basename $0` 2.42  rhaos-3.7-rhel-7 ./working/hpis" >&2
  echo >&2
  echo "This example would populate all the HPIs in the specified directory in the dist-git repo jenkins-2-plugins" >&2
  echo "and the branch rhaos-3.7-rhel-7 ." >&2
  exit 1
}

# Make sure they passed something in for us
if [ "$#" -lt 3 ] ; then
  usage
fi

USER_INFO=""
if [ "$(whoami)" == "jenkins" ]; then
    USER_INFO="--user=ocp-build"
fi

target_jenkins_version="$1"
jenkins_major=$(echo "${target_jenkins_version}." | cut -d . -f 1)
repo="jenkins-${jenkins_major}-plugins"
rhaos_branch="$2"
hpis_dir=$(realpath "$3")


# Setup
workingdir=$(mktemp -d /tmp/jenkins-plugin-XXXXXX)
cd ${workingdir}

echo "Cloning dist-git repository ...."
REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt rhpkg ${USER_INFO} clone ${repo}
pushd ${repo}
REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt rhpkg switch-branch ${rhaos_branch}
popd

mkdir -p ${workingdir}/build/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
topdir="${workingdir}/build"

SOURCES=""
INSTALLS=""
FILES=""

COUNT=0

for hpi in "${hpis_dir}"/*.hpi ; do

    filename="$(basename ${hpi})"

    if [ -f "${topdir}/SOURCES/${filename}" ]; then
        echo "Plugin ${filename} already added; skipping"
        continue
    fi

    extract=$(mktemp -d ${workingdir}/extract-XXXXXX)

    # Get hpi and find version
    cd "${extract}"
    unzip "${hpi}" > /dev/null
    cat META-INF/MANIFEST.MF | tr -d '\r' | tr '\n' '|' | sed -e 's#| ##g' | tr '|' '\n' > META-INF/MANIFEST.MF.format
    PLUGIN_NAME=$(basename -s .hpi ${hpi})  # Strip path and suffix to arrive at plugin name
    PLUGIN_VERSION="$(grep Plugin-Version: META-INF/MANIFEST.MF.format | awk '{print $2}')"

    echo
    echo "Working on: ${hpi} -> ${PLUGIN_NAME}:${PLUGIN_VERSION}"

    cp -f ${hpi} ${topdir}/SOURCES/

    SOURCES="${SOURCES}Source${COUNT}:    https://updates.jenkins-ci.org/download/plugins/${PLUGIN_NAME}/${PLUGIN_VERSION}/${PLUGIN_NAME}.hpi
" # Include a newline at the end of the SOURCES

    INSTALLS="${INSTALLS}cp %{SOURCE${COUNT}} %{buildroot}/%{_libdir}/jenkins/
" # Include a newline at the end of the INSTALLS

    FILES="${FILES}%{_libdir}/jenkins/${PLUGIN_NAME}.hpi
" # Include a newline at the end of the FILES

    COUNT=$(($COUNT+1))

done

# Make up a version based on date package was built
VERSION="$(echo ${rhaos_branch} | cut -d- -f2).$(date +%s)"

cat <<EOF > ${topdir}/SPECS/${repo}.spec
Summary:    OpenShift Jenkins ${jenkins_major} Plugins
Name:       ${repo}
Version:    $VERSION
Release:    1%{?dist}
License:    ASL 2.0
BuildArch: noarch
URL:        https://updates.jenkins-ci.org/download/plugins
${SOURCES}
Requires:   jenkins >= ${target_jenkins_version}


%description
Plugins for OpenShift Jenkins ${jenkins_major} image.

%prep


%build


%install
rm -rf %{buildroot}
mkdir -p %{buildroot}/%{_libdir}/jenkins/
${INSTALLS}

%files
${FILES}

%changelog
EOF


echo "  BUILDING: ${repo}"

cd "${workingdir}/${repo}"

cp ${workingdir}/build/SPECS/${repo}.spec .
git add ${repo}.spec

REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt rhpkg new-sources ${topdir}/SOURCES/*.hpi

REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt rhpkg ${USER_INFO} commit -p -m "Update to ${VERSION}"

REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt rhpkg ${USER_INFO} build

# cleanup
# rm -rf "${workingdir}"
