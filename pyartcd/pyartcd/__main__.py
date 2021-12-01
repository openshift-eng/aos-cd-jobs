from typing import Optional, Sequence

from pyartcd.cli import cli
from pyartcd.pipelines import prepare_release, rebuild, tarball_sources


def main(args: Optional[Sequence[str]] = None):
    cli()
