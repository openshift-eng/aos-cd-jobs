from typing import Optional, Sequence

from pyartcd.cli import cli
from pyartcd.pipelines import prepare_release, rebuild


def main(args: Optional[Sequence[str]] = None):
    cli()
