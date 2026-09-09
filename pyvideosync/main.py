"""
Main function to orchestrate the loading, processing, and merging of NEV, NS5, and camera data,
and aligning the audio with the video.
"""

import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

from pyvideosync.data_pool import VideoFilesPool
import pandas as pd
from pyvideosync.logging_config import (
    get_current_ts,
    configure_logging,
)
from pyvideosync.pathutils import PathUtils
from pyvideosync.process import (
    ffmpeg_concat_mp4s,
    ffmpeg_concat_mp4s_gpu,
    make_synced_subclip_moviepy,
    make_synced_subclip_moviepy_gpu,
)
from pyvideosync.utils import (
    get_column_min_max,
    get_json_file,
    get_mp4_file,
)
from pyvideosync.videojson import Videojson
from pyvideosync.nev import Nev
from pyvideosync.nsx import Nsx, read_nsx_time_bounds
from pyvideosync.sidecar import (
    build_frame_mapping,
    combine_frame_mappings,
    concatenate_frame_mappings,
    write_ns3_sidecar,
)
from pyvideosync.sessions import (
    NeuralSegmentSpec,
    SyncJobSpec,
    TimeAnchor,
    VideoSelection,
    resolve_run_spec,
)
import argparse
import glob
import shutil
import uuid


def _get_nev_chunk_serial_df(nev, ns5, time_anchor: TimeAnchor, logger):
    """Build the serial mapping using the session's explicit time anchor."""
    if time_anchor.kind == "first_raw_nev":
        logger.info(
            "Calibrating stitched timestamps with first raw NEV: "
            f"{time_anchor.reference_path}"
        )
        first_nev = Nev(str(time_anchor.reference_path))
        return (
            nev.get_chunk_serial_df(
                reference_time_origin=first_nev.get_time_origin(),
                reference_start_timestamp=first_nev.get_start_timestamp(),
            ),
            True,
        )

    if time_anchor.kind == "paired_ns5":
        logger.info(f"Calibrating raw timestamps with paired NS5: {ns5.path}")
        return (
            nev.get_chunk_serial_df(
                reference_time_origin=ns5.get_timeOrigin(),
                reference_start_timestamp=ns5.get_start_timestamp(),
            ),
            True,
        )

    return (
        nev.get_chunk_serial_df(),
        time_anchor.kind == "embedded",
    )


def _get_video_file_pool(
    selection: VideoSelection,
    cache: dict[VideoSelection, VideoFilesPool],
) -> VideoFilesPool:
    """Build each immutable video selection index at most once per run."""
    if selection not in cache:
        if selection.kind == "discover":
            cache[selection] = VideoFilesPool.from_directory(
                str(selection.recording_dir)
            )
        else:
            cache[selection] = VideoFilesPool.from_files(
                (*selection.json_paths, *selection.mp4_paths)
            )
    return cache[selection]


def _emit_ns3_sidecar(ns3_path, nev_chunk_serial_df, output_dir, task_name, logger):
    """Slice all NS3 channels by the NEV TimeStamp range and write an HDF5 sidecar.

    Runs once per session, before per-camera video processing. Failure here
    logs a warning but does not abort the session — the synced video is still
    the primary output.
    """
    try:
        ns3 = Nsx(ns3_path)
    except Exception as e:
        logger.error(f"Could not open NS3 {ns3_path}: {e}")
        return

    ts_min = int(nev_chunk_serial_df["TimeStamps"].min())
    ts_max = int(nev_chunk_serial_df["TimeStamps"].max())
    timestamps, amplitudes, channel_labels = ns3.get_all_channels_arrays(ts_min, ts_max)
    if len(timestamps) == 0:
        logger.warning(
            f"NS3 sidecar: no samples in NEV range [{ts_min}, {ts_max}] for {task_name}"
        )
        return

    sidecar_path = os.path.join(output_dir, f"{task_name}_ns3.h5")
    attrs = {
        "samp_per_s": ns3.sampleResolution / ns3.basic_header["Period"],
        "period": ns3.basic_header["Period"],
        "timestamp_resolution": ns3.timestampResolution,
        "time_origin": str(ns3.timeOrigin),
        "ns3_path": ns3_path,
        "nev_ts_min": ts_min,
        "nev_ts_max": ts_max,
    }
    write_ns3_sidecar(sidecar_path, timestamps, amplitudes, channel_labels, attrs)
    logger.info(
        f"NS3 sidecar: wrote {sidecar_path} "
        f"({len(timestamps)} samples × {len(channel_labels)} channels)"
    )


