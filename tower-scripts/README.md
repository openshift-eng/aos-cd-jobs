Scripts designed to drive cluster teardown/standup/install/etc from the Ops bastion host (a.k.a bastion2).
ssh keys are configured on bastion to execute certain entrypoint scripts from this collection.
The scripts will be manually installed onto bastion and periodically updated.
For security purposes, they will be not be pulled dynamically from this git repo.
