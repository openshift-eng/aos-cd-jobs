PLASHET_REMOTE_URL = "http://download.eng.bos.redhat.com/rcm-guest/puddles/RHAOS/plashets"
PLASHET_REMOTE_HOST = "ocp-build@rcm-guest.app.eng.bos.redhat.com"
PLASHET_REMOTE_BASE_DIR = "/mnt/rcm-guest/puddles/RHAOS/plashets"

TARBALL_SOURCES_REMOTE_HOST = "ocp-build@rcm-guest.app.eng.bos.redhat.com"
TARBALL_SOURCES_REMOTE_BASE_DIR = "/mnt/rcm-guest/ocp-client-handoff"

OPERATOR_URL = 'registry-proxy.engineering.redhat.com/rh-osbs/openshift-ose-operator-sdk'
BREW_SERVER = 'https://brewhub.engineering.redhat.com/brewhub'

RELEASE_IMAGE_REPO = "quay.io/openshift-release-dev/ocp-release"

GIT_AUTHOR = "AOS Automation Release Team <noreply@redhat.com>"

NIGHTLY_PAYLOAD_REPOS = {
    "x86_64": "registry.ci.openshift.org/ocp/release",
    "s390x": "registry.ci.openshift.org/ocp-s390x/release-s390x",
    "ppc64le": "registry.ci.openshift.org/ocp-ppc64le/release-ppc64le",
    "aarch64": "registry.ci.openshift.org/ocp-arm64/release-arm64",
}

OCP_BUILD_DATA_URL = 'https://github.com/openshift-eng/ocp-build-data'
