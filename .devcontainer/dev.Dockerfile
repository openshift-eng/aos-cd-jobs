FROM fedora:34

# Trust the Red Hat IT Root CA and set up rcm-tools repo
RUN curl -o /etc/pki/ca-trust/source/anchors/RH-IT-Root-CA.crt --fail -L \
         https://password.corp.redhat.com/RH-IT-Root-CA.crt \
 && update-ca-trust extract \
 && curl -o /etc/yum.repos.d/rcm-tools-fedora.repo \
         https://download.devel.redhat.com/rel-eng/RCMTOOLS/rcm-tools-fedora.repo

RUN dnf install -y \
    # runtime dependencies
    krb5-workstation git tig rsync koji skopeo podman rpmdevtools \
    python3 python3-certifi python3-rpm python3-kobo-rpmlib  \
    # development dependencies
    gcc krb5-devel \
    python3-devel python3-pip python3-wheel \
    # other tools for development and troubleshooting
    bash-completion vim tmux procps-ng psmisc wget net-tools iproute socat \
    # install rcm-tools
    koji brewkoji rhpkg \
  # clean up
  && dnf clean all \
  # make "python" available
  && ln -sfn /usr/bin/python3 /usr/bin/python \
  # install aws cli
  && python -m pip install awscli


ARG OC_VERSION=latest
RUN wget -O /tmp/openshift-client-linux-"$OC_VERSION".tar.gz https://mirror.openshift.com/pub/openshift-v4/clients/ocp/"$OC_VERSION"/openshift-client-linux.tar.gz \
  && tar -C /usr/local/bin -xzf  /tmp/openshift-client-linux-"$OC_VERSION".tar.gz oc kubectl \
  && rm /tmp/openshift-client-linux-"$OC_VERSION".tar.gz


# Create a non-root user - see https://aka.ms/vscode-remote/containers/non-root-user.
ARG USERNAME=dev
# On Linux, replace with your actual UID, GID if not the default 1000
ARG USER_UID=1000
ARG USER_GID=$USER_UID

# Create the "dev" user
RUN groupadd --gid "$USER_GID" "$USERNAME" \
    && useradd --uid "$USER_UID" --gid "$USER_GID" -m "$USERNAME" \
    && mkdir -p /workspaces/{aos-cd-jobs,aos-cd-jobs-working} \
    && chown -R "${USER_UID}:${USER_GID}" /home/"$USERNAME" /workspaces \
    && chmod 0755 /home/"$USERNAME" \
    && echo "$USERNAME" ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/"$USERNAME" \
    && chmod 0440 /etc/sudoers.d/"$USERNAME"

# Preinstall dependencies
COPY ./ /tmp/aos-cd-jobs/
RUN chown "$USERNAME" -R /tmp/aos-cd-jobs \
 && pushd /tmp/aos-cd-jobs/pyartcd \
 && sudo -u "$USERNAME" pip3 install --user -r ./requirements.txt -r ./requirements-dev.txt ./ \
 && popd && rm -rf /tmp/aos-cd-jobs

USER "$USER_UID"
WORKDIR /workspaces/aos-cd-jobs
