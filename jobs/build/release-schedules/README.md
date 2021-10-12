# OCP release schedules CM update

The purpose of this workflow is to update the content from the release-schedules config map that lives in app.ci cluster.

## Dependencies:

- `oc` and `git` commands are available already on the host.
- The specific kubeconfig with limited permissions must exists on the host.
