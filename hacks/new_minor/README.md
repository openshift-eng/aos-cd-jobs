# New Minor: Scripts for verifying distgit and tag setup

This is a set of scripts that can be used to verify what needs to be done to get
distgit branches and brew tags set up to initiate a new minor release.

Main entry point is `branch-new-release`, which should be invoked as:

```sh\
./branch-new-release 4.11
```

This script will export the variables `new_version` and `old_version`, and run
the `./verify-*` scripts.

What do the `verify-*` scripts check?

## verify-brew-tags
- checks if tags from the old version have a relating tag in the new version
- checks if the tags have the same arches set up
- checks if it has the same children (tag inheritence)

## verify-candidate-contents
Compares builds from both candidate tags, and filters out builds created by
known automation. And shows differences.

## verify-override-tag-contents
Same as `verify-candidate-contents`, but for `-override`.

## verify-distgit-branch
Checks if distgit branches are available. Warning, it queries cgit, so there
might be cache issues.

## verify-pkg-whitelist
Checks if allowed packages in `rhaos-$version-rhel-$rhel` is the same.
