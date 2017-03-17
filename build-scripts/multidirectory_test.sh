#!/bin/sh
set -eu

create_test_repos() {
    git init --quiet --bare origin.git
    git init --quiet init/
    cd init/
    git commit --quiet --allow-empty --message first
    git push --quiet ../origin.git master
    cd -> /dev/null
    git clone --quiet origin.git/ setup/
}

branches() {
    (
        cd setup/
        master_rev=$(git rev-parse --short master)
        for x; do
            git checkout --quiet --orphan "$x"
            git reset
            git clean --quiet -df
            > Jenkinsfile
            git add Jenkinsfile
            git commit --quiet \
                --message "Auto-generated from $master_rev:jobs/$x"
        done
        git checkout --quiet master
    )
}

jobs() {
    (
        cd setup/
        for x; do mkdir -p "jobs/$x"; > "jobs/$x/Jenkinsfile"; done
        git add .
        git commit --quiet --message "$x: jobs"
    )
}

expected_branches() {
    (IFS=$(printf '\n ') && echo "$*" > expected_branches.txt)
}

execute_test() {
    local branches x
    (cd setup/ && git push --quiet --all)
    git clone --quiet origin.git/ work/
    (cd work/ && "$MULTIDIRECTORY_SH")
    git clone --quiet origin.git/ check/
    cd check/
    branches=$(git ls-remote --heads origin \
        | awk '{print gensub("^refs/heads/", "", 1, $2)}')
    echo "$branches" | diff -u ../expected_branches.txt -
    branches=$(echo "$branches" | { grep -x / || true; })
    for x in $branches; do
        ls "jobs/$x/Jenkinsfile" > /dev/null
        (find * ! \( -wholename jobs -a -prune \) && cd "jobs/$x" && find *) \
            | sort > ../expected_files.txt
        git ls-tree -tr --name-only "origin/$x" \
            | sort \
            | diff -u ../expected_files.txt -
        echo "Auto-generated from $(git rev-parse --short master):jobs/$x" \
            > ../expected_message.txt
        git show --format=%s --no-patch "origin/$x" \
            | diff -u ../expected_message.txt -
    done
    cd -> /dev/null
}

# No jobs/branches.
test0() {
    create_test_repos
    expected_branches master
    execute_test
}

# Directories under jobs/ with no Jenkinsfile.
test1() {
    create_test_repos
    mkdir -p jobs/build jobs/cluster
    expected_branches master
    execute_test
}

# A job without a branch.
test2() {
    create_test_repos
    jobs build/ose
    expected_branches build/ose master
    execute_test
}

# Another job without a branch.
test3() {
    create_test_repos
    jobs cluster/dev-preview-int/install
    expected_branches cluster/dev-preview-int/install master
    execute_test
}

# Multiple jobs without branches.
test4() {
    create_test_repos
    jobs \
        build/ose build/ose-pipeline \
        cluster/dev-preview-int/install cluster/cicd-test
    expected_branches \
        build/ose build/ose-pipeline \
        cluster/cicd-test cluster/dev-preview-int/install master
    execute_test
}

# A branch without '/' in its name.
test5() {
    create_test_repos
    (cd setup/ && git branch build-scripts)
    expected_branches build-scripts master
    execute_test
}

# A branch without a job.
test6() {
    create_test_repos
    branches build/ose
    expected_branches master
    execute_test
}

# Multiple branches without jobs.
test7() {
    create_test_repos
    branches build/ose cluster/dev-preview-int/install
    expected_branches master
    execute_test
}

# Multiple branches without jobs, multiple jobs without branches.
test8() {
    create_test_repos
    branches build/ose cluster/dev-preview-int/install
    jobs build/ose-pipeline cluster/cicd-test
    expected_branches build/ose-pipeline cluster/cicd-test master
    execute_test
}

# Jobs with up-to-date branches.
test9() {
    local shas
    create_test_repos
    jobs build/ose cluster/dev-preview-int/install
    branches build/ose cluster/dev-preview-int/install
    expected_branches build/ose cluster/dev-preview-int/install master
    shas=$(cd setup/ \
        && git rev-parse build/ose cluster/dev-preview-int/install)
    execute_test
    echo "$shas" > expected_shas.txt
    (
        cd origin.git
        git rev-parse build/ose cluster/dev-preview-int/install \
            | diff -u ../expected_shas.txt -
    )
}

# Jobs with not-up-to-date branches.
test10() {
    local shas
    create_test_repos
    branches build/ose cluster/dev-preview-int/install
    shas=$(cd setup/ \
        && git rev-parse build/ose cluster/dev-preview-int/install)
    jobs build/ose cluster/dev-preview-int/install
    expected_branches build/ose cluster/dev-preview-int/install master
    execute_test
    echo "$shas" > unexpected_shas.txt
    (
        cd origin.git
        git rev-parse build/ose cluster/dev-preview-int/install \
            | { grep -xf ../unexpected_shas.txt - || exit 0 && exit 1; }
    )
}

# Extra files in the repository.
test11() {
    create_test_repos
    branches build/ose
    jobs build/ose cluster/dev-preview-int
    expected_branches build/ose cluster/dev-preview-int master
    (
        cd setup/ \
            && mkdir build-scripts/ \
            && > build-scripts/multidirectory.sh \
            && git add build-scripts/ \
            && git commit --quiet --message 'extra files'
    )
    execute_test
}

# Rerun.
test12() {
    create_test_repos
    jobs build/ose cluster/dev-preview-int
    expected_branches build/ose cluster/dev-preview-int master
    execute_test
    git ls-remote --heads "$PWD/origin.git/" > expected_output.txt
    rm -rf setup/ work/ check/
    git clone --quiet origin.git/ setup/
    execute_test
    git ls-remote --heads "$PWD/origin.git/" \
        | diff -u expected_output.txt -
}

MULTIDIRECTORY_SH=$(realpath "$(dirname "$0")/multidirectory.sh")
GIT_AUTHOR_NAME=test
GIT_AUTHOR_EMAIL=test@example.com
GIT_COMMITTER_NAME=$GIT_AUTHOR_NAME
GIT_COMMITTER_EMAIL=$GIT_AUTHOR_EMAIL
export GIT_AUTHOR_NAME GIT_AUTHOR_EMAIL GIT_COMMITTER_NAME GIT_COMMITTER_EMAIL
test_dir=$PWD/tests
rm -rf "$test_dir"
[ "$#" -gt 0 ] || set -- $(seq -f 'test%.0f' 0 12)
for x; do
    echo "$x"
    mkdir -p "$test_dir/$x"
    set +e
    (set -e; cd "$test_dir/$x"; "$x")
    [ "$?" -eq 0 ] || failed=1
    set -e
done
[ ! "${failed:-}" ]
