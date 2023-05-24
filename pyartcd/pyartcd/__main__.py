from typing import Optional, Sequence

from pyartcd.cli import cli
from pyartcd.pipelines import (
    build_microshift, check_bugs, gen_assembly, prepare_release, promote, rebuild, report_rhcos,
    review_cvp, tarball_sources, build_sync, build_rhcos, ocp4_scan, images_health, operator_sdk_sync,
    olm_bundle, ocp4, custom, scan_for_kernel_bugs, tag_rpms
)


def main(args: Optional[Sequence[str]] = None):
    cli()


if __name__ == "__main__":
    main()