def _find_overlapping_camera_timestamps(
    camera_files,
    camera_serials,
    nev_start_serial,
    nev_end_serial,
    logger,
    nev_start_utc=None,
    nev_end_utc=None,
):
    """Return camera groups overlapping the NEV window.

    Calibrated UTC bounds are preferred when a timestamp reference is
    available. Otherwise, preserve the serial-range fallback without assuming
    that serials are monotonic across recording-date folders.
    """
    if (nev_start_utc is None) != (nev_end_utc is None):
        raise ValueError("nev_start_utc and nev_end_utc must be supplied together")

    camera_items = sorted(camera_files.items())
    if nev_start_utc is not None:
        start_idx = _bisect_first_camera_overlap(camera_items, nev_start_utc)
        logger.info(
            f"Camera time search skipped {start_idx} of {len(camera_items)} "
            "recording groups"
        )
        camera_items = camera_items[start_idx:]

    configured_serials = {str(serial) for serial in camera_serials or []}
    timestamps = []
    for timestamp, camera_file_group in camera_items:
        json_path = get_json_file(camera_file_group, None)
        if json_path is None:
            logger.error(f"No JSON file found in group {timestamp}")
            continue

        videojson = Videojson(json_path)
        if not videojson.is_valid():
            logger.error(f"Invalid JSON file: {json_path}")
            continue

        if nev_start_utc is not None:
            camera_start, camera_end = videojson.get_realtime_bounds()
            if camera_start is not None and camera_start > nev_end_utc:
                break
            overlaps = (
                camera_start is not None
                and camera_end is not None
                and camera_start <= nev_end_utc
                and camera_end >= nev_start_utc
            )
        else:
            camera_start, camera_end = videojson.get_min_max_chunk_serial()
            overlaps = (
                camera_start is not None
                and camera_end is not None
                and camera_start <= nev_end_serial
                and camera_end >= nev_start_serial
            )

        available_serials = {str(serial) for serial in videojson.get_camera_serials()}
        if configured_serials and configured_serials.isdisjoint(available_serials):
            continue

        if overlaps:
            logger.info(f"Overlap found, timestamp: {timestamp}")
            timestamps.append(timestamp)

    return sorted(timestamps)


def _bisect_first_camera_overlap(camera_items, window_start):
    """Find the first camera group whose realtime end reaches the window."""
    lo, hi = 0, len(camera_items)
    while lo < hi:
        mid = (lo + hi) // 2
        _, camera_file_group = camera_items[mid]
        json_path = get_json_file(camera_file_group, None)
        if json_path is None:
            hi = mid
            continue

        videojson = Videojson(json_path)
        if not videojson.is_valid():
            hi = mid
            continue

        _, camera_end = videojson.get_realtime_bounds()
        if camera_end is not None and camera_end < window_start:
            lo = mid + 1
        else:
            hi = mid
    return lo


@dataclass
class _NeuralContext:
    segment: NeuralSegmentSpec
    ns5: Nsx
    chunk_serial_df: pd.DataFrame
    start_serial: int
    end_serial: int
    start_utc: datetime
    end_utc: datetime
    utc_calibrated: bool


@dataclass
class _AlignedFragment:
    mp4_path: str
    all_merged: pd.DataFrame
    frame_mapping: pd.DataFrame


def _segment_utc_bounds(segment: NeuralSegmentSpec, logger):
    """Return inexpensive candidate UTC bounds for overlap discovery."""
    if segment.time_anchor.kind == "paired_ns5":
        bounds = read_nsx_time_bounds(segment.ns5_path)
        return (
            bounds.start_utc,
            bounds.end_utc,
            timedelta(seconds=bounds.clk_per_sample / bounds.timestamp_resolution),
        )
    if segment.time_anchor.kind == "serial_only":
        raise ValueError(
            f"video-window discovery requires a UTC anchor: {segment.name}"
        )

    nev = Nev(str(segment.nev_path))
    chunk_serial_df, calibrated = _get_nev_chunk_serial_df(
        nev, None, segment.time_anchor, logger
    )
    if not calibrated or chunk_serial_df.empty:
        raise ValueError(f"cannot derive UTC bounds for neural segment: {segment.name}")
    return (
        chunk_serial_df["UTCTimeStamp"].min(),
        chunk_serial_df["UTCTimeStamp"].max(),
        timedelta(seconds=1 / 30),
    )


