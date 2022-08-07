from typing import Optional, Sequence

from pyartcd.cli import cli
from pyartcd.pipelines import (prepare_release, promote, rebuild,
                               tarball_sources, check_bugs, sweep, report_rhcos, review_cvp)


def main(args: Optional[Sequence[str]] = None):
    cli()

if __name__ == "__main__":
    main()
