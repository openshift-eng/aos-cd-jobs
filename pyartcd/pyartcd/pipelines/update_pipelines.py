import argparse
import sys
import subprocess
import pathlib
import logging


_LOGGER = logging.getLogger(__name__)


class UpdatePipelines:
    def __init__(self, working_dir: str, repo_url: str, revision: str) -> None:
        self.working_dir = pathlib.Path(working_dir)
        self.repo_url = repo_url
        self.revision = revision
        pass

    def run(self):
        local_repo = self.clone_repo()
        # local_repo = pathlib.Path("/Volumes/Workspaces/projects/openshift/aos-cd-jobs")
        self.apply_resources(local_repo)
        self.rebuild_images()

    def clone_repo(self):
        local_dir = self.working_dir / "aos-cd-jobs"
        local_dir.mkdir(parents=True)
        commands = [
            ["git", "init", str(local_dir)],
            [
                "git",
                "-C",
                str(local_dir),
                "remote",
                "add",
                "origin",
                self.repo_url,
            ],
            [
                "git",
                "-C",
                str(local_dir),
                "fetch",
                "origin",
                "--depth=1",
                self.revision,
            ],
            ["git", "-C", str(local_dir), "checkout", "FETCH_HEAD"],
            ["git", "-C", str(local_dir), "submodule", "update", "--init", "--depth=1"],
        ]
        for cmd in commands:
            _LOGGER.info("Running %s...", cmd)
            subprocess.run(
                cmd, check=True, universal_newlines=True, cwd=self.working_dir
            )
        return local_dir

    def apply_resources(self, repo: pathlib.Path):
        resource_base_dir = repo / "tekton-pipelines"
        excluded_dirs = {"secrets", "images"}
        for entry in resource_base_dir.iterdir():
            if not entry.is_dir() or entry.name in excluded_dirs:
                continue
            cmd = ["oc", "apply", "-f", str(entry.absolute())]
            subprocess.run(
                cmd, check=True, universal_newlines=True, cwd=self.working_dir
            )

    def rebuild_images(self, repo: pathlib.Path):
        cmd = ["oc", "start-build", "--follow" "artcd-image"]
        subprocess.run(cmd, check=True, universal_newlines=True, cwd=self.working_dir)
        cmd = ["oc", "start-build", "--follow" "smee-client-image"]
        subprocess.run(cmd, check=True, universal_newlines=True, cwd=self.working_dir)


def main(args):
    parser = argparse.ArgumentParser("update-pipelines")
    parser.add_argument(
        "--repo-url",
        default="git@github.com:openshift/aos-cd-jobs.git",
        help="the git repository URL to clone from",
    )
    parser.add_argument(
        "--revision", default="master", help="the git branch (tag, commit) to clone"
    )
    parser.add_argument(
        "-C", "--working-dir", default=".", help="set working directory"
    )
    opts = parser.parse_args(args)
    pipeline = UpdatePipelines(opts.working_dir, opts.repo_url, opts.revision)
    pipeline.run()


if __name__ == "__main__":
    exit(main(sys.argv[1:]))