def _video_utc_bounds(video: VideoSelection):
    starts = []
    ends = []
    for json_path in video.json_paths:
        videojson = Videojson(str(json_path))
        if not videojson.is_valid():
            raise ValueError(f"Invalid JSON file: {json_path}")
        start, end = videojson.get_realtime_bounds()
        if start is None or end is None:
            raise ValueError(f"camera JSON has no realtime bounds: {json_path}")
        starts.append(start)
        ends.append(end)
    if not starts:
        raise ValueError("video-window job has no JSON timing metadata")
    return min(starts), max(ends)


def _select_neural_segments(job: SyncJobSpec, logger):
    if job.window == "neural":
        return job.neural_segments

    video_start, video_end = _video_utc_bounds(job.video)
    candidates = []
    for segment in job.neural_segments:
        start, end, tolerance = _segment_utc_bounds(segment, logger)
        if start <= video_end and end >= video_start:
            candidates.append((start, end, tolerance, segment))
    if not candidates:
        raise RuntimeError(f"No neural data overlaps the video window for {job.name}")
    candidates.sort(key=lambda row: row[0])
    selected = tuple(segment for _, _, _, segment in candidates)
    if job.coverage == "require_full":
        covered_until = video_start
        for start, end, tolerance, _ in candidates:
            if start > covered_until + tolerance:
                raise RuntimeError(
                    f"Neural data has a UTC coverage gap for video job {job.name}: "
                    f"{covered_until} to {start}"
                )
            covered_until = max(covered_until, end)
        final_tolerance = candidates[-1][2]
        if covered_until + final_tolerance < video_end:
            raise RuntimeError(
                f"Neural data ends before video job {job.name}: "
                f"{covered_until} before {video_end}"
            )
    logger.info(
        f"Selected {len(selected)} of {len(job.neural_segments)} neural segments "
        f"for video window {video_start} to {video_end}"
    )
    return selected


def _load_neural_context(segment: NeuralSegmentSpec, logger) -> _NeuralContext:
    ns5 = Nsx(str(segment.ns5_path))
    nev = Nev(str(segment.nev_path))
    chunk_serial_df, utc_calibrated = _get_nev_chunk_serial_df(
        nev, ns5, segment.time_anchor, logger
    )
    if chunk_serial_df.empty:
        raise RuntimeError(f"NEV contains no camera serial events: {segment.nev_path}")
    start_serial, end_serial = get_column_min_max(chunk_serial_df, "chunk_serial")
    return _NeuralContext(
        segment=segment,
        ns5=ns5,
        chunk_serial_df=chunk_serial_df,
        start_serial=start_serial,
        end_serial=end_serial,
        start_utc=chunk_serial_df["UTCTimeStamp"].min(),
        end_utc=chunk_serial_df["UTCTimeStamp"].max(),
        utc_calibrated=utc_calibrated,
    )


def _camera_timestamps(job, camera_files, context, logger):
    if job.window == "video":
        return sorted(camera_files)
    return _find_overlapping_camera_timestamps(
        camera_files,
        job.video.camera_serials,
        context.start_serial,
        context.end_serial,
        logger,
        nev_start_utc=context.start_utc if context.utc_calibrated else None,
        nev_end_utc=context.end_utc if context.utc_calibrated else None,
    )


def _camera_serials(job, camera_files, timestamps, logger):
    if job.video.camera_serials:
        return tuple(job.video.camera_serials)

    available = set()
    for timestamp in timestamps:
        json_path = get_json_file(camera_files[timestamp], None)
        if json_path is None:
            continue
        videojson = Videojson(json_path)
        if videojson.is_valid():
            available.update(str(serial) for serial in videojson.get_camera_serials())
    serials = tuple(sorted(available))
    logger.info(f"Auto-detected camera serials: {serials}")
    return serials


