
Promotes RPMs from the staging repositories to the production repositories:
- Copies files from [latest/ in the enterprise online-stg](https://mirror.openshift.com/enterprise/online-stg/latest/) repo to [entperprise's online-prod/lastest](https://mirror.openshift.com/enterprise/online-prod/latest/)
- Copies files from [libra rhel-7-libra-stage](https://mirror.ops.rhcloud.com/libra/rhel-7-libra-stage/) to [libra's online-prod/latest](https://mirror.ops.rhcloud.com/libra/online-prod/latest/). Latest will symlink to a new directory in online-prod based on the day's date.
