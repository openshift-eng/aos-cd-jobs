#!/bin/bash
set -xeo pipefail

# This script copies the first AMI that is found to exist in the us-east-1 region in the meta.json
# to the AWS account configured via the AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables.
# The path to the meta.json file must be passed as the first parameter.
# An optional second parameter configures whether or not to do a dry run (defaults to false).
 
error-exit() {
    echo "Error: $*" >&2
    exit 1
}

copy_ami() {
    if [ "$#" -lt 1 ]; then
        error-exit incorrect parameter count for copy_ami $#
    fi

    if ! [ -x "$(command -v aws)" ]; then
        error-exit awscli command not found
    fi

    if [ -z "$AWS_ACCESS_KEY_ID" ]; then
        error-exit \$AWS_ACCESS_KEY_ID is empty
    fi
    
    if [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
        error-exit \$AWS_SECRET_ACCESS_KEY is empty
    fi

    # For ROSA, each released RHCOS AMI has to be synced to the us-east-1 region only.
    # It will be replicated to other regions from there using the AWS Marketplace API.
    local AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION:-us-east-1}
    local META_JSON_PATH="$1"
    local DRY_RUN="$2"
    local DRY_RUN_FLAG=""
    if [ "$DRY_RUN" = true ]; then
        DRY_RUN_FLAG="--dry-run"
    fi

    ami=$(jq -r "[.amis[]|select(.name==\"us-east-1\")][0].hvm" "${META_JSON_PATH}")
    if [ -z "$ami" ]; then
        error-exit no AMI found in metadata
    fi

    ami_name=$(aws ec2 --region "$AWS_DEFAULT_REGION" describe-images --image-ids "${ami}" --query 'Images[0].[Name]' --output text)
    if [ -z "$ami_name" ]; then
        error-exit no AMI name found in metadata
    fi
    
    aws ec2 copy-image \
        --description "${ami_name}" \
        --name "${ami_name}" \
        --source-image-id "${ami}" \
        --source-region us-east-1 \
        --region "${AWS_DEFAULT_REGION}" \
        $DRY_RUN_FLAG
}

copy_ami $*