def _align_camera_fragments(
    job,
    contexts,
    camera_files,
    timestamps,
    camera_serial,
    channel_name,
    logger,
):
    fragments = []
    expected_frame_keys = []
    for timestamp in timestamps:
        camera_file_group = camera_files[timestamp]
        json_path = get_json_file(camera_file_group, None)
        if json_path is None:
            raise RuntimeError(f"No JSON file found in group {timestamp}")
        videojson = Videojson(json_path)
        serial_lookup = {
            str(serial): serial for serial in videojson.get_camera_serials()
        }
        if str(camera_serial) not in serial_lookup:
            continue
        camera_df = videojson.get_camera_df(serial_lookup[str(camera_serial)])
        mp4_path = get_mp4_file(camera_file_group, str(camera_serial), None)
        if mp4_path is None:
            raise RuntimeError(
                f"No MP4 file found for camera {camera_serial} in group {timestamp}"
            )

        if job.window == "video":
            expected_frame_keys.extend(
                (str(mp4_path), int(chunk_serial))
                for chunk_serial in camera_df["chunk_serial_data"]
            )

        for context in contexts:
            camera_slice = camera_df.loc[
                (camera_df["chunk_serial_data"] >= context.start_serial)
                & (camera_df["chunk_serial_data"] <= context.end_serial)
            ]
            joined_frames = context.chunk_serial_df.merge(
                camera_slice,
                left_on="chunk_serial",
                right_on="chunk_serial_data",
                how="inner",
            )
            if joined_frames.empty:
                continue
            joined_frames = joined_frames.sort_values("TimeStamps").assign(
                mp4_file=mp4_path
            )
            ns5_slice = context.ns5.get_filtered_channel_df(
                channel_name,
                int(joined_frames.iloc[0]["TimeStamps"]),
                int(joined_frames.iloc[-1]["TimeStamps"]),
            )
            if ns5_slice.empty:
                raise RuntimeError(
                    f"NS5 has no samples for matched frames: {context.segment.ns5_path}"
                )
            all_merged = ns5_slice.merge(
                joined_frames,
                left_on="TimeStamp",
                right_on="TimeStamps",
                how="left",
            )[["TimeStamp", "Amplitude", "chunk_serial", "mp4_frame_idx"]]
            all_merged["mp4_file"] = mp4_path
            frame_mapping = build_frame_mapping(
                joined_frames,
                camera_serial=str(camera_serial),
                ns5_start_timestamp=context.ns5.timeStamp,
                ns5_clk_per_sample=context.ns5.clk_per_samp,
                ns5_path=context.ns5.path,
            )
            fragments.append(
                _AlignedFragment(
                    mp4_path=str(mp4_path),
                    all_merged=all_merged,
                    frame_mapping=frame_mapping,
                )
            )

    mapping = concatenate_frame_mappings(
        [fragment.frame_mapping for fragment in fragments]
    )
    if job.window == "video" and job.coverage == "require_full":
        actual_frame_keys = list(
            zip(
                mapping["source_mp4"].astype(str),
                mapping["chunk_serial"].astype(int),
            )
        )
        if actual_frame_keys != expected_frame_keys:
            expected_set = set(expected_frame_keys)
            actual_set = set(actual_frame_keys)
            raise RuntimeError(
                f"Neural data does not fully cover {job.name} camera "
                f"{camera_serial}: expected {len(expected_frame_keys)} mapped "
                f"frames, found {len(actual_frame_keys)} "
                f"({len(expected_set - actual_set)} missing, "
                f"{len(actual_set - expected_set)} unexpected)"
            )
    return fragments, mapping


def _render_camera(
    job,
    camera_serial,
    fragments,
    output_dir,
    run_spec,
):
    fragments_by_mp4 = defaultdict(list)
    for fragment in fragments:
        fragments_by_mp4[fragment.mp4_path].append(fragment.all_merged)

    video_output_dir = os.path.join(output_dir, str(camera_serial))
    os.makedirs(video_output_dir, exist_ok=True)
    session_uuid = str(uuid.uuid4())[:8]
    subclip_paths = []
    for mp4_path, dataframes in fragments_by_mp4.items():
        merged = pd.concat(dataframes, ignore_index=True)
        if run_spec.gpu_enabled:
            subclip = make_synced_subclip_moviepy_gpu(
                merged,
                mp4_path,
                video_output_dir,
                session_uuid,
                gpu_enabled=run_spec.gpu_enabled,
                gpu_type=run_spec.gpu_type,
            )
        else:
            subclip = make_synced_subclip_moviepy(
                merged, mp4_path, video_output_dir, session_uuid
            )
        subclip_paths.append(subclip)

    final_path = os.path.join(output_dir, f"{job.name}_{camera_serial}.mp4")
    if len(subclip_paths) == 1:
        shutil.move(subclip_paths[0], final_path)
    elif run_spec.gpu_enabled:
        ffmpeg_concat_mp4s_gpu(
            subclip_paths,
            final_path,
            gpu_enabled=run_spec.gpu_enabled,
            gpu_type=run_spec.gpu_type,
        )
    else:
        ffmpeg_concat_mp4s(subclip_paths, final_path)
    return final_path, video_output_dir


