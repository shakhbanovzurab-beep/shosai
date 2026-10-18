"""The rules every home's bucket carries (ADR 0055 point 6), and applying them.

An incomplete multipart upload is aborted a day after it began; an object under
`transient/` expires after 3 days; the cabinet's origins may PUT presigned parts and read
their `ETag`. The cabinet runs at the public address (`PUBLIC_BASE_URL`); a development
server on another origin is added through `CORS_ALLOWED_ORIGINS`. Applying replaces the
bucket's lifecycle and CORS configuration with these, so a repeat changes nothing.
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING, Final
from urllib.parse import urlsplit

from shosai.core.config.values import normalize_origin
from shosai.features.files.domain.keys import TRANSIENT_PREFIX

if TYPE_CHECKING:
    from types_aiobotocore_s3 import S3Client
    from types_aiobotocore_s3.type_defs import (
        BucketLifecycleConfigurationTypeDef,
        CORSConfigurationTypeDef,
    )

ABORT_INCOMPLETE_DAYS: Final = 1
TRANSIENT_DAYS: Final = 3
CORS_MAX_AGE_SECONDS: Final = 3600


def lifecycle_rules() -> BucketLifecycleConfigurationTypeDef:
    """The lifecycle configuration of a home's bucket."""
    return {
        "Rules": [
            {
                "ID": "abort-incomplete-multipart",
                "Status": "Enabled",
                "Filter": {"Prefix": ""},
                "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": ABORT_INCOMPLETE_DAYS},
            },
            {
                "ID": "expire-transient",
                "Status": "Enabled",
                "Filter": {"Prefix": TRANSIENT_PREFIX},
                "Expiration": {"Days": TRANSIENT_DAYS},
            },
        ]
    }


def cabinet_origins(public_base_url: str, allowed: Sequence[str]) -> list[str]:
    """The origins the cabinet runs at: the public address's first, then the others, once each."""
    parts = urlsplit(public_base_url)
    public = normalize_origin(f"{parts.scheme}://{parts.netloc}")
    return list(dict.fromkeys([public, *allowed]))


def cors_rules(origins: Sequence[str]) -> CORSConfigurationTypeDef:
    """The CORS configuration letting the cabinet's origins send parts and read their ETag."""
    if not origins:
        message = "у бакета нет разрешённых источников: задайте PUBLIC_BASE_URL"
        raise ValueError(message)
    return {
        "CORSRules": [
            {
                "AllowedOrigins": list(origins),
                "AllowedMethods": ["PUT", "GET", "HEAD"],
                "AllowedHeaders": ["*"],
                "ExposeHeaders": ["ETag"],
                "MaxAgeSeconds": CORS_MAX_AGE_SECONDS,
            }
        ]
    }


async def apply_bucket_rules(client: S3Client, bucket: str, origins: Sequence[str]) -> None:
    """Put the lifecycle and CORS configuration on the bucket; a repeat changes nothing."""
    cors = cors_rules(origins)
    await client.put_bucket_lifecycle_configuration(
        Bucket=bucket, LifecycleConfiguration=lifecycle_rules()
    )
    await client.put_bucket_cors(Bucket=bucket, CORSConfiguration=cors)
