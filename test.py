import asyncio
import yaml

from pyartcd.util import branch_arches


async def get_arches_2():
    return await branch_arches('openshift-4.12', 'stream')


if __name__ == '__main__':
    arches = asyncio.get_event_loop().run_until_complete(get_arches_2())
    print(yaml.safe_dump(arches))
    print(type(arches))