def _cleanup_intermediates(video_output_dir, logger):
    patterns = [
        "*_subclip_*.mp4",
        "*_audio_*.wav",
        "*_final_*.mp4",
        "concat_filelist.txt",
    ]
    removed = 0
    for pattern in patterns:
        for path in glob.glob(os.path.join(video_output_dir, pattern)):
            try:
                os.remove(path)
                removed += 1
            except OSError as exc:
                logger.warning(f"Could not remove {path}: {exc}")
    logger.info(f"Cleaned {removed} intermediate file(s) from {video_output_dir}")
    if os.path.isdir(video_output_dir) and not os.listdir(video_output_dir):
        os.rmdir(video_output_dir)


def _process_job(job, run_spec, video_file_pool_cache, logger):
    video_file_pool = _get_video_file_pool(job.video, video_file_pool_cache)
    camera_files = video_file_pool.list_groups()
    if not camera_files:
        raise RuntimeError(f"No camera files found for {job.name}")

    selected_segments = _select_neural_segments(job, logger)
    contexts = [_load_neural_context(segment, logger) for segment in selected_segments]
    timestamps = _camera_timestamps(job, camera_files, contexts[0], logger)
    if not timestamps:
        raise RuntimeError(f"No camera recordings overlap the window for {job.name}")
    camera_serials = _camera_serials(job, camera_files, timestamps, logger)
    if not camera_serials:
        raise RuntimeError(f"No cameras resolved for {job.name}")

    output_dir = os.path.join(str(run_spec.output_dir), job.name)
    os.makedirs(output_dir, exist_ok=True)
    if run_spec.ns3_sidecar:
        if job.window == "video":
            logger.warning("NS3 sidecars are skipped for video-window jobs")
        else:
            segment = contexts[0].segment
            if segment.ns3_path:
                _emit_ns3_sidecar(
                    str(segment.ns3_path),
                    contexts[0].chunk_serial_df,
                    output_dir,
                    job.name,
                    logger,
                )

    camera_mappings = []
    for camera_serial in camera_serials:
        fragments, mapping = _align_camera_fragments(
            job,
            contexts,
            camera_files,
            timestamps,
            str(camera_serial),
            run_spec.channel_name,
            logger,
        )
        if not fragments or mapping.empty:
            raise RuntimeError(
                f"No synchronized fragments produced for camera {camera_serial}"
            )
        final_path, intermediate_dir = _render_camera(
            job,
            str(camera_serial),
            fragments,
            output_dir,
            run_spec,
        )
        logger.info(f"Saved camera {camera_serial} to {final_path}")
        if not run_spec.keep_intermediates:
            _cleanup_intermediates(intermediate_dir, logger)
        camera_mappings.append(mapping)

    combined_mapping = combine_frame_mappings(camera_mappings)
    mapping_path = os.path.join(output_dir, f"{job.name}_frame_mapping.csv")
    combined_mapping.to_csv(mapping_path, index=False)
    logger.info(
        f"Wrote frame mapping: {mapping_path} "
        f"({len(combined_mapping)} frames across "
        f"{combined_mapping['camera_serial'].nunique()} cameras)"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Video synchronization tool for neural data and camera recordings."
    )
    parser.add_argument(
        "-c",
        "--config",
        required=True,
        help="Path to YAML configuration file",
        type=str,
    )

    args = parser.parse_args()
    config_path = args.config

    timestamp = get_current_ts()

    pathutils = PathUtils(config_path, timestamp)
    logger = configure_logging(pathutils.output_dir)

    if not pathutils.is_config_valid():
        logger.error("Config not valid, exiting to inital screen...")
        return

    run_spec = resolve_run_spec(pathutils)
    jobs = run_spec.jobs
    logger.info(f"Resolved {len(jobs)} job(s):")
    for job in jobs:
        logger.info(f"  - {job.name} ({job.window} window)")

    is_batch = len(jobs) > 1
    success_count = 0
    video_file_pool_cache: dict[VideoSelection, VideoFilesPool] = {}

    for job in jobs:
        if is_batch:
            logger.info(f"Processing job: {job.name}")
        try:
            _process_job(job, run_spec, video_file_pool_cache, logger)
            success_count += 1
            if is_batch:
                logger.info(f"Successfully processed: {job.name}")
        except Exception as exc:
            if is_batch:
                logger.error(f"Error processing {job.name}: {exc}")
            else:
                logger.error(f"Error processing: {exc}")
                raise

    if is_batch:
        logger.info(
            f"Batch processing complete. Successfully processed "
            f"{success_count}/{len(jobs)} jobs"
        )
        if success_count != len(jobs):
            raise RuntimeError(
                f"Batch failed for {len(jobs) - success_count}/{len(jobs)} "
                "jobs; see the log for details"
            )


if __name__ == "__main__":
    main()
