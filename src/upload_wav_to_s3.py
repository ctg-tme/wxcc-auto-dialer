#!/usr/bin/env python3
"""CLI helper to upload wav files to an S3 bucket with public-read access."""

from __future__ import annotations

import argparse
import os
import struct
import sys
import wave
from pathlib import Path
from typing import NamedTuple, Optional, Tuple
from urllib.parse import quote

import boto3
from botocore.exceptions import BotoCoreError, ClientError


DEFAULT_BUCKET = "liamfrawley"
DEFAULT_REGION = "eu-north-1"

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Upload a local wav file to S3 with public-read permissions so services "
            "like Twilio can fetch it."
        )
    )
    parser.add_argument("file", help="Path to the .wav file to upload.")
    parser.add_argument(
        "--bucket",
        default=DEFAULT_BUCKET,
        help=f"S3 bucket name (default: %(default)s).",
    )
    parser.add_argument(
        "--region",
        default=DEFAULT_REGION,
        help=f"AWS region for the bucket (default: %(default)s).",
    )
    parser.add_argument(
        "--key",
        default=None,
        help="S3 object key; defaults to the source filename.",
    )
    parser.add_argument(
        "--profile",
        default=os.getenv("AWS_PROFILE"),
        help="Optional named AWS profile to use for credentials.",
    )
    parser.add_argument(
        "--prefix",
        default=None,
        help="Prefix to prepend to the key (e.g. 'prompts/').",
    )
    return parser.parse_args()


def build_key(source: Path, provided_key: Optional[str], prefix: Optional[str]) -> str:
    key = provided_key or source.name
    if prefix:
        clean_prefix = prefix.rstrip("/")
        key = f"{clean_prefix}/{key}"
    return key


def ensure_wav_file(source: Path) -> None:
    if not source.exists():
        sys.exit(f"File not found: {source}")
    if not source.is_file():
        sys.exit(f"Not a file: {source}")
    if source.suffix.lower() != ".wav":
        sys.exit("Only .wav files are supported.")


class WavPayload(NamedTuple):
    nchannels: int
    sampwidth: int
    framerate: int
    comptype: str
    compname: str
    frames: bytes


def split_channels_if_needed(source: Path) -> Tuple[Path, Optional[Path]]:
    """Return a mono file to upload and optionally a saved right-channel file."""
    payload = read_wav_payload(source)
    if payload.nchannels == 1:
        return source, None
    if payload.nchannels != 2:
        sys.exit(f"Unsupported channel count ({payload.nchannels}); only mono or stereo wav files are supported.")

    left_data, right_data = split_stereo_frames(payload.frames, payload.sampwidth)

    split_dir = source.parent / "split-files"
    split_dir.mkdir(parents=True, exist_ok=True)
    left_path = split_dir / f"{source.stem}_customer.wav"
    right_path = split_dir / f"{source.stem}_agent.wav"
    write_mono_wav(
        left_path,
        payload.sampwidth,
        payload.framerate,
        payload.comptype,
        payload.compname,
        left_data,
    )
    write_mono_wav(
        right_path,
        payload.sampwidth,
        payload.framerate,
        payload.comptype,
        payload.compname,
        right_data,
    )
    return left_path, right_path


def write_mono_wav(
    path: Path,
    sampwidth: int,
    framerate: int,
    comptype: str,
    compname: str,
    frames: bytes,
) -> None:
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setparams((1, sampwidth, framerate, 0, comptype, compname))
        wav_file.writeframes(frames)


def split_stereo_frames(frames: bytes, sampwidth: int) -> Tuple[bytes, bytes]:
    """Split interleaved stereo frames into separate mono byte streams."""
    frame_stride = sampwidth * 2
    if frame_stride == 0 or len(frames) % frame_stride != 0:
        sys.exit("Unable to split stereo audio: invalid frame data.")
    left = bytearray()
    right = bytearray()
    mv = memoryview(frames)
    for offset in range(0, len(frames), frame_stride):
        frame = mv[offset : offset + frame_stride]
        left.extend(frame[:sampwidth])
        right.extend(frame[sampwidth:])
    return bytes(left), bytes(right)


def read_wav_payload(source: Path) -> WavPayload:
    """Read wav metadata and frames, falling back to decoding mu-law if needed."""
    try:
        with wave.open(str(source), "rb") as wav_file:
            params = wav_file.getparams()
            frames = wav_file.readframes(params.nframes)
            return WavPayload(
                params.nchannels,
                params.sampwidth,
                params.framerate,
                params.comptype,
                params.compname,
                frames,
            )
    except wave.Error as exc:
        payload = decode_non_pcm_wav(source)
        if payload:
            return payload
        sys.exit(f"Unable to read wav file: {exc}")


