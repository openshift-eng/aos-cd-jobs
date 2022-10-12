from typing import Optional, Sequence

from pyartcd.cli import cli
from pyartcd.pipelines import (build_microshift, check_bugs, prepare_release,
                               promote, rebuild, report_rhcos, review_cvp,
                               sweep, tarball_sources)


def main(args: Optional[Sequence[str]] = None):
    cli()


if __name__ == "__main__":
    main()
