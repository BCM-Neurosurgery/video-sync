# Understanding JSON

This section explains how JSON metadata is generated and saved during acquisition using the multi-camera recording system.

## How JSON is Saved

The JSON metadata is assembled during each recording loop iteration and written asynchronously to disk via a dedicated thread. This ensures that JSON saving does not block the main acquisition loop.

Relevant code:

```python
frame_metadata = {"real_times": real_time, "local_times": local_time, "base_filename": self.video_base_file}

frame_metadata["timestamps"] = []
frame_metadata["frame_id"] = []
frame_metadata["frame_id_abs"] = []
frame_metadata["chunk_serial_data"] = []
frame_metadata["serial_msg"] = []
frame_metadata["camera_serials"] = []
frame_metadata["exposure_times"] = []
frame_metadata["frame_rates_requested"] = []
frame_metadata["frame_rates_binning"] = []
```

Each frame's metadata is appended to this dictionary. After all cameras are processed for a single frame, the following call queues the metadata to be written:

```python
self.json_queue.put(frame_metadata)
```

Later, a thread runs `write_metadata_queue(...)` to write this metadata to JSON file(s).

## How JSON is Grouped with MP4 Files

During recording, both video and JSON metadata files are saved in **segments** (or chunks) to prevent excessive memory usage and to maintain system stability over long recordings.

For example, a 10-minute recording may result in multiple `.mp4` files per each camera and a corresponding `.json` metadata file:

```bash
-r--r-----+ 1 root datalake 441M Mar 18 11:30 YFMDatafile_20250318_110436.18486638.mp4
-r--r-----+ 1 root datalake 323M Mar 18 11:30 YFMDatafile_20250318_110436.18486644.mp4
-r--r-----+ 1 root datalake 216M Mar 18 11:30 YFMDatafile_20250318_110436.23505577.mp4
-r--r-----+ 1 root datalake 717M Mar 18 11:30 YFMDatafile_20250318_110436.23512012.mp4
-r--r-----+ 1 root datalake 233M Mar 18 11:30 YFMDatafile_20250318_110436.23512013.mp4
-r--r-----+ 1 root datalake 232M Mar 18 11:30 YFMDatafile_20250318_110436.23512014.mp4
-r--r-----+ 1 root datalake 362M Mar 18 11:30 YFMDatafile_20250318_110436.23512906.mp4
-r--r-----+ 1 root datalake 623M Mar 18 11:30 YFMDatafile_20250318_110436.23512908.mp4
-r--r-----+ 1 root datalake 9.4M Mar 18 11:30 YFMDatafile_20250318_110436.json
```

### Filename Format

The filenames follow the pattern:

```
<base_name>_<YYYYMMDD_HHMMSS>.<camera_serial>.mp4
```

- `base_name` is derived from the `recording_path` set at the beginning of acquisition.
- `YYYYMMDD_HHMMSS` represents the date and time at which the segment began recording.
- Each camera serial is appended as a suffix to distinguish between files from multiple cameras.
- A single `.json` file is generated for each chunk and contains metadata for **all cameras** in that segment.

The JSON filename does **not** have a camera serial suffix because it aggregates metadata across all cameras.

### Chunking Mechanism

The system is configured to split files every _N_ frames using the `video_segment_len` field from the camera config:

```python
video_segment_len = self.camera_config["acquisition-settings"]["video_segment_len"]
```

When this number of frames is reached:

- A new filename is generated using the current timestamp.
- New threads continue writing to the newly created files.
- JSON and video saving continue uninterrupted.

```python
if frame_idx % total_frames == 0:
    prog = tqdm(total=total_frames)
    frame_idx = 0

    if self.video_base_file is not None:
        # Create a new video_base_filename for the new video segment
        now = datetime.now()
        time_str = now.strftime("%Y%m%d_%H%M%S")

        # Update base name and file path
        self.video_base_name = "_".join([self.video_root, time_str])
        self.video_base_file = os.path.join(self.video_path, self.video_base_name)
```

## How JSON is Structured

For each recorded frame (per camera), the following fields are recorded:

- `timestamps`: Hardware timestamps from the camera.
- `frame_id`: The local frame number (may reset per segment).
- `frame_id_abs`: The absolute frame ID from chunk metadata.
- `chunk_serial_data`: Frame counter reconstructed from 5-byte serial message (if `SerialOn` is enabled).
- `serial_msg`: The raw 5-byte message received over serial.
- `camera_serials`: Camera serial number (device ID).
- `exposure_times`: Exposure time for each frame.
- `frame_rates_requested`: The requested acquisition frame rate.
- `frame_rates_binning`: The effective frame rate after binning.

These fields are updated per camera inside a loop:

```python
for c in self.cams:
    im_ref = c.get_image()
    timestamp = im_ref.GetTimeStamp()
    chunk_data = im_ref.GetChunkData()
    frame_id = im_ref.GetFrameID()
    frame_id_abs = chunk_data.GetFrameID()

    # Serial decoding
    serial_msg = []
    frame_count = -1
    if self.gpio_settings['line3'] == 'SerialOn':
        if c.ChunkSerialDataLength == 5:
            chunk_serial_data = c.ChunkSerialData
            serial_msg = chunk_serial_data
            split_chunk = [ord(c) for c in chunk_serial_data]

            frame_count = 0
            for i, b in enumerate(split_chunk):
                frame_count |= (b & 0x7F) << (7 * i)

    frame_metadata["timestamps"].append(timestamp)
    frame_metadata["frame_id"].append(frame_id)
    frame_metadata["frame_id_abs"].append(frame_id_abs)
    frame_metadata["chunk_serial_data"].append(frame_count)
    frame_metadata["serial_msg"].append(serial_msg)
    frame_metadata["camera_serials"].append(c.DeviceSerialNumber)
    frame_metadata["exposure_times"].append(c.ExposureTime)
    frame_metadata["frame_rates_binning"].append(c.BinningHorizontal * 30)
    frame_metadata["frame_rates_requested"].append(c.AcquisitionFrameRate)
```

This loop ensures that the metadata per frame and per camera is stored in a synchronized fashion and saved with high fidelity.
