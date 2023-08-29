FROM registry.access.redhat.com/ubi9/ubi:9.2 AS builder

# Install build dependencies
WORKDIR /usr/local/src
USER root
RUN dnf -y install python3 python3-pip python3-wheel python3-devel gcc krb5-devel wget tar gzip git

# Download oc
ARG OC_VERSION=latest
RUN wget -O "openshift-client-linux-${OC_VERSION}.tar.gz" "https://mirror.openshift.com/pub/openshift-v4/$(arch)/clients/ocp/${OC_VERSION}/openshift-client-linux.tar.gz" \
  && tar -xzvf "openshift-client-linux-$OC_VERSION.tar.gz" oc kubectl

# Build pyartcd, elliott, and doozer
COPY pyartcd pyartcd
COPY art-tools art-tools
RUN python3 -m pip wheel --wheel-dir /usr/local/src/wheels \
  ./art-tools/elliott ./art-tools/doozer ./pyartcd

FROM registry.access.redhat.com/ubi9/ubi:9.2
LABEL name="openshift-art/art-cd" \
  maintainer="OpenShift Team Automated Release Tooling <aos-team-art@redhat.com>"

# Trust Red Hat IT Root CA certificates
RUN curl -fLo /etc/pki/ca-trust/source/anchors/2022-IT-Root-CA.pem https://certs.corp.redhat.com/certs/2022-IT-Root-CA.pem \
  && curl -fLo /etc/pki/ca-trust/source/anchors/2015-IT-Root-CA.pem https://certs.corp.redhat.com/certs/2015-IT-Root-CA.pem \
  && curl -fLo /etc/pki/ca-trust/source/anchors/RH-IT-Root-CA.crt https://certs.corp.redhat.com/certs/RH-IT-Root-CA.crt \
 && update-ca-trust extract

# Install runtime dependencies
COPY ./tekton-pipelines/images/artcd/files/ /
RUN \
  # Configure Python environment
  dnf -y install python3 python3-pip \
  # Other tools
  && dnf -y install git brewkoji rhpkg krb5-workstation \
  # Clean up
  && dnf clean all

# Install oc
COPY --from=builder /usr/local/src/oc /usr/local/src/kubectl /usr/local/bin/

# Install pyartcd, elliott, doozer
COPY --from=builder /usr/local/src/wheels /usr/local/src/wheels
RUN python3 -m pip install --ignore-installed --no-index --find-links=/usr/local/src/wheels pyartcd rh-elliott rh-doozer \
  && rm /usr/local/src/wheels/*.whl \
  # Make python-certifi trust system CA certificates
  && python3 -m pip install pip_system_certs

# Set up user
RUN useradd -m -d /home/dev -u 1000 dev
USER 1000
WORKDIR /home/dev
