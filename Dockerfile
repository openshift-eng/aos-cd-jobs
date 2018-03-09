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
ENV JOB_SPEC '{"type":"presubmit","job":"test_pull_request_openshift_ansible_logging_37","buildid":"e9ef0abe-22e7-11e8-80e2-0a58ac100e53","refs":{"org":"openshift","repo":"openshift-ansible","base_ref":"release-3.7","base_sha":"10251ac2b0f0172c9fcefa4de3b265fe6c0ca507","pulls":[{"number":7360,"author":"vrutkovs","sha":"49d7822fea0c4bccce6c80cd027517c9a222211b"}]}}'
ENV buildId 'e9ef0abe-22e7-11e8-80e2-0a58ac100e53'
ENV BUILD_ID 'e9ef0abe-22e7-11e8-80e2-0a58ac100e53'
ENV REPO_OWNER 'openshift'
ENV REPO_NAME 'openshift-ansible'
ENV PULL_BASE_REF 'release-3.7'
ENV PULL_BASE_SHA '10251ac2b0f0172c9fcefa4de3b265fe6c0ca507'
ENV PULL_REFS 'release-3.7:10251ac2b0f0172c9fcefa4de3b265fe6c0ca507,7360:49d7822fea0c4bccce6c80cd027517c9a222211b'
ENV PULL_NUMBER '7360'
ENV PULL_PULL_SHA '49d7822fea0c4bccce6c80cd027517c9a222211b'
ENV CLONEREFS_ARGS ''
# env
ENV WORKSPACE /code
ENV JOB_NAME "vrutkovs"
ENV TEST "test_pull_request_openshift_ansible_extended_conformance_install"

ADD . /code
WORKDIR /code
RUN chmod +x entrypoint.sh

CMD ["/code/entrypoint.sh"]
