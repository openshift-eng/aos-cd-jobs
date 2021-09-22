# triage

This is a bunch of scripts that opens all the places that the ART distractionist should
[keep a tab](https://mojo.redhat.com/docs/DOC-1207451) on.

In particular:
## triage
Opens web browser with incoming stuff and problems

## assemblies
Opens a web browser with urls relating to an assembly. Includes desktop items
for *4.8 building* and *4.7 shipping*.

## nightlies
Opens a web browser with nightlies for each arch for a particular version. Either get the
list view, or jump to the info page of the most recent one.

To install the scripts, the desktop entries, run `install`. Ensure that `yq` is
installed `pip install --user yq; ln -s ~/.local/bin/yq ~/bin/yq`
