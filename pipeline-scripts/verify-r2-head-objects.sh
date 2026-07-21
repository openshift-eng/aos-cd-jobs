#!/bin/bash
# Re-checks files flagged by `aws s3 sync --dryrun` against Cloudflare R2 using HeadObject.
#
# `aws s3 sync --dryrun` determines mismatches via ListObjectsV2. On Cloudflare R2, that
# listing can lag behind the object store itself for a period of time after an upload,
# even though HeadObject/GetObject already reflect the correct, current object. This
# produces false-positive "missing or size mismatch" verification failures.
#
# Reads dryrun output lines from the file given as $1 (one per line, in the format
# produced by `aws s3 sync --dryrun`) and prints only the lines that are still genuinely
# mismatched after directly re-checking the object via HeadObject.
set -euo pipefail

dryrun_file="$1"
bucket="art-srv-enterprise"

while IFS= read -r line; do
    case "$line" in
        "(dryrun) upload:"*)
            local_path=$(echo "$line" | sed -E 's/^\(dryrun\) upload: //; s/ to s3:\/\/.*$//')
            key=$(echo "$line" | sed -E 's#.* to s3://[^/]+/##')
            # -L dereferences symlinks so the target's size is reported, not the link's own size.
            local_size=$(stat -Lc%s "$local_path" 2>/dev/null || stat -Lf%z "$local_path" 2>/dev/null || echo -1)
            remote_size=$(aws s3api head-object --bucket "$bucket" --key "$key" \
                --profile cloudflare --endpoint-url "${CLOUDFLARE_ENDPOINT}" \
                --query ContentLength --output text 2>/dev/null || echo MISSING)
            if [ "$remote_size" != "$local_size" ]; then
                echo "${line} (head-object confirms: local=${local_size} remote=${remote_size})"
            fi
            ;;
        *)
            # Any other dryrun action (e.g. an unexpected extra remote file staged for
            # deletion) can't be disambiguated by a HeadObject check -- treat as a real mismatch.
            echo "$line"
            ;;
    esac
done < "$dryrun_file"
