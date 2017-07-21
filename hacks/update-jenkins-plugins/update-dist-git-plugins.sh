#!/bin/bash

usage() {
  echo >&2
  echo "Usage `basename $0` <lowest-supported-jenkins-version> <aos-release> <path-to-hpis-dir> " >&2
  echo >&2
  echo "Example: `basename $0` 1.651.2  3.6  ./working/hpis" >&2
  echo >&2
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
rhaos_release="$2"
hpis_dir=$(realpath "$3")

request_file="/tmp/rcm-requests-$(date +%Y-%m-%d)"
rm "${request_file}" 2> /dev/null  # If there happens to have been another run today

for hpi in "${hpis_dir}"/*.hpi ; do

    # Setup
    workingdir=$(mktemp -d /tmp/jenkins-plugin-XXXXXX)
    cd ${workingdir}
    mkdir extract
    mkdir -p ${workingdir}/build/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
    topdir="${workingdir}/build"

    # Get hpi and find version
    cd extract
    unzip "${hpi}" > /dev/null
    cat META-INF/MANIFEST.MF | tr -d '\r' | tr '\n' '|' | sed -e 's#| ##g' | tr '|' '\n' > META-INF/MANIFEST.MF.format
    PLUGIN_NAME=$(basename -s .hpi ${hpi})  # Strip path and suffix to arrive at plugin name
    PLUGIN_VERSION="$(grep Plugin-Version: META-INF/MANIFEST.MF.format | awk '{print $2}')"
    PLUGIN_JENKINS_VERSION="$(grep Jenkins-Version: META-INF/MANIFEST.MF.format | awk '{print $2}')"
    PLUGIN_URL="$(grep Url: META-INF/MANIFEST.MF.format | awk '{print $2}')"
    PLUGIN_DEPS="$(grep '^Plugin-Dependencies: ' META-INF/MANIFEST.MF.format | sed -e 's#^Plugin-Dependencies: ##')"
    PLUGIN_SUMMARY="$(grep Long-Name: META-INF/MANIFEST.MF.format |cut -d' ' -f2-)"
    PLUGIN_DESCRIPTION="$(grep Specification-Title: META-INF/MANIFEST.MF.format |cut -d' ' -f2-)"

    echo
    echo "Working on: ${hpi} -> ${PLUGIN_NAME}:${PLUGIN_VERSION}"

    # Check if we already have that built
    brew download-build --arch=src --latestfrom=rhaos-${rhaos_release}-rhel-7-candidate jenkins-plugin-${PLUGIN_NAME} > /dev/null 2>&1
    if [ "$?" == "0" ]; then
        SRC_RPM="$(ls -1 jenkins-plugin-${PLUGIN_NAME}*.src.rpm)"
        OLD_VERSION="$(rpm -qp --qf '%{version}' ${SRC_RPM})"
        echo "  Found existing version in dist-git: ${OLD_VERSION}"
        if [ "${OLD_VERSION}" == "${PLUGIN_VERSION}" ] ; then
            echo "  Version matches target; skipping update"
            echo
            continue
        else
            rpm -U --define "_topdir ${topdir}" ${SRC_RPM}
        fi
    else
        echo "  No rpm has been built yet for jenkins-plugin-${PLUGIN_NAME}"
        echo "    Creating initial spec file"
        echo
        cat <<EOF > ${topdir}/SPECS/jenkins-plugin-${PLUGIN_NAME}.spec
%global plugin_name ${PLUGIN_NAME}

Summary:    ${PLUGIN_SUMMARY}
Name:       jenkins-plugin-%{plugin_name}
Version:    ${PLUGIN_VERSION}
Release:    1%{?dist}
License:    ASL 2.0
URL:        ${PLUGIN_URL}
Source0:    https://updates.jenkins-ci.org/download/plugins/%{plugin_name}/%{version}/%{plugin_name}.hpi
Requires:   jenkins >= ${target_jenkins_version}

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

    # Move in hpi
    rm -f ${topdir}/SOURCES/${PLUGIN_NAME}.hpi   # If we are updating an existing dist-git, remove old hpi
    cp -f ${hpi} ${topdir}/SOURCES/

    ## Update spec file
    cd ${topdir}/SPECS
    # Remove Requires: jenkins-plugin
    sed -i '/^Requires:.*jenkins-plugin.*/d' jenkins-plugin-${PLUGIN_NAME}.spec

    # Add in new Requires: jenkins-plugin
    IFS=',' read -a array <<< "${PLUGIN_DEPS}"
    for d in "${array[@]}"; do
        plugin="$(cut -d':' -f1 - <<< "$d")"
        if [[ $d == *"resolution:=optional"* ]]; then
            echo "  Skipping optional dependency $plugin"
        else
            sed -i "s/^Requires:.*jenkins .*/&\nRequires:   jenkins-plugin-${plugin}/" jenkins-plugin-${PLUGIN_NAME}.spec
        fi
    done

    # Update Version, Jenkins Release, and Changelog
    sed -i "s|^Version: .*|Version:    ${PLUGIN_VERSION}|" jenkins-plugin-${PLUGIN_NAME}.spec
    sed -i "s|^Release: .*|Release:    0%{?dist}|" jenkins-plugin-${PLUGIN_NAME}.spec
    sed -i "s|^Requires:   jenkins >=.*|Requires:   jenkins >= ${target_jenkins_version}|" jenkins-plugin-${PLUGIN_NAME}.spec
    rpmdev-bumpspec -u "Sam Munilla+smunilla@redhat.com" --comment="Update to ${PLUGIN_VERSION}" jenkins-plugin-${PLUGIN_NAME}.spec
    ## END: Update spec file

    ## Lets build the new package, if we can
    echo "Dependencies finished for ${PLUGIN_NAME}-${PLUGIN_VERSION}"
    echo

    # Create src.rpm
    NEW_SRPM=`rpmbuild -bs --define "_topdir ${topdir}" jenkins-plugin-${PLUGIN_NAME}.spec | grep Wrote: | awk '{print $2}'`

    # Build package in brew
    cd ${workingdir}
    echo "  Checking if a dist-git repo has been created ...."
    rhpkg "${USER_INFO}" clone jenkins-plugin-${PLUGIN_NAME} > /dev/null 2>&1
    if [ "$?" == "0" ] ; then
        cd jenkins-plugin-${PLUGIN_NAME}
        echo "    dist-git repo has been created."
        echo
        echo "  Checking if a dist-git branch has been created ...."
        rhpkg switch-branch rhaos-${rhaos_release}-rhel-7 > /dev/null 2>&1
        if [ "$?" == "0" ] ; then
            echo "    dist-git branch has been created."
            echo
        else
            echo
            echo "    There is no dist-git branch rhaos-${rhaos_release}-rhel-7 for jenkins-plugin-${PLUGIN_NAME}"
            echo "    You will need to request this branch be created before you can build this RPM."
            echo
            echo "NeedBranch: jenkins-plugin-${PLUGIN_NAME} Branch: rhaos-${rhaos_release}-rhel-7" >> ${request_file}
            read -p "Press enter to continue (the plugin for this RPM will be skipped and can be retried after the repo/branch is established)"
            continue
        fi
    else
        echo "    There is no dist-git repo for jenkins-plugin-${PLUGIN_NAME}"
        echo "    You will need to request this repo be created before you can build this RPM."
        echo
        echo "NeedRepo: jenkins-plugin-${PLUGIN_NAME} Branch: rhaos-${rhaos_release}-rhel-7" >> ${request_file}
        read -p "Press enter to continue (the plugin for this RPM will be skipped and can be retried after the repo/branch is established)"
        continue
    fi

    echo "  BUILDING: jenkins-plugin-${PLUGIN_NAME}-${PLUGIN_VERSION}"
    echo

    rhpkg "${USER_INFO}" import --skip-diffs ${NEW_SRPM} > /dev/null 2>&1

    if [ "$?" != "0" ]; then
        echo "Error importing srpm"
        exit 1
    fi

    rhpkg "${USER_INFO}" commit -p -m "Update to ${PLUGIN_VERSION}" > /dev/null 2>&1

    if [ "$?" != "0" ]; then
        echo "Error committing to dist-git"
        exit 1
    fi

    rhpkg "${USER_INFO}" build

    if [ "$?" != "0" ]; then
        echo "Error during build"
        exit 1
    fi

    # Make sure that no previous build with a greater version gets precedence over what we just built
    brew untag-build rhaos-${rhaos_release}-rhel-7-candidate jenkins-plugin-${PLUGIN_NAME} --non-latest

    # cleanup
    rm -rf ${workingdir}

done

if [ -f "${request_file}" ]; then
    echo "You need to work with RCM to finish this task..."
    cat "${request_file}"
    exit 1
fi
