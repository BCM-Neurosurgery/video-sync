"""UTC references from Blackrock NEV 3.0 recording-start packets.

LB-0110 rev. 7, sections 4.1 and 4.10 associate the NEV header UTC with
packet 65529, reason 0. Digital/serial events are not recording-start events.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from struct import unpack_from

import numpy as np

from pyvideosync.utils import ts2unix


@dataclass(frozen=True)
class NevRecordingAnchor:
    time_origin: datetime
    timestamp_resolution: int
    start_timestamp: int

    def validate_clock(self, timestamp_resolution: int, first_timestamp: int):
        if timestamp_resolution != self.timestamp_resolution:
            raise ValueError(
                "timestamp resolution differs from the recording-start reference"
            )
        if first_timestamp < self.start_timestamp:
            raise ValueError(
                "timestamps precede recording start; check for a clock reset or wrong reference"
            )

    def to_utc(self, timestamp: int) -> datetime:
        return ts2unix(
            self.time_origin,
            self.timestamp_resolution,
            int(timestamp) - self.start_timestamp,
        )


@dataclass(frozen=True)
class _NevTiming:
    time_origin: datetime
    timestamp_resolution: int
    first_timestamp: int
    recording_starts: tuple[int, ...]


def _read_nev_timing(path: Path) -> _NevTiming:
    """Scan fixed-size packets in bounded buffers, without decoding waveforms."""
    with path.open("rb") as stream:
        header = stream.read(336)
        if len(header) != 336 or header[:8] != b"BREVENTS":
            raise ValueError(f"invalid or truncated NEV header: {path}")
        if header[8:10] != bytes((3, 0)):
            raise ValueError(f"recording-start anchoring requires NEV 3.0: {path}")
        header_size, packet_size, resolution = unpack_from("<III", header, 12)
        extended_count = unpack_from("<I", header, 332)[0]
        if (
            header_size < 336 + 32 * extended_count
            or resolution == 0
            or not 12 <= packet_size <= 256
            or packet_size % 4
        ):
            raise ValueError(f"invalid NEV timing/packet metadata: {path}")
        year, month, _, day, hour, minute, second, millisecond = unpack_from(
            "<8H", header, 28
        )
        origin = datetime(year, month, day, hour, minute, second, millisecond * 1000)
        stream.seek(0, 2)
        payload_size = stream.tell() - header_size
        if payload_size <= 0 or payload_size % packet_size:
            raise ValueError(f"empty or truncated NEV packet data: {path}")
        stream.seek(header_size)
        dtype = np.dtype(
            {
                "names": ["tick", "id", "reason"],
                "formats": ["<u8", "<u2", "<u2"],
                "offsets": [0, 8, 10],
                "itemsize": packet_size,
            }
        )
        starts = []
        first_timestamp = None
        previous_timestamp = None
        while payload_size:
            size = min(payload_size, packet_size * 16384)
            data = stream.read(size)
            if len(data) != size:
                raise ValueError(f"truncated NEV packet data: {path}")
            packets = np.frombuffer(data, dtype=dtype)
            ticks = packets["tick"]
            if (
                previous_timestamp is not None and int(ticks[0]) < previous_timestamp
            ) or np.any(ticks[1:] < ticks[:-1]):
                raise ValueError(f"NEV timestamp reset or out-of-order packets: {path}")
            if first_timestamp is None:
                first_timestamp = int(ticks[0])
            previous_timestamp = int(ticks[-1])
            is_start = (packets["id"] == 65529) & (packets["reason"] == 0)
            starts.extend(int(tick) for tick in ticks[is_start])
            payload_size -= size
    return _NevTiming(origin, resolution, first_timestamp, tuple(starts))


def read_nev_recording_anchor(reference_path, target_path) -> NevRecordingAnchor:
    """Use an explicit first raw NEV from the target's recording and NSP.

    The caller must select files with a shared, unre-based tick clock. Reject
    missing/ambiguous starts and detectable resets; filenames alone cannot
    establish that two files belong to the same recording.
    """
    reference_path = Path(reference_path)
    target_path = Path(target_path)
    reference = _read_nev_timing(reference_path)
    if len(reference.recording_starts) != 1:
        raise ValueError(
            "reference NEV must contain exactly one recording-start event "
            f"(packet 65529, reason 0): {reference_path}"
        )
    anchor = NevRecordingAnchor(
        reference.time_origin,
        reference.timestamp_resolution,
        reference.recording_starts[0],
    )
    anchor.validate_clock(reference.timestamp_resolution, reference.first_timestamp)
    target = (
        reference
        if target_path.resolve() == reference_path.resolve()
        else _read_nev_timing(target_path)
    )
    anchor.validate_clock(target.timestamp_resolution, target.first_timestamp)
    if target.recording_starts and (
        target.recording_starts != (anchor.start_timestamp,)
        or target.time_origin != anchor.time_origin
    ):
        raise ValueError(
            f"target NEV contains a different recording start: {target_path}"
        )
    return anchor
