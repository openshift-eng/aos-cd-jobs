#!/usr/bin/env python
import glob
import re
import sys


def main(filename):
    configs = glob.glob('sjb/config/test_cases/*.yml') \
        + glob.glob('sjb/config/common/test_cases/*.yml')
    children(filename, configs, {c: parent(c) for c in configs})


def parent(filename):
    with open(filename, 'r') as f:
        for line in f:
            match = re.match(r"^parent: '([^']+)'$", line)
            if match:
                return 'sjb/config/' + match.group(1)


def children(filename, configs, parents):
    for config in configs:
        if parents.get(config) == filename:
            print(config)
            children(config, configs, parents)


if __name__ == '__main__':
    main(*sys.argv[1:])
