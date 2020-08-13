
# Publish 3.11 AMI to AWS

## Purpose

This job publishes an AMI created for an OCP 3.11 build on AWS.
At some point it must have been used in testing 3.y builds in AWS.
It is not clear that anyone uses it for anything now.

## Timing

The ocp3 job runs this job when it's complete.
There's no known reason for a human to run it.

## Parameters

See the job.
