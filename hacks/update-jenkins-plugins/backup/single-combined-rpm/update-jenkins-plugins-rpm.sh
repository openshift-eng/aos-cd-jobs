#!/bin/bash

usage() {
  echo >&2
  echo "Usage `basename $0` <jenkins-major-version> <aos-release> <path-to-plugins-list>" >&2
  echo "  Where path-to-plugins-list is a line delimited list of jenkins plugins to prepare." >&2
  echo "    Example entries:   workflow-aggregator:2.1" >&2
  echo "      or use latest:   workflow-aggregator" >&2

  echo >&2
  echo "Example: `basename $0` 2 3.6 /some/path/jenkins-2-plugins.txt" >&2
  echo >&2
  popd &>/dev/null
  exit 1
}

# Make sure they passed something in for us
if [ "$#" -lt 3 ] ; then
  usage
fi

set -o xtrace

JENKINS_VERSION="$1"
RHAOS_RELEASE="$2"
PLUGIN_LISTING="$(realpath $3)"
PLUGINS_RPM_VERSION="1.$(date +%s%3N)"  # Ever increasing millis since epoch

workingdir=$(mktemp -d /tmp/jenkins-plugin-XXXXXX)
pushd "${workingdir}"
topdir="${workingdir}/build"
mkdir -p ${topdir}/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
mkdir -p ${workingdir}/{extracts}
hpis_dir="${topdir}/SOURCES"
extracts_dir="${workingdir}/extracts"
spec_file="${topdir}/SPECS/jenkins-${JENKINS_VERSION}-plugins.spec"

# Create the start of the spec file

cat <<EOF > ${spec_file}.head
Summary:    Collection of plugins for OpenShift jenkins-${JENKINS_VERSION} runtime
Name:       jenkins-${JENKINS_VERSION}-plugins
Version:    ${PLUGINS_RPM_VERSION}
Release:    1%{?dist}
License:    ASL 2.0
URL:        https://updates.jenkins-ci.org
Requires:   jenkins >= ${JENKINS_VERSION}.0
EOF

cat <<EOF > ${spec_file}.tail


%description
Collection of plugins for OpenShift jenkins-${JENKINS_VERSION} runtime.

%prep


%build


%install
rm -rf %{buildroot}
mkdir -p %{buildroot}/%{_libdir}/jenkins/
EOF

NN=0

add_plugin() {
    plugin_line="$1"

    # Some dependencies are of the form: "subversion:2.5;resolution:=optional"
    if [[ "$plugin_line" == *"resolution:=optional"*  ]]; then
        echo "Skipping optional dependency: ${plugin_line}"
        return 0
    fi

    # Remove anything after the colon
    plugin_line=${plugin_line%\;.*}

    plugin=$(echo "${plugin_line}:" | cut -d : -f 1)
    echo "Processing plugin: $plugin"
    plugin_version=$(echo "${plugin_line}:" | cut -d : -f 2)
    if [ -z "${plugin_version}" -o "${plugin_version}" == "latest" ]; then
        plugin_url="https://updates.jenkins-ci.org/latest/${plugin}.hpi"
    else
        plugin_url="https://updates.jenkins-ci.org/download/plugins/${plugin}/${plugin_version}/${plugin}.hpi"
    fi
    hpi_file="${hpis_dir}/${plugin}.hpi"

    if [ -f "${hpi_file}" ]; then
        echo "Skipping already existing plugin: $hpi_file"
        return 0
    fi

    echo "Downloading plugin: ${plugin_url}"
    wget -O "${hpi_file}" "${plugin_url}"
    if [ "$?" != "0" ]; then
        echo "Error downloading ${plugin}; exiting"
        exit 1
    fi

    extract="${workingdir}/extracts/${plugin}"
    mkdir -p ${extract}
    unzip "${hpi_file}" -d ${extract}

    pushd "${extract}"
        cat META-INF/MANIFEST.MF | tr -d '\r' | tr '\n' '|' | sed -e 's#| ##g' | tr '|' '\n' > META-INF/MANIFEST.MF.format
        PLUGIN_VERSION="$(grep Plugin-Version: META-INF/MANIFEST.MF.format | awk '{print $2}')"
        PLUGIN_JENKINS_VERSION="$(grep Jenkins-Version: META-INF/MANIFEST.MF.format | awk '{print $2}')"
        PLUGIN_URL="$(grep Url: META-INF/MANIFEST.MF.format | awk '{print $2}')"
        PLUGIN_DEPS="$(grep '^Plugin-Dependencies: ' META-INF/MANIFEST.MF.format | sed -e 's#^Plugin-Dependencies: ##')"
        PLUGIN_SUMMARY="$(grep Long-Name: META-INF/MANIFEST.MF.format |cut -d' ' -f2-)"
        PLUGIN_DESCRIPTION="$(grep Specification-Title: META-INF/MANIFEST.MF.format |cut -d' ' -f2-)"
    popd

    echo "Source${NN}: ${plugin_url}" >> ${spec_file}.head
    echo "cp %{SOURCE${NN}} %{buildroot}/%{_libdir}/jenkins/" >> ${spec_file}.tail
    NN=$(($NN + 1))

    PLUGIN_DEPS=$(echo "${PLUGIN_DEPS}" | tr "," " ")  # Space delimit dependencies

    for plugin_entry in ${PLUGIN_DEPS}; do
        add_plugin "${plugin_entry}"
    done

}

