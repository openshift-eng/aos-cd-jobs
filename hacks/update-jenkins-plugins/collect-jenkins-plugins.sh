#!/bin/bash

usage() {
    echo >&2
    echo "Usage `basename $0` <lowest-supported-jenkins-version> <path-to-plugins-list>" >&2
    echo "  Where path-to-plugins-list is a line delimited list of jenkins plugins to prepare." >&2
    echo "    Example entries:   workflow-aggregator:2.1" >&2
    echo "      or use latest:   workflow-aggregator:latest" >&2
    echo >&2
    echo " Example: ./collect-jenkins-plugins.sh  1.651.2  plugins.txt" >&2
    exit 1
}

# https://stackoverflow.com/questions/4023830/how-compare-two-strings-in-dot-separated-version-format-in-bash
vercomp () {
    if [[ $1 == $2 ]]
    then
        return 0
    fi
    local IFS=.
    local i ver1=($1) ver2=($2)
    # fill empty fields in ver1 with zeros
    for ((i=${#ver1[@]}; i<${#ver2[@]}; i++))
    do
        ver1[i]=0
    done
    for ((i=0; i<${#ver1[@]}; i++))
    do
        if [[ -z ${ver2[i]} ]]
        then
            # fill empty fields in ver2 with zeros
            ver2[i]=0
        fi
        if ((10#${ver1[i]} > 10#${ver2[i]}))
        then
            return 1
        fi
        if ((10#${ver1[i]} < 10#${ver2[i]}))
        then
            return 2
        fi
    done
    return 0
}

# e.g. testvercomp 3.2.1.9.8144     3.2          >
#   returns 0
testvercomp () {
    vercomp $1 $2
    case $? in
        0) op='=';;
        1) op='>';;
        2) op='<';;
    esac
    if [[ $op != $3 ]]
    then
        echo "FAIL: Expected '$3', Actual '$op', Arg1 '$1', Arg2 '$2'"
        return 1
    else
        return 0
    fi
}


# Make sure they passed something in for us
if [ "$#" -lt 2 ] ; then
  usage
fi

# set -o xtrace

JENKINS_VERSION="$1"
PLUGIN_LISTING="$(realpath $2)"


workingdir=$(dirname $(realpath $0))/working
rm -rf "${workingdir}"  # Remove old data

tmp_hpis_dir="${workingdir}/tmp_hpis"
hpis_dir="${workingdir}/hpis"
mkdir -p "${tmp_hpis_dir}" "${hpis_dir}"

DEP_LIST=""

get_plugin() {
    plugin_line="$1"

    echo
    echo
    echo "Processing plugin: ${plugin_line}"

    JENKINS_VERSION_OVERRIDE=""
    if [[ "$plugin_line" == *"jenkins-version-override"*  ]]; then
        JENKINS_VERSION_OVERRIDE="true"
    fi

    # Remove anything after the semicolon if it exists
    plugin_line=${plugin_line%\;*}

    plugin=$(echo "${plugin_line}:" | cut -d : -f 1)
    plugin_version=$(echo "${plugin_line}:" | cut -d : -f 2)

    if [ -z "${plugin_version}" -o "${plugin_version}" == "latest" ]; then
        plugin_url="https://updates.jenkins-ci.org/latest/${plugin}.hpi"
    else
        plugin_url="https://updates.jenkins-ci.org/download/plugins/${plugin}/${plugin_version}/${plugin}.hpi"
    fi
    tmp_hpi_file="${tmp_hpis_dir}/${plugin}.hpi"

    echo "Downloading plugin: ${plugin_url}"
    wget -O "${tmp_hpi_file}" "${plugin_url}" 2> /dev/null
    if [ "$?" != "0" ]; then
        echo "Error downloading ${plugin}; exiting"
        exit 1
    fi

    extract="${workingdir}/extracts/${plugin}"
    rm -rf "${extract}"
    mkdir -p ${extract}
    unzip "${tmp_hpi_file}" -d ${extract} > /dev/null

    pushd "${extract}"
        cat META-INF/MANIFEST.MF | tr -d '\r' | tr '\n' '|' | sed -e 's#| ##g' | tr '|' '\n' > META-INF/MANIFEST.MF.format
        PLUGIN_VERSION="$(grep Plugin-Version: META-INF/MANIFEST.MF.format | awk '{print $2}')"
        PLUGIN_JENKINS_VERSION="$(grep Jenkins-Version: META-INF/MANIFEST.MF.format | awk '{print $2}')"
        if [ "${JENKINS_VERSION_OVERRIDE}" == "true" ]; then
            PLUGIN_JENKINS_VERSION="${JENKINS_VERSION}"
        fi
        PLUGIN_URL="$(grep Url: META-INF/MANIFEST.MF.format | awk '{print $2}')"
        PLUGIN_DEPS="$(grep '^Plugin-Dependencies: ' META-INF/MANIFEST.MF.format | sed -e 's#^Plugin-Dependencies: ##')"
        PLUGIN_SUMMARY="$(grep Long-Name: META-INF/MANIFEST.MF.format |cut -d' ' -f2-)"
        PLUGIN_DESCRIPTION="$(grep Specification-Title: META-INF/MANIFEST.MF.format |cut -d' ' -f2-)"
        echo "     Plugin ${plugin} : ${PLUGIN_VERSION}"
        echo "       Jenkins Version ${PLUGIN_JENKINS_VERSION}"
        echo "       Dependencies: ${PLUGIN_DEPS}"
    popd

    PLUGIN_DEPS=$(echo "${PLUGIN_DEPS}" | tr "," " ")  # Space delimit dependencies

    hpi_file="${hpis_dir}/${plugin}.hpi"
    version_file="${tmp_hpis_dir}/${plugin}.version"

    if [ -f "${hpi_file}" ]; then
        existing_version="$(cat ${version_file})"

        if [ "${existing_version}" == "${PLUGIN_VERSION}" ]; then
            echo "Skipping already existing plugin: ${plugin}:${existing_version}"
            return 0
        fi

        # If the version is opinionated, let the human resolve it
        if [ ! -z "${plugin_version}" ]; then
            echo "Unable to resolve dependency version conflict: ${plugin}:${plugin_version} conflicts with existing ${existing_version}"
            return 1
        fi

        echo "Skipping already existing plugin: ${plugin}:${existing_version}"
        return 0
    fi

    testvercomp "${JENKINS_VERSION}" "${PLUGIN_JENKINS_VERSION}" ">" ||  testvercomp "${JENKINS_VERSION}" "${PLUGIN_JENKINS_VERSION}" "="
    if [[ "$?" == "0" ]]; then
        echo "Jenkins requirement satisfied... ${JENKINS_VERSION} >= ${PLUGIN_JENKINS_VERSION}"
    else
        echo "Plugin ${plugin_line} requires newer version of Jenkins (${PLUGIN_JENKINS_VERSION}); whereas you specified ${JENKINS_VERSION}"
        return 1
    fi

    echo "Plugin ${plugin} adding dependencies: ${PLUGIN_DEPS}"
    DEP_LIST="${DEP_LIST} ${PLUGIN_DEPS}"  # Keep a running total of dependencies

    mv "${tmp_hpi_file}" "${hpi_file}"
    echo -n "${PLUGIN_VERSION}" > "${version_file}"

}

# For each entry in the file (ignore whitespace lines and comment lines.
for plugin_line in $(cat "${PLUGIN_LISTING}" | grep -v -e '^[[:space:]]*$' | grep -v -e '^[[:space:]]*#.*$' ); do
    if [[ -z "${plugin_line}" ]]; then
        continue
    fi
    get_plugin "${plugin_line}" || exit 1
done

# Process dependencies after the fact so that specified versions take precedence.
for plugin_entry in ${DEP_LIST}; do
    echo "${plugin} dependency causing processing of ${plugin_entry}"

    # Some dependencies are of the form: "subversion:2.5;resolution:=optional"
    if [[ "$plugin_entry" == *"resolution:=optional"*  ]]; then
        echo "Skipping optional dependency: ${plugin_line}"
        continue
    fi

    # Remove anything after the semicolon if it exists
    plugin_line=${plugin_line%\;*}

    stripped_entry=$(echo "${plugin_entry}:" | cut -d : -f 1)  # Strip off the version since Jenkins doesn't really honor dependency versions
    get_plugin "${stripped_entry}" || exit 1
done

echo
echo
echo "Collected plugins in ${hpis_dir}:"
for vf in ${tmp_hpis_dir}/*.version; do
    plugin=$(basename -s .version "$vf")
    echo "${plugin}:$(cat $vf)"
done

exit 0

