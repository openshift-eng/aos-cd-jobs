# sync-nvr-to-quay

Sync a Konflux-built image (identified by its NVR) into an approved quay repo,
tagging it so quay does not garbage-collect it.

`sync_to_quay` (in art-tools / pyartcd) always creates a `sha256-<digest>` tag
to prevent garbage collection, plus the build-specific `image_tag` from the build
record. No floating `<name>-<X.Y>` tag is applied, since it would be overwritten
by any later build of the same component in this pull-for-testing repo.

## Parameters

| Parameter      | Description |
| -------------- | ----------- |
| `ART_TOOLS_COMMIT` | (via `artToolsParam`) art-tools version to run. |
| `NVR`          | NVR(s) to sync. A comma-separated list of one or more NVRs is supported; values are trimmed. **Required.** |
| `TARGET_REPO`  | Target quay repo to sync into. This is a dropdown (allowlist). The only allowed value for now is `quay.io/redhat-user-workloads/ocp-art-tenant/art-images-test`. The allowlist is also enforced server-side by the pipeline. |
| `ALLOW_FAILED` | When `true`, also consider terminal failed builds (e.g. a build that was built but failed ITS/conforma, `its_error`) in addition to successful ones. When `false` (default), only `success` records are eligible. Embargoed builds are **never** synced, even with `ALLOW_FAILED` set. |
| `RECORD_ID`    | Konflux build `record_id`. When more than one record exists for a single NVR, the job fails and lists the candidate record_ids; set `RECORD_ID` to the desired one to pick among them. Only meaningful for a single NVR. Defaults to empty. |
| `DRY_RUN`      | Take no action, just log what the job would have done. Defaults to `false`. |
| `MOCK`         | (via `mockParam`) Pin parameters without running the job. |

## Notes

- **Embargoed NVRs are never synced.** The pipeline skips any NVR that is
  embargoed (checked via the NVR visibility suffix and the build record's
  embargo flag).
- Quay push authentication is provided through the `quay-auth-file` credential,
  exposed to the pipeline as the `QUAY_AUTH_FILE` environment variable.
- RHCOS source images live in the `art-rhcos-images` repo, which uses a separate
  quay credential. The `art-rhcos-images-sa` credential is exposed as the
  `RHCOS_QUAY_AUTH_FILE` environment variable, and the pipeline builds a **merged
  registry config** (covering both the default konflux creds and the RHCOS creds)
  so `oc image mirror` can read an RHCOS source as well as a konflux source and
  write to the destination repo.
- Google Cloud credentials are provided through the `konflux-gcp-app-creds-prod`
  credential, exposed as the `GOOGLE_APPLICATION_CREDENTIALS` environment
  variable, so the pipeline's KonfluxDb / BigQuery client can authenticate when
  resolving build records.
- On successful completion the job appends a summary of the destination pullspecs
  it created (grouped by NVR) to the Jenkins build description. This requires the
  `jenkins-service-account` / `jenkins-service-account-token` credentials and the
  `BUILD_URL` / `JOB_NAME` environment variables.
- The underlying pipeline command is
  `artcd ... sync-nvr-to-quay --nvr "<NVR>" --target-repo "<TARGET_REPO>"`,
  with `--dry-run` appended when `DRY_RUN` is set.
