go get github.com/openshift/imagebuilder/cmd/imagebuilder

export OS_BUILD_IMAGE_ARGS=''
hack/build-base-images.sh
make release
JUNIT_REPORT='true' make test-extended SUITE=conformance