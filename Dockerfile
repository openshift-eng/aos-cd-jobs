FROM centos:7

# oct deps
RUN yum update -y && \
    yum install -y epel-release && \
    yum install -y python2-pip python2-crypto python2-boto python2-boto3 git-core && \
    yum clean all

# oct
RUN pip install git+https://github.com/openshift/origin-ci-tool.git --process-dependency-links

# AWS creds
ADD .aws_credentials /root/.aws/credentials

# libra
ADD .libra.pem /var/lib/jenkins/.ssh/devenv.pem
RUN chmod 0600 /var/lib/jenkins/.ssh/devenv.pem

# Bootstrap
RUN oct bootstrap self

# Fake gcs creds
RUN mkdir -p /var/lib/jenkins/.config/gcloud/
RUN touch /var/lib/jenkins/.config/gcloud/gcs-publisher-credentials.json

# Fake venv
RUN mkdir -p /root/oct-venv/bin && \
    touch /root/oct-venv/bin/activate && \
    mkdir -p /root/origin-ci-tool && \
    ln -s /root/oct-venv /root/origin-ci-tool/latest

# oct
ENV ANSIBLE_ROLES_PATH /usr/lib/python2.7/site-packages/oct/ansible/oct/roles
# Job specific
ENV BUILD_NUMBER "41"
ENV JOB_SPEC '{"type":"presubmit","job":"test_pull_request_openshift_ansible_extended_conformance_install_system_containers_39","buildid":"b4fde4ea-4885-11e8-bde9-0a58ac1004b5","refs":{"org":"openshift","repo":"openshift-ansible","base_ref":"release-3.9","base_sha":"52a8a84d00bd0b27b9d82ce87febfb409f86775b","pulls":[{"number":8106,"author":"vrutkovs","sha":"78668485c896643140261078210d2cf151903e98"}]}}'
ENV buildId 'b4fde4ea-4885-11e8-bde9-0a58ac1004b5'
ENV BUILD_ID 'b4fde4ea-4885-11e8-bde9-0a58ac1004b5'
ENV REPO_OWNER 'openshift'
ENV REPO_NAME 'openshift-ansible'
ENV PULL_BASE_REF 'release-3.9'
ENV PULL_BASE_SHA '52a8a84d00bd0b27b9d82ce87febfb409f86775b'
ENV PULL_REFS 'release-3.9:52a8a84d00bd0b27b9d82ce87febfb409f86775b,8106:78668485c896643140261078210d2cf151903e98'
ENV PULL_NUMBER '8106'
ENV PULL_PULL_SHA '78668485c896643140261078210d2cf151903e98'
ENV CLONEREFS_ARGS ''
# env
ENV WORKSPACE /code
ENV JOB_NAME "vrutkovs"
ENV TEST "test_pull_request_openshift_ansible_extended_conformance_install_system_containers_39"

ADD . /code
WORKDIR /code
RUN chmod +x entrypoint.sh

CMD ["/code/entrypoint.sh"]
