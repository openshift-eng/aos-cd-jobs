# run commitchecker outside release container as it needs
# access to git; also explicitly force godeps verification
symbolic_ref="$( git symbolic-ref HEAD )"
branch="${symbolic_ref##refs/heads/}"
if [[ "${branch}" == "master" ]]; then
	RESTORE_AND_VERIFY_GODEPS=1 make verify-commits -j
fi

OS_BUILD_ENV_DOCKER_ARGS="-v /tmp/ci:/tmp " hack/env TEST_KUBE='true' JUNIT_REPORT='true' make check -j -k