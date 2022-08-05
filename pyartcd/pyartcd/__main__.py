from typing import Optional, Sequence

from pyartcd.cli import cli
from pyartcd.pipelines import (prepare_release, promote, rebuild,
                               tarball_sources, check_bugs, sweep, report_rhcos, gen_assembly)


def main(args: Optional[Sequence[str]] = None):
    cli()
