# triage

This is a script that opens all the places that the ART distractionist should
[keep a tab](https://mojo.redhat.com/docs/DOC-1207451) on.

To install the script, the desktop entry, and the application entry:

```sh
AOS_CD_JOBS=/path/to/repository
ln -s $AOS_CD_JOBS/hacks/triage/triage ~/bin/triage
ln -s $AOS_CD_JOBS/hacks/triage/triage.desktop ~/.local/share/applications/triage.desktop
update-desktop-database ~/.local/share/applications
for s in 16 22 32 48 64 128; do
  xdg-icon-resource install --size $s --novendor $AOS_CD_JOBS/hacks/triage/openshift.png openshift
done
```
