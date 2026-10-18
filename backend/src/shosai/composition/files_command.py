"""`shosai files bucket-rules [--home ru|eu]`: the operator puts ADR 0055's rules on the buckets.

Each home's bucket gets its lifecycle rules (incomplete multipart uploads aborted after a
day, `transient/` expired after 3 days) and the CORS rule for the cabinet's origins
(`CORS_ALLOWED_ORIGINS`). The keys need the right to configure the bucket; a repeat
changes nothing. The command answers per home and exits non-zero if any home failed.
"""

from collections.abc import Mapping, Sequence
from typing import Final

import structlog
from botocore.exceptions import BotoCoreError, ClientError

from shosai.composition.features import FEATURES
from shosai.composition.startup import load_process_settings
from shosai.core.config.roles import ProcessRole
from shosai.core.kernel.homes import Home
from shosai.core.observability.logs import configure_logging
from shosai.core.observability.metrics import ObservabilityMetrics, build_metrics_registry
from shosai.core.storage.s3_client import open_s3_client
from shosai.features.files.channels.bucket_rules import apply_bucket_rules

EXIT_OK: Final = 0
EXIT_FAILED: Final = 1
log = structlog.stdlib.get_logger(__name__)


async def run_bucket_rules(environ: Mapping[str, str], homes: Sequence[Home]) -> int:
    """Apply the rules to each named home's bucket; return the exit code."""
    role = ProcessRole.FILES
    settings = load_process_settings(environ, role, FEATURES)
    if settings is None:
        return EXIT_FAILED
    pipeline = configure_logging(
        settings.observability, role, ObservabilityMetrics(build_metrics_registry())
    )
    origins = [str(origin) for origin in settings.web.cors_allowed_origins]
    failed = 0
    try:
        for home in homes:
            storage = settings.storage[home]
            try:
                async with open_s3_client(storage) as client:
                    await apply_bucket_rules(client, storage.s3_bucket, origins)
            except (ClientError, BotoCoreError, ValueError) as error:
                failed += 1
                log.error(
                    "Правила бакета не применены", home=home.value, reason=type(error).__name__
                )
                continue
            log.info("Правила бакета применены", home=home.value)
    finally:
        pipeline.close()
    return EXIT_FAILED if failed else EXIT_OK
