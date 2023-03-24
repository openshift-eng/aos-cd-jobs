import json
import os
import logging
from pyartcd import exectools
from pyartcd.runtime import Runtime
import openshift as oc
from openshift import Result

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


def get_release_image_pullspec(release_pullspec: str, image: str):
    # oc adm release info --image-for=<image> <pullspec>
    with oc.tracking() as tracker:
        try:
            r = Result("adm")
            r.add_action(oc.oc_action(oc.cur_context(), 'adm', cmd_args=['release', 'info', f'--image-for={image}', release_pullspec]))
            if r.status() == 0:
                logger.info(f"Output: {r.out().strip()}")
            else:
                logger.warn(r.err())
        except Exception as e:
            logger.error(tracker.get_result())
            raise e
    return r.status(), r.out().strip()


def extract_release_binary(image_pullspec: str, path_args: list[str]):
    # oc image extract --confirm --only-files --path=/usr/bin/..:<workdir> <pullspec>
    with oc.tracking() as tracker:
        try:
            r = Result("image")
            r.add_action(oc.oc_action(oc.cur_context(), 'image', cmd_args=['extract', '--confirm', '--only-files'] + path_args + [image_pullspec]))
            r.fail_if("extract release binary failed")
        except Exception as e:
            logger.error(tracker.get_result())
            raise e


def extract_release_client_tools(release_pullspec: str, path_arg: str, arch: str):
    # oc adm release extract --tools --command-os='*' -n ocp --to=<workdir> --filter-by-os=<arch> --from <pullspec>
    with oc.tracking() as tracker:
        try:
            r = Result("tools")
            if arch:
                cmd_args = ["release", "extract", "--tools", "--command-os='*'", "-n=ocp", f"--filter-by-os={arch}", path_arg, release_pullspec]
            else:
                cmd_args = ["release", "extract", "--tools", "--command-os='*'", "-n=ocp", path_arg, release_pullspec]
            r.add_action(oc.oc_action(oc.cur_context(), 'adm', cmd_args))
            r.fail_if("extract release binary failed")
        except Exception as e:
            logger.error(tracker.get_result())
            raise e