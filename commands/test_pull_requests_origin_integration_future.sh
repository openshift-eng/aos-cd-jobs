go get github.com/openshift/imagebuilder/cmd/imagebuilder

export OS_BUILD_IMAGE_ARGS=''
hack/build-base-images.sh
make release
OPENSHIFT_SKIP_BUILD=1 JUNIT_REPORT='true' make test -o check -k