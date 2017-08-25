Scripts designed to drive cluster teardown/standup/install/etc from the Ops bastion host (a.k.a tower2).
ssh keys are configured on tower to execute certain entrypoint scripts from this collection.
The scripts will be manually installed onto tower and periodically updated.
For security purposes, they will be not be pulled dynamically from this git repo.
