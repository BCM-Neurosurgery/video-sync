# **Discontinuity in Json**

## **Discontinuity of Serial**

### **The Problem**

When analyzing `chunk_serial_data` from JSON metadata files, various forms of **discontinuities** may appear. These discontinuities can impact synchronization and downstream processing, requiring explicit handling. We categorize them as follows:

- **Type I Discontinuity**: Serial number drops to 0 and resumes from a value greater than 1.
- **Type II Discontinuity**: Serial resets from 0 to 1 and counts up (e.g., 1 → 127 → 0), then jumps back to original stream.
- **Type III Discontinuity**: Consecutive serial numbers differ by more than 1 (i.e., skipped values).
- **Type IV Discontinuity**: Serial number is `-1`, indicating a failed read or missing chunk.

These patterns are artifacts of the encoding and buffering system and do not necessarily indicate data loss.

---

### **Examples**

#### **Type I Discontinuity**
[YFC_20240719_091054.json](discontinuity-in-json/YFC_20240719_091054.json)

```json
"chunk_serial_data": [
        20323583,
        20323583,
        20323583,
        20323583,
        20323583
    ], 
    [
        0,
        0,
        0,
        0,
        0
    ],
    [
        20323585,
        20323585,
        20323585,
        20323585,
        20323585
    ],
```

#### **Type II Discontinuity**  
[YFC_20240719_091054.json](discontinuity-in-json/YFC_20240719_091054.json)

```json
"chunk_serial_data": [
        20332543,
        20332543,
        20332543,
        20332543,
        20332543
    ],
    [
        0,
        0,
        0,
        0,
        0
    ],
    [
        1,
        1,
        1,
        1,
        1
    ],
    ...
    [
        127,
        127,
        127,
        127,
        127
    ],
    [
        0,
        0,
        0,
        0,
        0
    ],
    [
        20332673,
        20332673,
        20332673,
        20332673,
        20332673
    ],
```

#### **Type III Discontinuity**  
[YFB_20240504_052717.json](discontinuity-in-json/YFB_20240504_052717.json)

```json
"chunk_serial_data": [
        30133802,
        30133802,
        30133803,
        30133803,
        30133803
    ],
    [
        30133804,
        30133804,
        30133804,
        30133804,
        30133804
    ],
```

#### **Type IV Discontinuity**  
[YFC_20240719_091054.json](discontinuity-in-json/YFC_20240719_091054.json)

```json
"chunk_serial_data": [
        20323571,
        20323571,
        -1,
        -1,
        -1
    ],
    [
        20323572,
        20323572,
        20323572,
        20323572,
        20323572
    ],
```

> When `chunk_serial_data == -1`, it is explicitly set by the acquisition software when serial data cannot be decoded correctly. See:

```python
frame_count = -1
if self.gpio_settings['line3'] == 'SerialOn':
    # We expect only 5 bytes to be sent
    if c.ChunkSerialDataLength == 5:
        chunk_serial_data = c.ChunkSerialData
        serial_msg = chunk_serial_data
        split_chunk = [ord(c) for c in chunk_serial_data]

        # Reconstruct the current count from the chunk serial data
        frame_count = 0
        for i, b in enumerate(split_chunk):
            frame_count |= (b & 0x7F) << (7 * i)

frame_metadata["chunk_serial_data"].append(frame_count)
```

---

### **Observation**

- **Type I** discontinuities appear frequently and follow a repeated gap pattern of 128, possibly due to buffer handling or chunk boundaries.
- **Type II** often occurs once per JSON, where a separate counting sequence briefly replaces the main stream.
- **Type III** skips are rare but detectable.
- **Type IV** values (-1) are often present at the beginning of the file or during transient serial glitches.

Despite these anomalies, the **total number of chunk serial entries matches the duration of the recording**, indicating no frames are lost:

```python
>>> with open(json_path, "r") as f:
>>>     json_dic = json.load(f)
>>> len(json_dic["chunk_serial_data"])
36000
```

---

### **Conclusion**

The analysis highlights a strong pattern of Type I discontinuities, suggesting a structured reset mechanism rather than random errors. The gaps of 128 could indicate an intentional segmentation in the data stream, possibly due to a recording or transmission mechanism.

In my implementation, I used the following function in `pyvideosync.fixanomaly` to correct the stream and produce continuous chunk serials and frame IDs:

```python
df = pd.DataFrame.from_records(res)
df = self.reconstruct_frame_id(df)

# Fix Type I and Type II discontinuities
chunk_serial_fixed = fix_discontinuities(df["chunk_serial_data"].tolist())
frame_id_fixed = fix_discontinuities(df["frame_ids_reconstructed"].tolist())

# Fix Type III jumps and Type IV -1s
continuous_chunk_serial = fill_array_gaps(chunk_serial_fixed)
continuous_frame_ids = fill_array_gaps(frame_id_fixed)
```


### **Download Example Data**

- [2024-07-19_09:10:54_chunk_discontinuities.json](discontinuity-in-json/2024-07-19_09:10:54_chunk_discontinuities.json)
- [YFC_20240719_091054.json](discontinuity-in-json/YFC_20240719_091054.json)
- [Jupyter Notebook to Reproduce Results](notebooks/json_discontinuities.ipynb)


## **Discontinuity of Frame ID**

### **The Problem**

In some cases, the JSON metadata file shows frame counters that jump unexpectedly. However, the **total frame count** remains consistent across multiple verification methods, suggesting that frames are **not actually lost**, but rather the frame ID counter has anomalies.

---

### **Examples**

#### **Type III Discontinuity**  
[`YFB_20240504_052717.json`](discontinuity-in-json/YFB_20240504_052717.json)

```json
{
  "frames": [
    [19393, 19393, 19392, 19393, 19392],
    [19400, 19400, 19399, 19400, 19399]
  ]
}
```

In this case, the frame IDs jump from `19392 → 19399`, indicating a possible counter skip.

#### **Special Discontinuity (Overflow)**  
[`YFB_20240504_052717.json`](discontinuity-in-json/YFB_20240504_052717.json)

```json
[
    65534, 65534, 65535, 65535, 65535
],
[
    65535, 65535, 1, 1, 1
],
[
    1, 1, 2, 2, 2
],
[
    2, 2, 3, 3, 3
]
```

This suggests a **16-bit counter overflow** where the frame ID resets after reaching `65535`.

---

### **Observations**

Even when frame IDs show discontinuities:

```python
>>> len(yfb_json["frame_id"])
18000
```

The count still returns `18000` frames, indicating **no data loss**.

Verifying the video file with `ffmpeg` confirms the full frame count:

```python
import subprocess

def count_frames_ffmpeg(video_path: str) -> int:
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-count_packets", "-show_entries", "stream=nb_read_packets",
        "-of", "csv=p=0", video_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return int(result.stdout.strip())
```

Alternatively, with OpenCV:

```python
self.frame_count = int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))
```

Both methods confirm the actual number of frames rendered in the MP4 file matches expectations.

---

### **Conclusion**

The irregularities in `frame_id` (such as jumps or resets) are best understood as **counter inconsistencies**, not actual frame drops.

- **Total frame count is preserved** in both metadata and video.
- **Frame ID jumps** (e.g., `19392 → 19399`) or overflows (e.g., `65535 → 1`) are internal to the acquisition system or serialization process.
- This issue is a **metadata anomaly**, not a data loss or sync error.

These anomalies **do not affect** the video content and can be corrected or ignored during post-processing.

---

### **Download Reference JSON File**

- [`YFB_20240505_133351.json`](discontinuity-in-json/YFB_20240505_133351.json)
