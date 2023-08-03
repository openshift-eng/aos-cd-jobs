PLASHET_REMOTE_URL = "https://ocp-artifacts.hosts.prod.psi.rdu2.redhat.com/pub/RHOCP/plashets"
PLASHET_REMOTE_HOST = "ocp-artifacts"
PLASHET_REMOTE_BASE_DIR = "/mnt/data/pub/RHOCP/plashets"

SPMM_UTILS_REMOTE_HOST = "exd-ocp-buildvm-bot-prod@spmm-util"

OPERATOR_URL = 'registry-proxy.engineering.redhat.com/rh-osbs/openshift-ose-operator-sdk'
BREW_SERVER = 'https://brewhub.engineering.redhat.com/brewhub'
BREW_DOWNLOAD_SERVER = 'https://download.eng.bos.redhat.com/brewroot'
RELEASE_IMAGE_REPO = "quay.io/openshift-release-dev/ocp-release"

GIT_AUTHOR = "AOS Automation Release Team <noreply@redhat.com>"

NIGHTLY_PAYLOAD_REPOS = {
    "x86_64": "registry.ci.openshift.org/ocp/release",
    "s390x": "registry.ci.openshift.org/ocp-s390x/release-s390x",
    "ppc64le": "registry.ci.openshift.org/ocp-ppc64le/release-ppc64le",
    "aarch64": "registry.ci.openshift.org/ocp-arm64/release-arm64",
}

# Maps the name of a release component tag to the filename element to include
# when creating artifacts on mirror.openshift.com.
MIRROR_CLIENTS = {
    "cli": "openshift-client",
    "installer": "openshift-installer",
    "operator-registry": "opm",
}

OCP_BUILD_DATA_URL = 'https://github.com/openshift-eng/ocp-build-data'

# This is the URL that buildvm itself uses to resolve Jenkins
# It shall be used by jenkinsapi to start new builds
JENKINS_SERVER_URL = 'https://buildvm.hosts.prod.psi.bos.redhat.com:8443'

# This is the URL that humans behind a VPN use to browse Jenkins UI
# It shall be used to print clickable logs that redirect the user to the triggered job page
JENKINS_UI_URL = 'https://saml.buildvm.hosts.prod.psi.bos.redhat.com:8888'

MIRROR_BASE_URL = 'https://mirror.openshift.com'

UMB_BROKERS = {
    "prod": "stomp+ssl://umb.api.redhat.com:61612",
    "stage": "stomp+ssl://umb.stage.api.redhat.com:61612",
    "qa": "stomp+ssl://umb.qa.api.redhat.com:61612",
    "dev": "stomp+ssl://umb.dev.api.redhat.com:61612",
}
