FROM registry.access.redhat.com/ubi8/ubi:8.3
LABEL name="openshift-art/art-cd" \
  maintainer="OpenShift Team Automated Release Tooling <aos-team-art@redhat.com>"

# trust Red Hat IT Root CA
RUN curl -o /etc/pki/ca-trust/source/anchors/RH-IT-Root-CA.crt --fail -L \
         https://password.corp.redhat.com/RH-IT-Root-CA.crt \
 && update-ca-trust extract

# install Python
RUN dnf module install -y python36 \
  && python3 -m pip install "pip >= 19"

#  RPM_PY_SYS=true
  # https://github.com/aio-libs/aiohttp/issues/5390
  # && pip3 install chardet==3.0.3 \
# install runtime dependencies
COPY ./tekton-pipelines/images/artcd/files/ /
RUN dnf install -y python36-devel \
  python3-wheel \
  gcc \
  git \
  krb5-devel \
  krb5-workstation \
  openssl-devel \
  rpm-devel \
  wget \
  koji \
  rhpkg

# install oc
ARG OC_VERSION=latest
RUN wget -O /tmp/openshift-client-linux-"$OC_VERSION".tar.gz https://mirror.openshift.com/pub/openshift-v4/x86_64/clients/ocp/"$OC_VERSION"/openshift-client-linux.tar.gz \
  && tar -C /usr/local/bin -xzf  /tmp/openshift-client-linux-"$OC_VERSION".tar.gz oc kubectl \
  && rm /tmp/openshift-client-linux-"$OC_VERSION".tar.gz

# install elliott, doozer, and pyartcd
COPY ./art-tools/ /usr/local/src/
COPY ./pyartcd/ /usr/local/src/pyartcd/
RUN pushd /usr/local/src/ \
  && pip3 wheel --wheel-dir /usr/local/src/wheels --use-deprecated=legacy-resolver --no-deps ./elliott ./doozer ./pyartcd
RUN python3 -m pip install --ignore-installed /usr/local/src/wheels/*.whl \
  # make Python trust system CA certificates
  && python3 -m pip install certifi && ln -sf /etc/pki/tls/cert.pem /usr/local/lib/python3.6/site-packages/certifi/cacert.pem
