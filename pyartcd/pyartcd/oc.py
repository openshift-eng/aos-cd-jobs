import json
import os

from pyartcd import exectools
from pyartcd.runtime import Runtime


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
