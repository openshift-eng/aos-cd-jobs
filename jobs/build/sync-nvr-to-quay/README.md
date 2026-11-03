# sync-nvr-to-quay

Sync a Konflux-built image (identified by its NVR) into an approved quay repo,
tagging it so quay does not garbage-collect it.

`sync_to_quay` (in art-tools / pyartcd) always creates a `sha256-<digest>` tag
to prevent garbage collection, plus the human-friendly tags derived from the
build record.

## Parameters

| Parameter      | Description |
| -------------- | ----------- |
| `ART_TOOLS_COMMIT` | (via `artToolsParam`) art-tools version to run. |
| `NVR`          | NVR(s) to sync. A comma-separated list of one or more NVRs is supported; values are trimmed. **Required.** |
| `TARGET_REPO`  | Target quay repo to sync into. This is a dropdown (allowlist). The only allowed value for now is `quay.io/redhat-user-workloads/ocp-art-tenant/art-images-test`. The allowlist is also enforced server-side by the pipeline. |
| `DRY_RUN`      | Take no action, just log what the job would have done. Defaults to `false`. |
| `MOCK`         | (via `mockParam`) Pin parameters without running the job. |

## Notes

- **Embargoed NVRs are never synced.** The pipeline skips any NVR that is
  embargoed (checked via the NVR visibility suffix and the build record's
  embargo flag).
- Quay push authentication is provided through the `quay-auth-file` credential,
  exposed to the pipeline as the `QUAY_AUTH_FILE` environment variable.
- Google Cloud credentials are provided through the `konflux-gcp-app-creds-prod`
  credential, exposed as the `GOOGLE_APPLICATION_CREDENTIALS` environment
  variable, so the pipeline's KonfluxDb / BigQuery client can authenticate when
  resolving build records.
- The underlying pipeline command is
  `artcd ... sync-nvr-to-quay --nvr "<NVR>" --target-repo "<TARGET_REPO>"`,
  with `--dry-run` appended when `DRY_RUN` is set.
