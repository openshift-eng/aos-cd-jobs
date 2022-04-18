from typing import Optional, Sequence

from pyartcd.cli import cli
from pyartcd.pipelines import (check_bugs, poll_for_prs, prepare_release,
                               promote, pyartcd_unittest, rebuild, sweep,
                               tarball_sources)


def main(args: Optional[Sequence[str]] = None):
    cli()
