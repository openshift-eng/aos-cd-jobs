oct provision remote all-in-one --os "rhel" --stage "base" --provider "aws" --discrete-ssh-config --name "$JOB_NAME"_"$BUILD_NUMBER"
rm -rf ~/continuous-upgrade
mkdir -p ~/continuous-upgrade
cp -fr ./.config/origin-ci-tool ~/continuous-upgrade/
tree ~/continuous-upgrade/
cat ~/continuous-upgrade/origin-ci-tool/inventory/.ssh_config