def decode_non_pcm_wav(source: Path) -> Optional[WavPayload]:
    """Handle simple non-PCM formats such as mu-law."""
    fmt_chunk, data_chunk = extract_wav_chunks(source)
    if fmt_chunk is None or data_chunk is None:
        return None
    if len(fmt_chunk) < 16:
        sys.exit("Malformed WAV file: fmt chunk too small.")
    (
        format_tag,
        nchannels,
        framerate,
        _byte_rate,
        _block_align,
        bits_per_sample,
    ) = struct.unpack("<HHIIHH", fmt_chunk[:16])

    if format_tag == 0x0007:  # mu-law
        if bits_per_sample != 8:
            sys.exit("Unsupported mu-law encoding: expected 8 bits per sample.")
        pcm_frames = decode_mulaw_bytes(data_chunk)
        return WavPayload(
            nchannels,
            2,
            framerate,
            "NONE",
            "converted from mu-law",
            pcm_frames,
        )

    return None


def get_wav_duration_seconds(source: Path) -> float:
    """Return the duration of a WAV (or mu-law) file in seconds."""
    payload = read_wav_payload(source)
    if payload.framerate == 0:
        return 0.0
    bytes_per_frame = payload.nchannels * payload.sampwidth
    if bytes_per_frame == 0:
        return 0.0
    frame_count = len(payload.frames) // bytes_per_frame
    return frame_count / float(payload.framerate)


def extract_wav_chunks(source: Path) -> Tuple[Optional[bytes], Optional[bytes]]:
    """Return the raw fmt and data chunks from a WAV file."""
    try:
        with source.open("rb") as wav_file:
            header = wav_file.read(12)
            if len(header) < 12:
                sys.exit(f"{source} is not a valid WAV file.")
            riff, _size, wave_marker = struct.unpack("<4sI4s", header)
            if riff != b"RIFF" or wave_marker != b"WAVE":
                sys.exit(f"{source} is not a RIFF/WAVE file.")
            fmt_chunk = None
            data_chunk = None
            while True:
                chunk_header = wav_file.read(8)
                if len(chunk_header) < 8:
                    break
                chunk_id, chunk_size = struct.unpack("<4sI", chunk_header)
                chunk_data = wav_file.read(chunk_size)
                if len(chunk_data) < chunk_size:
                    sys.exit("Unexpected end of file while reading WAV data.")
                if chunk_size % 2 == 1:
                    wav_file.seek(1, os.SEEK_CUR)
                if chunk_id == b"fmt ":
                    fmt_chunk = chunk_data
                elif chunk_id == b"data":
                    data_chunk = chunk_data
            return fmt_chunk, data_chunk
    except OSError as exc:
        sys.exit(f"Failed to read {source}: {exc}")


def decode_mulaw_bytes(data: bytes) -> bytes:
    """Convert mu-law encoded bytes to 16-bit PCM little-endian samples."""
    if not data:
        return b""
    pcm = bytearray(len(data) * 2)
    for index, sample_byte in enumerate(data):
        value = mulaw_byte_to_linear(sample_byte)
        struct.pack_into("<h", pcm, index * 2, value)
    return bytes(pcm)


def mulaw_byte_to_linear(sample_byte: int) -> int:
    """Decode a single 8-bit mu-law sample to 16-bit PCM."""
    # Algorithm taken from ITU-T G.711: convert to biased magnitude, scale by the
    # exponent and then remove the bias with the correct sign.
    sample = ~sample_byte & 0xFF
    sign = sample & 0x80
    sample &= 0x7F
    exponent = (sample >> 4) & 0x07
    mantissa = sample & 0x0F
    magnitude = ((mantissa << 3) + 0x84) << exponent
    if sign:
        value = 0x84 - magnitude
    else:
        value = magnitude - 0x84
    return max(-32768, min(32767, value))


def create_s3_client(region: str, profile: Optional[str]):
    session_kwargs = {"region_name": region}
    if profile:
        session_kwargs["profile_name"] = profile
    session = boto3.Session(**session_kwargs)
    return session.client("s3")


def upload_wav(source: Path, bucket: str, key: str, client) -> str:
    extra_args = {
        "ACL": "public-read",
        "ContentType": "audio/wav",
    }
    client.upload_file(str(source), bucket, key, ExtraArgs=extra_args)
    encoded_key = quote(key)
    return f"https://{bucket}.s3.{client.meta.region_name}.amazonaws.com/{encoded_key}"


def main() -> None:
    args = parse_args()
    source = Path(args.file).expanduser().resolve()
    ensure_wav_file(source)
    upload_source, right_channel = split_channels_if_needed(source)
    if right_channel:
        print(f"Stereo file detected. Left channel: {upload_source}, right channel kept locally: {right_channel}")
    key = build_key(upload_source, args.key, args.prefix)
    client = create_s3_client(args.region, args.profile)

    try:
        public_url = upload_wav(upload_source, args.bucket, key, client)
    except (ClientError, BotoCoreError) as exc:
        sys.exit(f"Upload failed: {exc}")

    print("Upload complete.")
    print(f"Public URL:\n{public_url}")


if __name__ == "__main__":
    main()
