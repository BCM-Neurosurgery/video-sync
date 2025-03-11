# 🔄 Program Flow

This section explains the **data processing flow** of `video-sync`.

### 1. Configuration

In main.py, we load and validate the configuration using the `PathUtils` class.

```python
timestamp = get_current_ts()

pathutils = PathUtils(config_path, timestamp)
logger = configure_logging(pathutils.output_dir)

if not pathutils.is_config_valid():
    logger.error("Config not valid, exiting to inital screen...")
    return
```

This ensures the configuration is valid before proceeding with synchronization.

### 2. Data Integrity Check

The DataPool class ensures all required neural and camera files are present.

If files are missing, the process stops.

```python
datapool = DataPool(pathutils.nsp_dir, pathutils.cam_recording_dir)

if not datapool.verify_integrity():
    logger.error(
        "File integrity check failed: Missing or duplicate NSP files detected. "
        "Please verify the directory structure and try again. Returning to the initial screen."
    )
    return
```

### 3. Extracting Neural Data (NEV)

This step extracts and reconstructs chunk serial data in the format of a dataframe from the stitched NSP-1 `.nev` file, which contains event-based neural data. The chunk serial values are reconstructed by combining **five split chunks** of serial communication sent from an Arduino.

```python
# 1. Get NEV serial start and end
nsp1_nev_path = datapool.get_nsp1_nev_path()
nev = Nev(nsp1_nev_path)
nev_chunk_serial_df = nev.get_chunk_serial_df()
logger.info(f"NEV dataframe\n: {nev_chunk_serial_df}")
nev_start_serial, nev_end_serial = get_column_min_max(
    nev_chunk_serial_df, "chunk_serial"
)
logger.info(f"Start serial: {nev_start_serial}, End serial: {nev_end_serial}")
```

The script first retrieves the NSP-1 `.nev` file path and initializes an instance of the Nev class to parse its contents. It then calls `get_chunk_serial_df()`, which reconstructs the chunk serials by combining the five split parts. This reconstructed DataFrame provides a sequential timeline of neural events, essential for aligning with video data.

To establish the valid time range for synchronization, the script determines **the earliest and latest chunk serial values** from the NEV data using `get_column_min_max()`. These values define the window in which video frames should be extracted later to ensure proper alignment.


### 4. Identifying Relevant Video and Metadata Files for Synchronization

To ensure proper alignment between neural and video data, the script identifies which camera recordings overlap with the neural event (NEV) time range. Each video recording has an associated JSON metadata file containing start and end chunk serials, which are extracted and compared against the NEV serial range.

To optimize performance, the script first checks if previously computed timestamps exist in `timestamps.json`. If found, these timestamps are used directly to skip redundant processing. Otherwise, the script iterates through all available JSON metadata files, extracting their chunk serials and determining whether they overlap with the neural recording. If a video’s serial range falls within the NEV range, its timestamp is added to the processing list.

Once all relevant timestamps are identified, they are saved to `timestamps.json` for future runs and **sorted** to maintain chronological order. This approach ensures that only the necessary video files are processed, reducing computational overhead while maintaining precise synchronization.

```python
# 3. load camera serials from the config file
camera_serials = pathutils.cam_serial
logger.info(f"Camera serials loaded from config: {camera_serials}")

# 4. Go through all JSON files and find the ones that
# are within the NEV serial range
# read timestamps if available
timestamps_path = os.path.join(pathutils.output_dir, "timestamps.json")
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
        start_serial, end_serial = videojson.get_min_max_chunk_serial()
        if start_serial is None or end_serial is None:
            logger.error(f"No chunk serials found in JSON file: {json_path}")
            continue

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
```

### 5. Processing Videos for Synchronization

Once the relevant timestamps are identified, this part of the script processes video files to align them with neural data. The workflow can be divided into two phases:

- Before Processing Videos → Extract and merge neural and video data.
- After Processing Videos → Generate subclips, add synchronized audio, and export the final video.

#### Before Processing Videos: Extracting and Merging Data

The script iterates over each camera serial number and processes the corresponding video recordings. For each timestamp, it loads the associated camera metadata JSON file, extracts frame information, and filters the frames that overlap with the NEV chunk serial range.

```python
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
        camera_df["frame_ids_relative"] = (
            camera_df["frame_ids_reconstructed"]
            - camera_df["frame_ids_reconstructed"].iloc[0]
            + 1
        )

        camera_df = camera_df.loc[
            (camera_df["chunk_serial_data"] >= nev_start_serial)
            & (camera_df["chunk_serial_data"] <= nev_end_serial)
        ]
```

The filtered camera frame data is then **merged with the NEV chunk serials on serial** to create a synchronized dataset. Next, the script extracts continuous neural/audio signals (NS5 data) for the same time window and merges them with the existing dataset. This results in a combined DataFrame containing timestamped neural/audio data, camera frame IDs, and amplitudes from the NS5 file.

Note: the audio signal and the neural data are all arrays in the same format in NS5, so they can be processed in the same way.

```python
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
                "frame_id",
                "frame_ids_reconstructed",
                "frame_ids_relative",
            ]
        ]
```

If a matching MP4 file is found for the timestamp, it is added to the processing list. After iterating through all timestamps, the merged data for the camera serial is stored and logged for validation.

```python
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
```

#### After Processing Videos: Synchronizing and Exporting

With the synchronized DataFrame ready, the script processes the corresponding video files. It iterates through each unique MP4 file and **extracts relevant frames** based on the filtered timestamps. Using `make_synced_subclip_ffmpeg()`, the script generates subclips, attaching the audio data at 30 kHz.

```python
for camera_serial in camera_serials:
    ...
    # process the videos
    video_output_dir = os.path.join(pathutils.output_dir, camera_serial)
    os.makedirs(video_output_dir, exist_ok=True)
    video_output_path = os.path.join(video_output_dir, "output.mp4")

    subclip_paths = []
    for mp4_path in all_merged_df["mp4_file"].unique():
        df_sub = all_merged_df[all_merged_df["mp4_file"] == mp4_path]

        # Build a subclip from the relevant frames, attach audio
        subclip = make_synced_subclip_ffmpeg(
            df_sub,
            mp4_path,
            fps_audio=30000,  # 30kHz
            out_dir=os.path.join(pathutils.output_dir, camera_serial),
        )
        subclip_paths.append(subclip)
```

If multiple subclips are generated, they are concatenated into a single video using `ffmpeg_concat_mp4s()`. Finally, the fully synchronized video is saved to the output directory, completing the alignment process. This ensures that the final exported video is precisely synchronized with continuous audio amplitude signals.

```python
    # Now 'subclip_paths' has each final MP4 subclip
    # If we have only one, just rename or copy it
    if len(subclip_paths) == 1:
        final_path = subclip_paths[0]
    else:
        final_path = os.path.join(
            pathutils.output_dir, camera_serial, f"stitched_{camera_serial}.mp4"
        )
        ffmpeg_concat_mp4s(subclip_paths, final_path)

    logger.info(f"Saved {camera_serial} to {video_output_path}")
```
