Auto-detect and publish RHCOS boot-image bumps for a single z-stream y-stream (ART-25059).

For the given OCP y-stream (`VERSION`), this job runs `artcd rhcos-sync-fast-channel`,
which:

1. Queries the Cincinnati **fast** channel (`fast-<major>.<minor>`) for the release
   end users are currently receiving.
2. Picks the newest release node in that y-stream and extracts the RHCOS build id it
   references.
3. Compares that id against the `rhcos-id.txt` currently published on
   mirror.openshift.com (the same "needsHappening" check used by the GA path).
4. If the id differs, triggers the existing `rhcos_sync` job with `sign_only=False`
   to publish the updated z-stream boot images. If it matches — or the fast channel
   has no nodes yet (pre-GA) — it is a no-op.

This replaces the previous manual, per-z-stream Jira request (recurring template
ART-4163) for publishing boot-image bumps.

Parameters:
- `VERSION`: the OCP y-stream to scan (e.g. `4.19`).
- `FORCE`: trigger the sync even if the mirror already appears current.
- `DRY_RUN`: run without side effects (no downstream `rhcos_sync` trigger).

This job is normally driven per y-stream by the scheduled dispatcher
`scheduled-jobs/build/rhcos-sync-fast-channel`, which iterates all buildable
4.x/5.x y-streams sequentially. It can also be run manually for a single version.
