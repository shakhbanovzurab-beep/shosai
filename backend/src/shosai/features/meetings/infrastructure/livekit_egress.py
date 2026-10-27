"""LiveKit's egress messages for meetings: a call's video recording and its reports (A7).

A recording is the room's composite — the speaker layout — at the staging preset of 540p and 15
frames a second, an MP4 written straight into the owner's home bucket with the credentials of
the request, never kept in egress's own config. A report reads LiveKit's status and the file
it wrote; a webhook's egress arrives as protobuf's JSON and is read the same way.
"""

from typing import Final

from livekit.protocol.egress import (
    EgressInfo,
    EgressStatus,
    EncodedFileOutput,
    EncodedFileType,
    EncodingOptions,
    RoomCompositeEgressRequest,
    S3Upload,
)
from livekit.protocol.models import AudioCodec, VideoCodec

from shosai.features.meetings.application.video_server import BucketTarget, EgressReport

NANOSECONDS: Final = 1_000_000_000
LAYOUT: Final = "speaker"
# Пресет стейджинга (§1.3): 960×540, 15 кадров, H.264 1,2 Мбит/с, Opus 64 кбит/с. Замер A7b при
# лимите 1 CPU: ~0,5 ядра и до 434 МиБ; 720p30 — ~0,75 ядра и до 569 МиБ, у предела лимита.
RECORDING_PRESET: Final = EncodingOptions(
    width=960,
    height=540,
    framerate=15,
    video_codec=VideoCodec.H264_MAIN,
    video_bitrate=1_200,
    audio_codec=AudioCodec.OPUS,
    audio_bitrate=64,
    key_frame_interval=4,
)


def composite(room_name: str, target: BucketTarget) -> RoomCompositeEgressRequest:
    """The request of a room's video recording into the bucket."""
    upload = S3Upload(
        access_key=target.access_key,
        secret=target.secret,
        region=target.region,
        endpoint=target.endpoint,
        bucket=target.bucket,
        force_path_style=True,
    )
    # Без манифеста: рядом с файлом владельца не остаётся объекта, которого не знает files.
    output = EncodedFileOutput(
        file_type=EncodedFileType.MP4, filepath=target.key, disable_manifest=True, s3=upload
    )
    return RoomCompositeEgressRequest(
        room_name=room_name, layout=LAYOUT, file_outputs=[output], advanced=RECORDING_PRESET
    )


def report_of(info: EgressInfo) -> EgressReport:
    """The report of LiveKit's egress."""
    files = list(info.file_results) or ([info.file] if info.HasField("file") else [])
    size = max((item.size for item in files), default=0)
    duration = max((item.duration for item in files), default=0)
    return EgressReport(
        egress_id=info.egress_id,
        room_name=info.room_name,
        status=EgressStatus.Name(info.status),
        size_bytes=size,
        duration_seconds=duration // NANOSECONDS,
        error=info.error,
    )
