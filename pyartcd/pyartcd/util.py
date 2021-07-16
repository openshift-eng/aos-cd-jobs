import re
from typing import Optional


def isolate_el_version_in_release(release: str) -> Optional[int]:
    """
    Given a release field, determines whether is contains
    a RHEL version. If it does, it returns the version value as int.
    If it is not found, None is returned.
    """
    match = re.match(r'.*\.el(\d+)(?:\.+|$)', release)
    if match:
        return int(match.group(1))

    return None


def isolate_el_version_in_branch(branch_name: str) -> Optional[int]:
    """
    Given a distgit branch name, determines whether is contains
    a RHEL version. If it does, it returns the version value as int.
    If it is not found, None is returned.
    """
    match = re.fullmatch(r'.*rhel-(\d+).*', branch_name)
    if match:
        return int(match.group(1))

    return None
