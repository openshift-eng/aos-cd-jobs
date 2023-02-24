import asyncio
import logging
from os import PathLike
from pathlib import Path
from typing import Optional, Tuple

import click

from pyartcd.cli import cli, click_coroutine, pass_runtime
from pyartcd.runtime import Runtime
from pyartcd.signatory import Signatory
from pyartcd.util import mirror_to_google_cloud, mirror_to_s3


class SignArtifactsPipeline:
    """Rebase and build MicroShift for an assembly"""

    def __init__(
        self,
        runtime: Runtime,
        env: str,
        ssl_cert: Optional[str],
        ssl_key: Optional[str],
        sig_keyname: str,
        product: str,
        release_name: str,
        out_dir: Optional[str],
        json_digests: Tuple[Tuple[str, str], ...],
        message_digests: Tuple[str, ...],
        message_digests_dir: Optional[str],
        requestor: Optional[str],
        logger: Optional[logging.Logger] = None,
    ):
        self.runtime = runtime
        self.env = env
        self.ssl_cert = ssl_cert
        self.ssl_key = ssl_key
        self.sig_keyname = sig_keyname
        self.product = product
        self.release_name = release_name
        self.out_dir = Path(out_dir) if out_dir else self.runtime.working_dir
        self.json_digests = json_digests
        self.message_digests = message_digests
        self.message_digests_dir = message_digests_dir
        self.requestor = requestor
        self._logger = logger or runtime.logger
        self._dry_run = runtime.dry_run

        self._signing_config = self.runtime.config.get("signing" if env == "prod" else f"signing_{env}")
        self._broker_config = self.runtime.config.get("message_broker", {}).get(self._signing_config["message_broker"])

        # Currently only "openshift" product is supported
        if product != "openshift":
            raise ValueError(f"Product {product} is not support yet.")

    async def _sign_json_digest(self, signatory: Signatory, pullspec: str, digest: str, output_path: Path):
        """ Sign a JSON digest claim
        :param signatory: Signatory
        :param pullspec: Pullspec of the payload
        :param digest: SHA256 digest of the payload
        :param output_path: Where to save the signature file
        """
        self._logger.info("Signing json digest for payload %s with digest %s...", pullspec, digest)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as sig_file:
            if self._dry_run and self.env == "prod":
                self._logger.warning("[DRY RUN] Would have signed the requested artifact.")
            else:
                await signatory.sign_json_digest(self.product, self.release_name, pullspec, digest, sig_file)

    async def _sign_message_digest(self, signatory: Signatory, input_path: str, output_path: str):
        """ Sign a message digest
        :param signatory: Signatory
        :param input_path: Path to the message digest file
        :param output_path: Where to save the signature file
        """
        input_path = Path(input_path)
        self._logger.info("Signing message digest file %s...", input_path.absolute())
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(input_path, "rb") as in_file, open(output_path, "wb") as sig_file:
            if self._dry_run and self.env == "prod":
                self._logger.warning("[DRY RUN] Would have signed the requested artifact.")
            else:
                await signatory.sign_message_digest(self.product, self.release_name, in_file, sig_file)

    async def _publish_json_digest_signatures(self, local_dir: PathLike):
        tasks = []
        # mirror to S3
        mirror_release_path = "release" if self.env == "prod" else "test"
        tasks.append(mirror_to_s3(local_dir, f"s3://art-srv-enterprise/pub/openshift-v4/signatures/openshift/{mirror_release_path}/", exclude="*", include="sha256=*", dry_run=self._dry_run))
        if mirror_release_path == "release":
            tasks.append(mirror_to_s3(local_dir, f"s3://art-srv-enterprise/pub/openshift-v4/signatures/openshift-release-dev/ocp-release/", exclude="*", include="sha256=*", dry_run=self._dry_run))
            tasks.append(mirror_to_s3(local_dir, f"s3://art-srv-enterprise/pub/openshift-v4/signatures/openshift-release-dev/ocp-release-nightly/", exclude="*", include="sha256=*", dry_run=self._dry_run))

        # mirror to google storage
        google_storage_path = "official" if self.env == "prod" else "test-1"
        tasks.append(mirror_to_google_cloud(f"{local_dir}/*", f"gs://openshift-release/{google_storage_path}/signatures/openshift/release", dry_run=self._dry_run))
        tasks.append(mirror_to_google_cloud(f"{local_dir}/*", f"gs://openshift-release/{google_storage_path}/signatures/openshift-release-dev/ocp-release", dry_run=self._dry_run))
        tasks.append(mirror_to_google_cloud(f"{local_dir}/*", f"gs://openshift-release/{google_storage_path}/signatures/openshift-release-dev/ocp-release-nightly", dry_run=self._dry_run))

        await asyncio.gather(*tasks)

    async def _publish_message_digest_signatures(self, local_dir: PathLike):
        # mirror to S3
        await mirror_to_s3(local_dir, f"s3://art-srv-enterprise/pub/openshift-v4/", exclude="*", include="*/sha256sum.txt.gpg", dry_run=self._dry_run)

    async def run(self):
        if self.ssl_cert:
            self._broker_config["cert_file"] = self.ssl_cert
        if self.ssl_key:
            self._broker_config["key_file"] = self.ssl_key
        if self.message_digests and not self.message_digests_dir:
            raise ValueError("--message-digests-dir is required if --message-digest is set")

        self._logger.info("About to sign artifacts for %s %s with key %s", self.product, self.release_name, self.sig_keyname)
        json_digest_sig_dir = self.out_dir / "json_digests"
        message_digest_sig_dir = self.out_dir / "message_digests"
        async with Signatory(self._signing_config, self._broker_config, sig_keyname=self.sig_keyname, requestor=self.requestor) as signatory:
            tasks = []
            if self.json_digests:
                for pullspec, digest in self.json_digests:
                    sig_file = json_digest_sig_dir / f"{digest.replace(':', '=')}" / "signature-1"
                    tasks.append(self._sign_json_digest(signatory, pullspec, digest, sig_file))
            if self.message_digests:
                for message_digest in self.message_digests:
                    input_path = Path(self.message_digests_dir, message_digest)
                    if not input_path.is_file():
                        raise IOError(f"Message digest file {input_path} doesn't exist or is not a regular file")
                    sig_file = message_digest_sig_dir / f"{message_digest}.gpg"
                    tasks.append(self._sign_message_digest(signatory, input_path, sig_file))
            await asyncio.gather(*tasks)
        self._logger.info("All artifacts are successfully signed.")

        self._logger.info("Publishing signatures...")
        tasks = [
            self._publish_json_digest_signatures(json_digest_sig_dir),
            self._publish_message_digest_signatures(message_digest_sig_dir),
        ]
        await asyncio.gather(*tasks)

        self._logger.info("Done.")


