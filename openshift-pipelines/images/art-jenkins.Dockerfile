FROM registry.access.redhat.com/openshift3/jenkins-2-rhel7:v3.11
USER root
RUN curl -sfL https://password.corp.redhat.com/RH-IT-Root-CA.crt \
    -o /etc/pki/ca-trust/source/anchors/RH-IT-Root-CA.crt ;\
    update-ca-trust
USER 1001
