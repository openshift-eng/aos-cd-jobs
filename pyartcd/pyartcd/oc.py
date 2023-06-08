import json
import os
import logging
from pyartcd import exectools
from pyartcd.runtime import Runtime
import openshift as octool
from typing import List, Optional


logger = logging.getLogger(__name__)


async def get_release_image_info(pullspec: str, raise_if_not_found: bool = False):
    cmd = ["oc", "adm", "release", "info", "-o", "json", "--", pullspec]
    env = os.environ.copy()
    env["GOTRACEBACK"] = "all"
    rc, stdout, stderr = await exectools.cmd_gather_async(cmd, check=False, env=env)
    if rc != 0:
        if "not found: manifest unknown" in stderr or "was deleted or has expired" in stderr:
            # release image doesn't exist
            if raise_if_not_found:
                raise IOError(f"Image {pullspec} is not found.")
            return None
        raise ChildProcessError(f"Error running {cmd}: exit_code={rc}, stdout={stdout}, stderr={stderr}")
    info = json.loads(stdout)
    if not isinstance(info, dict):
        raise ValueError(f"Invalid release info: {info}")
    return info


async def registry_login(runtime: Runtime):
    try:
        await exectools.cmd_gather_async(
            f'oc --kubeconfig {os.environ["KUBECONFIG"]} registry login')

    except KeyError:
        runtime.logger.error('KUBECONFIG env var must be defined!')
        raise

    except ChildProcessError:
        runtime.logger.error('Failed to login into OC registry')
        raise


def common_oc_wrapper(cmd_result_name: str, cli_verb: str, oc_args: List[str], check_status: bool = True, return_value: bool = False) -> (int, str):
    # cmd_result_name: Result obj name in log
    # cli_verb: first command group
    # oc_args: args list of command
    # check_status: whether check status and print output in log
    # return_value: whether need return value sets
    logger.info(f"run: oc {cli_verb} {' '.join(oc_args)}")
    with octool.tracking() as tracker:
        try:
            r = octool.Result(cmd_result_name)
            r.add_action(octool.oc_action(octool.cur_context(), cli_verb, cmd_args=oc_args))
            if check_status:
                if r.status() == 0:
                    logger.debug(f"Output: {r.out().strip()}")
                else:
                    logger.warn(f"oc command exited with error: {r.err()}")
            r.fail_if(f"oc action {cmd_result_name} failed")
        except Exception as e:
            logger.error(tracker.get_result())
            raise e
    if return_value:
        return r.status(), r.out().strip()


def get_release_image_info_from_pullspec(pullspec: str) -> (int, str):
    # oc image info --output=json <pullspec>
    cmd_args = ['info', "--output=json", pullspec]
    res, out = common_oc_wrapper("single_image_info", "image", cmd_args, True, True)
    return res, json.loads(out)


def extract_release_binary(image_pullspec: str, path_args: List[str]) -> (int, str):
    # oc image extract --confirm --only-files --path=/usr/bin/..:<workdir> <pullspec>
    cmd_args = ['extract', '--confirm', '--only-files'] + path_args + [image_pullspec]
    common_oc_wrapper("extract_image", "image", cmd_args, True, False)


def get_release_image_pullspec(release_pullspec: str, image: str) -> (int, str):
    # oc adm release info --image-for=<image> <pullspec>
    cmd_args = ['release', 'info', f'--image-for={image}', release_pullspec]
    return common_oc_wrapper("image_info_in_release", "adm", cmd_args, True, True)


def extract_release_client_tools(release_pullspec: str, path_arg: str, single_arch: Optional[str] = None) -> (int, str):
    # oc adm release extract --tools --command-os=* -n ocp --to=<workdir> --filter-by-os=<arch> --from <pullspec> --to <path>
    args = ["release", "extract", "--tools", "--command-os=*", "-n=ocp"]
    if single_arch:
        args += [f"--filter-by-os={single_arch}"]
    args += [f"--from={release_pullspec}", path_arg]
    common_oc_wrapper("extract_tools", "adm", args, True, False)