@cli.command("sign-artifacts")
@click.option(
    "--env",
    type=click.Choice(['stage', 'prod']),
    default="stage",
    help="Which environment to sign in",
)
@click.option(
    "--ssl-cert",
    help="SSL certifiact for message broker connection",
)
@click.option(
    "--ssl-key",
    help="SSL certifiact for message broker connection",
)
@click.option(
    "--sig-keyname",
    "sig_keyname",
    metavar="KEY",
    required=True,
    help="Which key to sign with",
)
@click.option(
    "--product",
    type=click.Choice(['openshift', 'rhcos', 'coreos-installer']),
    metavar="PRODUCT",
    required=True,
    help="Product name. e.g. openshift",
)
@click.option(
    "--release",
    "release",
    metavar="RELEASE",
    required=True,
    help="Release name. e.g. 4.13.1",
)
@click.option(
    "--out-dir",
    metavar="DIR",
    help="Write signature files to the specified directory instead of working directory",
)
@click.option(
    "--json-digest",
    "json_digests",
    nargs=2,
    multiple=True,
    help="(Optional) [MULTIPLE] Pullspec and sha256 digest of the payload to sign; format is <PULLSPEC> <DIGEST>",
)
@click.option(
    "--message-digest",
    "message_digests",
    multiple=True,
    help="(Optional) [MULTIPLE] Path of the message digest file to sign",
)
@click.option(
    "--message-digests-dir",
    metavar="DIR",
    help="(Optional) Base directory of message digest files; Required if --message-digest is specified",
)
@click.option(
    "--requestor",
    metavar="USERID",
    default="timer",
    help="(Optional) The user who requested the signature",
)
@pass_runtime
@click_coroutine
async def sign_artifacts(
    runtime: Runtime,
    env: str,
    ssl_cert: Optional[str],
    ssl_key: Optional[str],
    sig_keyname: str,
    product: str,
    release: str,
    out_dir: Optional[str],
    json_digests: Tuple[Tuple[str, str], ...],
    message_digests: Tuple[str, ...],
    message_digests_dir: Optional[str],
    requestor: Optional[str],
):
    pipeline = SignArtifactsPipeline(
        runtime=runtime,
        env=env,
        ssl_cert=ssl_cert,
        ssl_key=ssl_key,
        sig_keyname=sig_keyname,
        product=product,
        release_name=release,
        out_dir=out_dir,
        json_digests=json_digests,
        message_digests=message_digests,
        message_digests_dir=message_digests_dir,
        requestor=requestor,
    )
    await pipeline.run()