for plugin_line in $(cat "${PLUGIN_LISTING}"); do
    add_plugin "${plugin_line}"
done

cat ${spec_file}.head ${spec_file}.tail > ${spec_file}
rm ${spec_file}.head ${spec_file}.tail

echo >> ${spec_file}
echo "%files" >> ${spec_file}

for hpi in $(ls ${hpis_dir}); do
    echo "%{_libdir}/jenkins/$(basename $hpi)" >> ${spec_file}
done

echo >> ${spec_file}.tail
echo "%changelog" >> ${spec_file}

pushd "${topdir}/SPECS"
NEW_SRPM=`rpmbuild -bs --define "_topdir ${topdir}" ${spec_file} | grep Wrote: | awk '{print $2}'`
popd

popd
# rm -rf "${workingdir}"

exit 0




echo
echo "Working on:"
echo "  PLUGIN_NAME: ${PLUGIN_NAME}  PLUGIN_VERSION: ${PLUGIN_VERSION}"

# Check if we already have that built
brew download-build --arch=src --latestfrom=rhaos-3.6-rhel-7-candidate jenkins-plugin-${PLUGIN_NAME} > /dev/null 2>&1
if [ "$?" == "0" ] ; then
  SRC_RPM="$(ls -1 jenkins-plugin-${PLUGIN_NAME}*.src.rpm)"
  OLD_VERSION="$(rpm -qp --qf '%{version}' ${SRC_RPM})"
  echo "  OLD_VERSION: ${OLD_VERSION}"
  if [ "${OLD_VERSION}" == "${PLUGIN_VERSION}" ] ; then
    echo
    echo "  Already Done: ${PLUGIN_NAME} - ${OLD_VERSION}"
    echo
    exit 1
  else
    rpm -U --define "_topdir ${topdir}" ${SRC_RPM}
  fi
else
  echo "  No rpm has been built yet for jenkins-plugin-${PLUGIN_NAME}"
  echo "    Creating initial spec file"
  echo
  cat <<EOF > ${topdir}/SPECS/jenkins-plugin-${PLUGIN_NAME}.spec
%global plugin_name ${PLUGIN_NAME}

Summary:    ${PLUGIN_VERSION}
Name:       jenkins-plugin-%{plugin_name}
Version:    ${PLUGIN_SUMMARY}
Release:    1%{?dist}
License:    ASL 2.0
URL:        ${PLUGIN_URL}
Source0:    https://updates.jenkins-ci.org/download/plugins/%{plugin_name}/%{version}/%{plugin_name}.hpi
Requires:   jenkins >= ${PLUGIN_JENKINS_VERSION}

%description
${PLUGIN_DESCRIPTION}

%prep


%build


%install
rm -rf %{buildroot}
mkdir -p %{buildroot}/%{_libdir}/jenkins/
cp %{SOURCE0} %{buildroot}/%{_libdir}/jenkins/


%files
%{_libdir}/jenkins/%{plugin_name}.hpi

%changelog
EOF
fi

