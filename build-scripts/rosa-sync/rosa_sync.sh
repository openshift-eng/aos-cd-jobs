#!/bin/bash
# Credential checks must not expose keys through shell tracing or captured logs.
set +x
set -euo pipefail

# This script copies the us-east-1 AMI in the meta.json to the AWS account configured via the
# AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables, unless that account already
# has an AMI with the same name.
# The path to the meta.json file must be passed as the first parameter.
# An optional second parameter enables dry-run validation (defaults to false).
# Dry-run checks identity, EC2 reads, and CopyImage permission, even for an existing AMI.
 
error-exit() {
    echo "Error: $*" >&2
    exit 1
}

copy_ami() {
    if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
        error-exit "Usage: rosa_sync.sh META_JSON [true|false]"
    fi

    if ! [ -x "$(command -v aws)" ]; then
        error-exit awscli command not found
    fi

    if [ -z "${AWS_ACCESS_KEY_ID:-}" ]; then
        error-exit \$AWS_ACCESS_KEY_ID is empty
    fi
    
    if [ -z "${AWS_SECRET_ACCESS_KEY:-}" ]; then
        error-exit \$AWS_SECRET_ACCESS_KEY is empty
    fi

    # For ROSA, each released RHCOS AMI has to be synced to the us-east-1 region only.
    # It will be replicated to other regions from there using the AWS Marketplace API.
    local AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION:-us-east-1}
    local META_JSON_PATH="$1"
    local DRY_RUN="${2:-false}"
    [[ "$DRY_RUN" == true || "$DRY_RUN" == false ]] || error-exit "Dry-run must be true or false"

    local ami ami_name existing_ami
    ami=$(jq -er '[.amis[] | select(.name == "us-east-1")][0].hvm // empty' "$META_JSON_PATH")
    [[ "$ami" =~ ^ami-[0-9a-f]+$ ]] || error-exit "No valid us-east-1 AMI found in metadata"

    if [ "$DRY_RUN" = true ]; then
        export AWS_PAGER='' AWS_CLI_AUTO_PROMPT=off
        local account
        account=$(aws sts get-caller-identity --region "$AWS_DEFAULT_REGION" --query Account --output text)
        [[ "$account" =~ ^[0-9]{12}$ ]] || error-exit "AWS account identity could not be verified"
        echo "[DRY RUN] Authenticated AWS account ${account}"
    fi

    ami_name=$(aws ec2 --region "$AWS_DEFAULT_REGION" describe-images --image-ids "${ami}" --query 'Images[0].[Name]' --output text)
    if [ -z "$ami_name" ] || [ "$ami_name" = None ]; then
        error-exit "Source AMI name could not be resolved"
    fi

    existing_ami=$(aws ec2 --region "$AWS_DEFAULT_REGION" describe-images \
        --owners self \
        --filters "Name=name,Values=${ami_name}" \
        --query 'Images[0].ImageId' \
        --output text)
    if [ "$DRY_RUN" = true ]; then
        echo "[DRY RUN] Source and destination EC2 image reads verified"
        if [ -n "$existing_ami" ] && [ "$existing_ami" != None ]; then
            echo "[DRY RUN] Destination AMI already exists; a live run would skip copying"
        fi
        # AWS reports a successful permission check as the nonzero DryRunOperation error.
        # Check this even when the AMI exists, so a skipped copy cannot masquerade as validation.
        local output status
        if output=$(AWS_CLI_ERROR_FORMAT=legacy aws ec2 copy-image \
            --description "$ami_name" --name "$ami_name" \
            --source-image-id "$ami" --source-region us-east-1 \
            --region "$AWS_DEFAULT_REGION" --dry-run 2>&1); then
            error-exit "CopyImage dry-run returned no permission-check result"
        else
            status=$?
            if [[ "$output" == *"(DryRunOperation) when calling the CopyImage operation:"* ]]; then
                echo "[DRY RUN] CopyImage permission verified; no AMI created"
            elif [[ "$output" =~ \(([A-Za-z0-9]+)\)\ when\ calling\ the\ CopyImage\ operation ]]; then
                error-exit "CopyImage dry-run failed (${BASH_REMATCH[1]})"
            else
                error-exit "CopyImage dry-run failed (exit ${status}); permission not verified"
            fi
        fi
        return 0
    fi

    if [ -n "$existing_ami" ] && [ "$existing_ami" != "None" ]; then
        echo "AMI ${ami_name} (${existing_ami}) already exists in this AWS account; skipping copy"
        return 0
    fi
    
    aws ec2 copy-image \
        --description "${ami_name}" \
        --name "${ami_name}" \
        --source-image-id "${ami}" \
        --source-region us-east-1 \
        --region "${AWS_DEFAULT_REGION}"
}

copy_ami "$@"
