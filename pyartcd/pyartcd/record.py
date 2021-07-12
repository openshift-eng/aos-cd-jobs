from typing import Dict, List, Optional, TextIO


def parse_record_log(file: TextIO) -> Dict[str, List[Dict[str, Optional[str]]]]:
    """
    Parse record.log from Doozer into a dict.
    The dict will be keyed by the type of operation performed.
    The values will be a list of dicts. Each of these dicts will contain the attributes for a single recorded operation of the top
    level key's type.
    """
    result = {}
    for line in file:
        fields = line.rstrip().split("|")
        type = fields[0]
        record = {entry_split[0]: entry_split[1] if len(entry_split) > 1 else None for entry_split in map(lambda entry: entry.split("=", 1), fields[1:]) if entry_split[0]}
        result.setdefault(type, []).append(record)
    return result