## Everything is setup, proceed with the update
# Move in hpi
rm -f ${topdir}/SOURCES/${PLUGIN_NAME}.hpi
cp -f ${workingdir}/${PLUGIN_NAME}.hpi ${topdir}/SOURCES/${PLUGIN_NAME}.hpi

## Update spec file
cd ${topdir}/SPECS
# Remove Requires: jenkins-plugin
sed -i '/^Requires:.*jenkins-plugin.*/d' jenkins-plugin-${PLUGIN_NAME}.spec
# Add in new Requires: jenkins-plugin
IFS=',' read -a array <<< "${PLUGIN_DEPS}"
for d in "${array[@]}"
do
  plugin="$(cut -d':' -f1 - <<< "$d")"
  if [[ $d == *"resolution:=optional"* ]]; then
    echo "  Skipping optional dependency $plugin"
  else
    echo "  ${PLUGIN_NAME}:: Requires:   jenkins-plugin-${plugin}"
    sed -i "s/^Requires:.*jenkins .*/&\nRequires:   jenkins-plugin-${plugin}/" jenkins-plugin-${PLUGIN_NAME}.spec
    echo "    ${PLUGIN_NAME}: verifying that we have dependency updated"
    update-jenkins-plugins-rpm.sh ${plugin}
  fi
done
# Update Version, Jenkins Release, and Changelog
sed -i "s|^Version: .*|Version:    ${PLUGIN_VERSION}|" jenkins-plugin-${PLUGIN_NAME}.spec
sed -i "s|^Release: .*|Release:    0%{?dist}|" jenkins-plugin-${PLUGIN_NAME}.spec
sed -i "s|^Requires:   jenkins >=.*|Requires:   jenkins >= ${PLUGIN_JENKINS_VERSION}|" jenkins-plugin-${PLUGIN_NAME}.spec
rpmdev-bumpspec --comment="Update to ${PLUGIN_VERSION}" jenkins-plugin-${PLUGIN_NAME}.spec
## END: Update spec file

## Lets build the new package, if we can
echo "Dependencies finished for ${PLUGIN_NAME}-${PLUGIN_VERSION}"
echo

# Create src.rpm
NEW_SRPM=`rpmbuild -bs --define "_topdir ${topdir}" jenkins-plugin-${PLUGIN_NAME}.spec | grep Wrote: | awk '{print $2}'`

# Build package in brew
cd ${workingdir}
echo "  Checking if a dist-git repo has been created ...."
rhpkg clone jenkins-plugin-${PLUGIN_NAME} > /dev/null 2>&1
if [ "$?" == "0" ] ; then
  cd jenkins-plugin-${PLUGIN_NAME}
  echo "    dist-git repo has been created."
  echo
  echo "  Checking if a dist-git branch has been created ...."
  rhpkg switch-branch rhaos-${RHAOS_RELEASE}-rhel-7 > /dev/null 2>&1
  if [ "$?" == "0" ] ; then
    echo "    dist-git branch has been created."
    echo
  else
    echo "    There is no dist-git branch rhaos-${RHAOS_RELEASE}-rhel-7 for jenkins-plugin-${PLUGIN_NAME}"
    echo "    Adding to our list of package branches to request"
    echo
    echo "NeedBranch: jenkins-plugin-${PLUGIN_NAME} Branch: rhaos-${RHAOS_RELEASE}-rhel-7" >> ${request_file}
    cat ${request_file}
    echo
    exit 1
  fi
else
  echo "    There is no dist-git repo for jenkins-plugin-${PLUGIN_NAME}"
  echo "    Adding to our list of packages to request"
  echo
  echo "NeedRepo: jenkins-plugin-${PLUGIN_NAME} Branch: rhaos-${RHAOS_RELEASE}-rhel-7" >> ${request_file}
  cat ${request_file}
  echo
  exit 1
fi

echo "  BUILDING: jenkins-plugin-${PLUGIN_NAME}-${PLUGIN_VERSION}"
echo

rhpkg import --skip-diffs ${NEW_SRPM} > /dev/null 2>&1 
rhpkg commit -p -m "Update to ${PLUGIN_VERSION}" > /dev/null 2>&1
rhpkg build

# cleanup
rm -rf ${workingdir}
