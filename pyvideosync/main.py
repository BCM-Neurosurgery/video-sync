"""
Main function to orchestrate the loading, processing, and merging of NEV, NS5, and camera data,
and aligning the audio with the video.
"""

import os
from pyvideosync.data_pool import DataPool
import pandas as pd
from pyvideosync.logging_config import (
    get_current_ts,
    configure_logging,
)
from pyvideosync.pathutils import PathUtils
from pyvideosync.process import (
    ffmpeg_concat_mp4s,
    ffmpeg_concat_mp4s_gpu,
    make_synced_subclip_ffmpeg,
    make_synced_subclip_moviepy,
    make_synced_subclip_moviepy_gpu,
)
from pyvideosync.utils import (
    load_timestamps,
    save_timestamps,
    sort_timestamps,
    get_column_min_max,
    get_json_file,
    get_mp4_file,
)
from pyvideosync.videojson import Videojson
from pyvideosync.nev import Nev
from pyvideosync.nsx import Nsx
from pyvideosync.sidecar import write_ns3_sidecar
import argparse
import glob
import json
import shutil
import uuid


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

    # Build the list of sessions to process. Each entry is a tuple:
    #   (task_name, nsp_dir, nev_path_or_None, ns5_path_or_None, ns3_path_or_None)
    # Explicit paths are populated only in flat-batch mode (where multiple
    # chunks coexist in one directory). In single/subdir modes the slots stay
    # None and DataPool resolves files from `nsp_dir`.
    sessions: list[tuple[str, str, str | None, str | None, str | None]] = []
    if pathutils.is_batch_mode():
        logger.info("Running in subdir batch processing mode")
        base_dir = pathutils._config.get("base_dir")
        keywords = pathutils._config.get(
            "keywords", pathutils._config.get("keyword", [])
        )
        matching_dirs = pathutils.get_matching_task_dirs(base_dir, keywords)
        if not matching_dirs:
            logger.error("No matching task directories found")
            return
        logger.info(f"Found {len(matching_dirs)} matching directories:")
        for dir_path in matching_dirs:
            logger.info(f"  - {dir_path}")
        sessions = [(os.path.basename(d), d, None, None, None) for d in matching_dirs]
    elif pathutils.is_flat_batch_mode():
        logger.info("Running in flat-file batch processing mode")
        flat_dir = pathutils._config.get("flat_dir")
        keywords = pathutils._config.get(
            "keywords", pathutils._config.get("keyword", None)
        )
        flat_sessions = pathutils.get_flat_nev_session_files(flat_dir, keywords)
        if not flat_sessions:
            logger.error("No nev/ns5 sessions found in flat_dir")
            return
        logger.info(f"Found {len(flat_sessions)} sessions in {flat_dir}:")
        for task_name, _, _, ns3 in flat_sessions:
            logger.info(f"  - {task_name}{' (no ns3)' if ns3 is None else ''}")
        sessions = [
            (name, flat_dir, nev, ns5, ns3) for name, nev, ns5, ns3 in flat_sessions
        ]
    else:
        logger.info("Running in single directory mode")
        sessions = [
            (
                os.path.basename(pathutils.nsp_dir),
                pathutils.nsp_dir,
                None,
                None,
                None,
            )
        ]

    is_batch = pathutils.is_batch_mode() or pathutils.is_flat_batch_mode()
    success_count = 0

    for task_name, nsp_dir, nev_path, ns5_path, ns3_path in sessions:
        if is_batch:
            logger.info(f"Processing session: {task_name}")

        try:
            # Create datapool for this session (explicit paths used in flat mode).
            datapool = DataPool(
                nsp_dir,
                pathutils.cam_recording_dir,
                nev_path=nev_path,
                ns5_path=ns5_path,
                ns3_path=ns3_path,
            )

            # Create output directory named after the session (task) name
            current_output_dir = os.path.join(pathutils.output_dir, task_name)

            os.makedirs(current_output_dir, exist_ok=True)

            if not datapool.verify_integrity():
                logger.error(
                    "File integrity check failed: Missing or duplicate NSP files detected. "
                    "Please verify the directory structure and try again. Returning to the initial screen."
                )
                if is_batch:
                    continue
                else:
                    return

            # 1. Get NEV serial start and end
            nsp1_nev_path = datapool.get_nev_path()
            nev = Nev(nsp1_nev_path)
            nev_chunk_serial_df = nev.get_chunk_serial_df()
            logger.info(f"NEV dataframe\n: {nev_chunk_serial_df}")
            nev_start_serial, nev_end_serial = get_column_min_max(
                nev_chunk_serial_df, "chunk_serial"
            )
            logger.info(
                f"Start serial: {nev_start_serial}, End serial: {nev_end_serial}"
            )

            # Optional NS3 sidecar: all-channel HDF5 sliced by the NEV TimeStamps
            # range. Emitted once per session, before per-camera processing.
            if pathutils.ns3_sidecar:
                ns3_resolved = datapool.get_ns3_path()
                if ns3_resolved:
                    _emit_ns3_sidecar(
                        ns3_resolved,
                        nev_chunk_serial_df,
                        current_output_dir,
                        task_name,
                        logger,
                    )
                else:
                    logger.warning(
                        f"ns3_sidecar enabled but no .ns3 resolved for {task_name}"
                    )

            # 2. Find all JSON files and MP4 files
            camera_files = datapool.get_video_file_pool().list_groups()
            if not camera_files:
                logger.error("No camera files found")
                if is_batch:
                    continue
                else:
                    return

            # 3. Go through all JSON files and find the ones that
            # are within the NEV serial range
            # read timestamps if available
            timestamps_path = os.path.join(current_output_dir, "timestamps.json")
            timestamps = load_timestamps(timestamps_path, logger)
            if timestamps:
                logger.info(f"Loaded timestamps: {timestamps}")
            else:
                logger.info("No timestamps found")
                timestamps = []
                for timestamp, camera_file_group in camera_files.items():

                    json_path = get_json_file(camera_file_group, pathutils)
                    if json_path is None:
                        logger.error(f"No JSON file found in group {timestamp}")
                        continue

                    videojson = Videojson(json_path)
                    if not videojson.is_valid():
                        logger.error(f"Invalid JSON file: {json_path}")
                        continue

                    start_serial, end_serial = videojson.get_min_max_chunk_serial()
                    if start_serial is None or end_serial is None:
                        logger.error(
                            f"No chunk serials found in JSON file: {json_path}"
                        )
                        continue

                    if start_serial > nev_end_serial:
                        logger.info(f"Past end serial: {timestamp}")
                        break

                    if end_serial < nev_start_serial:
                        logger.info(f"No overlap found: {timestamp}")
                        continue

                    elif start_serial <= nev_end_serial:
                        logger.info(f"Overlap found, timestamp: {timestamp}")
                        timestamps.append(timestamp)

                    else:
                        logger.info(f"Break: {timestamp}")
                        break
                logger.info(f"timestamps: {timestamps}")
                save_timestamps(timestamps_path, timestamps)

            sorted_timestamps = sort_timestamps(timestamps)

            # 4. Get available camera serials from overlapping JSON files only
            if pathutils.cam_serial:
                camera_serials = pathutils.cam_serial
                logger.info(f"Camera serials loaded from config: {camera_serials}")
            else:
                # Auto-detect camera serials from JSON files with overlapping timestamps
                available_serials = set()
                for timestamp in sorted_timestamps:
                    camera_file_group = camera_files[timestamp]
                    json_path = get_json_file(camera_file_group, pathutils)
                    if json_path:
                        videojson = Videojson(json_path)
                        if videojson.is_valid():
                            json_serials = videojson.get_camera_serials()
                            available_serials.update(json_serials)

                camera_serials = list(available_serials)
                logger.info(
                    f"Auto-detected camera serials from overlapping JSONs: {camera_serials}"
                )

            if not camera_serials:
                logger.error(
                    "No camera serials found (either in config or overlapping JSON files)"
                )
                if is_batch:
                    continue
                else:
                    return

            # process NS5 channel data
            ns5_path = datapool.get_ns5_path()
            ns5 = Nsx(ns5_path)

            # 5. Go through the timestamps and process the videos
            for camera_serial in camera_serials:
                all_merged_list = []

                for i, timestamp in enumerate(sorted_timestamps):
                    camera_file_group = camera_files[timestamp]

                    json_path = get_json_file(camera_file_group, pathutils)
                    if json_path is None:
                        logger.error(f"No JSON file found in group {timestamp}")
                        continue

                    videojson = Videojson(json_path)
                    camera_df = videojson.get_camera_df(camera_serial)

                    camera_df = camera_df.loc[
                        (camera_df["chunk_serial_data"] >= nev_start_serial)
                        & (camera_df["chunk_serial_data"] <= nev_end_serial)
                    ]

                    chunk_serial_joined = nev_chunk_serial_df.merge(
                        camera_df,
                        left_on="chunk_serial",
                        right_on="chunk_serial_data",
                        how="inner",
                    )

                    logger.info("Processing ns5 filtered channel df...")
                    ns5_slice = ns5.get_filtered_channel_df(
                        pathutils.ns5_channel,
                        chunk_serial_joined.iloc[0]["TimeStamps"],
                        chunk_serial_joined.iloc[-1]["TimeStamps"],
                    )

                    logger.info("Merging ns5 and chunk serial df...")
                    all_merged = ns5_slice.merge(
                        chunk_serial_joined,
                        left_on="TimeStamp",
                        right_on="TimeStamps",
                        how="left",
                    )

                    all_merged = all_merged[
                        [
                            "TimeStamp",
                            "Amplitude",
                            "chunk_serial",
                            "mp4_frame_idx",  # we only need the mp4_frame_idx
                        ]
                    ]

                    mp4_path = get_mp4_file(camera_file_group, camera_serial, pathutils)
                    if mp4_path is None:
                        logger.error(f"No MP4 file found in group {timestamp}")
                        continue

                    all_merged["mp4_file"] = mp4_path
                    all_merged_list.append(all_merged)

                if not all_merged_list:
                    logger.warning(f"No valid merged data for {camera_serial}")
                    continue

                all_merged_df = pd.concat(all_merged_list, ignore_index=True)
                logger.info(
                    f"Final merged DataFrame for {camera_serial} head:\n{all_merged_df.head()}"
                )
                logger.info(
                    f"Final merged DataFrame for {camera_serial} tail:\n{all_merged_df.tail()}"
                )

                # process the videos
                video_output_dir = os.path.join(current_output_dir, camera_serial)
                os.makedirs(video_output_dir, exist_ok=True)

                session_uuid = str(uuid.uuid4())[:8]
                subclip_paths = []
                for mp4_path in all_merged_df["mp4_file"].unique():
                    df_sub = all_merged_df[all_merged_df["mp4_file"] == mp4_path]

                    # Build a subclip from the relevant frames, attach audio
                    # Use GPU acceleration if enabled
                    if pathutils.gpu_enabled:
                        subclip = make_synced_subclip_moviepy_gpu(
                            df_sub,
                            mp4_path,
                            os.path.join(current_output_dir, camera_serial),
                            session_uuid,
                            gpu_enabled=pathutils.gpu_enabled,
                            gpu_type=pathutils.gpu_type,
                        )
                    else:
                        subclip = make_synced_subclip_moviepy(
                            df_sub,
                            mp4_path,
                            os.path.join(current_output_dir, camera_serial),
                            session_uuid,
                        )
                    subclip_paths.append(subclip)

                # Final video name follows the session task name
                final_video_name = f"{task_name}.mp4"

                final_path = os.path.join(
                    current_output_dir, camera_serial, final_video_name
                )
                # Now 'subclip_paths' has each final MP4 subclip
                # If we have only one, just rename or copy it
                if len(subclip_paths) == 1:
                    shutil.move(subclip_paths[0], final_path)
                else:
                    # Use GPU-accelerated concat if enabled
                    if pathutils.gpu_enabled:
                        ffmpeg_concat_mp4s_gpu(
                            subclip_paths,
                            final_path,
                            gpu_enabled=pathutils.gpu_enabled,
                            gpu_type=pathutils.gpu_type,
                        )
                    else:
                        ffmpeg_concat_mp4s(subclip_paths, final_path)

                logger.info(f"Saved {camera_serial} to {final_path}")

                window_path = os.path.join(
                    current_output_dir, camera_serial, f"{task_name}_window.json"
                )
                with open(window_path, "w") as f:
                    json.dump(
                        {
                            "ts_start": int(all_merged_df["TimeStamp"].min()),
                            "ts_end": int(all_merged_df["TimeStamp"].max()),
                            "samp_per_s": ns5.sampleResolution
                            / ns5.basic_header["Period"],
                            "channel_name": pathutils.ns5_channel,
                        },
                        f,
                        indent=2,
                    )
                logger.info(f"Wrote NS5 window: {window_path}")

                if not pathutils.keep_intermediates:
                    cam_dir = os.path.join(current_output_dir, camera_serial)
                    patterns = [
                        "*_subclip_*.mp4",
                        "*_audio_*.wav",
                        "*_final_*.mp4",
                        "concat_filelist.txt",
                    ]
                    removed = 0
                    for pat in patterns:
                        for path in glob.glob(os.path.join(cam_dir, pat)):
                            if path == final_path:
                                continue
                            try:
                                os.remove(path)
                                removed += 1
                            except OSError as e:
                                logger.warning(f"Could not remove {path}: {e}")
                    logger.info(
                        f"Cleaned {removed} intermediate file(s) from {cam_dir}"
                    )

            # Track success for batch modes
            if is_batch:
                success_count += 1
                logger.info(f"Successfully processed: {task_name}")

        except Exception as e:
            if is_batch:
                logger.error(f"Error processing {task_name}: {str(e)}")
            else:
                logger.error(f"Error processing: {str(e)}")
                raise

    # Log batch processing results
    if is_batch:
        logger.info(
            f"Batch processing complete. Successfully processed {success_count}/{len(sessions)} sessions"
        )


if __name__ == "__main__":
    main()
