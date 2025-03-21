# Understanding NS5

BlackRock NSx files (`.ns1` through `.ns9`) contain **continuously sampled data** from electrophysiological recordings, such as raw voltage traces, local field potentials (LFP), or EMG signals. The number `x` in the file extension corresponds to the sampling rate tier — for example, `.ns1` might store lower-rate LFP data (e.g., 500 Hz), while `.ns5` typically stores high-resolution raw data sampled at 30,000 Hz.

These files are **written in a time non-decreasing manner** and are typically paired with a `.nev` file that contains spike events and digital triggers. For instance, the files `experiment.nev` and `experiment.ns5` together represent the full set of spike events and high-resolution continuous signals for a recording session.

It is important to note that:
- An NSx file can exist independently of a NEV file, and vice versa.
- Multiple NSx files (e.g., `.ns2`, `.ns6`) may exist in the same recording session if continuous sampling was performed at multiple rates.
- The `.ns5` file is most commonly used when raw neural data is acquired at the **highest available sampling rate (30 kHz)**.

This section provides guidance on how to interpret and process `.ns5` files, including reading the header structure, decoding the data blocks, and aligning NS5 signals with NEV-based events like triggers or serial pulses.

## NS5 File Structure

Ns5 is...

A Ns5 file consists of three main components:

- Basic Header
- Extended Headers
- Data Packets

You can load a `.ns5` file by

```python
from pyvideosync.nsx import Nsx
ns5_path = "/path/to/ns5"
ns5 = Nsx(ns5_path)
```

### Basic Header

The **Basic Header** provides essential metadata about the `.ns5` file and its structure. It is always located at the beginning of the file and defines how to interpret the rest of the data. All multi-byte values are stored in **little-endian format**, and character arrays may not be null-terminated unless they are shorter than the maximum allowed length.

Below is an example output of the parsed NS5 basic header using the `get_basic_header()` method:

```python
>>> ns5.get_basic_header()
{'FileTypeID': 'BRSMPGRP',
 'SampleResolution': 30000,
 'FileSpec': '3.0',
 'BytesInHeader': 710,
 'Label': '30 kS/s',
 'Comment': '',
 'Period': 1,
 'TimeStampResolution': 30000,
 'TimeOrigin': datetime.datetime(2024, 7, 17, 13, 35, 39, 30000),
 'ChannelCount': 6}
```

Explanation of fields

| Field                 | Description |
|----------------------|-------------|
| `FileTypeID`         | Always set to `"BRSMPGRP"`, indicating a Neural Continuous Data file. Earlier versions may use `"NEURALSG"` or `"NEURALCD"`. |
| `FileSpec`           | File specification version, represented as major and minor (e.g., `'3.0'` corresponds to version 3.0). |
| `BytesInHeader`      | Total number of bytes in the combined standard and extended headers. Also serves as the byte offset to the first data packet. |
| `Label`              | A human-readable label for the sampling group (e.g., `"30 kS/s"` or `"LFP Low"`). |
| `Comment`            | Optional descriptive comment about the file or recording session. |
| `Period`             | Number of 1/30,000 second intervals between data points. A value of `1` implies a 30,000 Hz sampling rate. A value of `3` would indicate 10,000 Hz. |
| `TimeStampResolution`| Frequency of the global time base (in counts per second). Typically `30,000`, indicating that each timestamp unit equals 1/30,000 seconds. |
| `TimeOrigin`         | The UTC time at which the recording began. This is considered time zero for the timestamp values. |
| `ChannelCount`       | Total number of continuously sampled channels in this file. This should match the number of extended headers that follow. |

### Extended Headers

The NS5 file includes one extended header per continuously sampled channel. These headers describe how each electrode channel was configured during acquisition. The number of extended headers corresponds to the ChannelCount specified in the basic header.

The standard format for each extended header includes:

| Field | Description | 
|-----------------------|-----------------| 
| `Type` | Always set to "CC" (Continuous Channel), indicating this is an extended header for continuous data. | 
| `ElectrodeID` | Unique identifier for the electrode. This ID matches the electrode numbers in the corresponding NEV file. | 
| `ElectrodeLabel` | A human-readable label or name for the electrode (e.g., "elec1"). | 
| `PhysicalConnector` | The physical bank or system connector to which the electrode is attached. For example: 1 = Bank A, 2 = Bank B, etc. | 
| `ConnectorPin` | The specific pin number on the connector where the electrode is connected (typically 1–37). | 
| `MinDigitalValue` | Minimum digital value of the signal (e.g., -8192). | 
| `MaxDigitalValue` | Maximum digital value of the signal (e.g., 8192). | 
| `MinAnalogValue` | Minimum analog value after scaling, typically in microvolts or millivolts (e.g., -5000). | 
| `MaxAnalogValue` | Maximum analog value after scaling (e.g., 5000). | 
| `Units` | Unit of measurement for the analog values (e.g., "μV" or "mV"). | 
| `HighFreqCorner` | The upper cutoff frequency of the signal filter in millihertz. | 
| `HighFreqOrder` | Order of the high-pass filter applied (e.g., 4 for a 4th-order filter). | 
| `HighFilterType` | Type of high-pass filter used. 0 = NONE, 1 = Butterworth. | 
| `LowFreqCorner` | The lower cutoff frequency of the signal filter in millihertz. | 
| `LowFreqOrder` | Order of the low-pass filter applied. | 
| `LowFilterType` | Type of low-pass filter used. 0 = NONE, 1 = Butterworth. |

Each of these entries helps interpret the scale and filtering applied to the raw neural signals stored in the NS5 file.

You can also render the extended headers using:

```python
>>> ns5.get_extended_headers_df()
```

{{ read_csv('understanding-ns5/extended_headers_df.csv') }}


### Data Packets

The third section of an NS5 file contains the actual recorded data: time-stamped packets of continuously sampled neural signals. Each **data packet** begins with a small header, followed by a timestamp, the number of data points, and the data values themselves.

According to Blackrock’s NSx file specification (Rev 7.00, Page 18):

| **Field**               | **Type**         | **Length (Bytes)** | **Description** |
|-------------------------|------------------|---------------------|-----------------|
| `Header`                | `Byte`           | 1                   | Always set to `0x01` to indicate the start of a data packet. |
| `Timestamp`             | `Unsigned int64` | 8                   | The global timestamp for when this block of data begins. The unit is determined by `TimeStampResolution` in the basic header. |
| `NumDataPoints`         | `Unsigned int32` | 4                   | The number of data points that follow this header. |
| `DataPoints`            | `Array of int16` | Variable            | The sampled voltage values. There are `ChannelCount` values for each time point, one per channel, repeated for `NumDataPoints`. |

All data points are stored in **channel-major** order (i.e., samples from all channels at the same time step are grouped together), and the timestamps always **increase monotonically**.

These packets can also be used to **indicate acquisition gaps** or pauses in recording — if multiple packets appear, it's usually because the file was paused or segmented.

You can access the continuous data using the `get_data()` method:

```json
{
  'start_time_s': 0.0,
  'data_time_s': 'all',
  'downsample': 1,
  'elec_ids': [257, 258, 259, 260, 261, 262],
  'data_headers': [{
      'Timestamp': 4057455182,
      'NumDataPoints': 38332687,
      'data_time_s': 1277.756
  }],
  'data': [memmap(..., dtype=int16)],
  'samp_per_s': 30000.0
}
```

- **start_time_s**: Time in seconds corresponding to the first timestamp (usually 0).
- **elec_ids**: List of electrode (channel) IDs in the order of the data.
- **data_headers**: Contains metadata like the starting timestamp and the number of data points in each segment.
- **data**: A NumPy `memmap` array representing the signal data. Each row corresponds to a different channel.
- **samp_per_s**: The sampling rate, typically 30,000 Hz.

## How Audio/Neuro Data is Encoded

In the NS5 file format, audio and neural data are stored as **continuous analog signals** recorded from multiple channels at high sampling rates (e.g., 30,000 Hz). These signals are organized in **data packets**, each containing:

- A global timestamp indicating when the data block begins.
- A fixed number of data points sampled uniformly over time.
- One sample per channel per timestamp, stored as 16-bit signed integers.

This layout ensures accurate alignment between channels and enables consistent decoding of the analog waveform over time.

Each **channel** (e.g., a microphone or electrode) has metadata stored in the **extended headers**, such as the channel label, pin number, analog range, and filter settings.

To access the raw signal from a particular channel, the following function retrieves the corresponding row in the `memmap` array:

```python
def get_channel_array(self, channel: str):
    """
    Retrieve the raw analog signal array from a specific channel.

    Args:
        channel (str): The electrode or microphone label (e.g., "RoomMic2").

    Returns:
        np.ndarray: 1D array of raw amplitude values.
    """
    row_index = self.extended_headers_df[
        self.extended_headers_df["ElectrodeLabel"] == channel
    ].index.item()
    return self.memmapData[row_index]
```

To convert the raw array into a time-aligned DataFrame:

```python
def get_channel_df(self, channel: str):
    """
    Construct a DataFrame for a specific channel with timestamp and amplitude.

    Returns:
        pd.DataFrame: DataFrame containing:
            - TimeStamp: Sample index based on global timestamp.
            - Amplitude: Raw signal values (int16).
            - UTCTimeStamp: Human-readable UTC timestamp.
    """
    channel_data = self.get_channel_array(channel)
    num_samples = len(channel_data)
    channel_df = pd.DataFrame(channel_data, columns=["Amplitude"])
    channel_df["TimeStamp"] = np.arange(
        self.timeStamp, self.timeStamp + num_samples
    )
    channel_df["UTCTimeStamp"] = channel_df["TimeStamp"].apply(
        lambda x: utils.ts2unix(self.timeOrigin, self.timestampResolution, x)
    )
    return channel_df[["TimeStamp", "Amplitude", "UTCTimeStamp"]]
```

Each sample in the array is aligned using:

- **`self.timeStamp`**: The timestamp of the first recorded data point.
- **`self.timeOrigin`**: The actual UTC time corresponding to timestamp 0.
- **`self.timestampResolution`**: The number of counts per second (usually 30,000).

This ensures that the amplitude at each point is properly aligned in real time, allowing precise synchronization with other data streams such as video or triggers.

## How to Decode Audio

To export microphone data from NS5 to a `.wav` file:

1. **Extract the audio channel**:
```python
df_sub = ns5.get_channel_df("RoomMic2")
audio_samples = df_sub["Amplitude"].values.astype(np.int16)
```

2. **Compute dynamic sample rate**:  
Although the NS5 file uses a nominal timestamp resolution of 30,000 Hz, the actual spacing between video frames (based on `frame_id` vs. `TimeStamp`) is not exactly 1000 ticks per frame. This small variation (e.g., 998, 1001) accumulates over time and can lead to noticeable drift. To ensure audio and video remain aligned, we compute the true sample rate dynamically:
```python
exported_video_duration_s = (max_frame - min_frame + 1) / 30  # 30 fps
fps_audio = int(len(audio_samples) / exported_video_duration_s)
```

3. **Export to WAV**:
```python
from scipy.io.wavfile import write as wav_write
wav_write(audio_wav_path, fps_audio, audio_samples)
```

This ensures the audio duration matches the actual video length, avoiding sync issues due to small timing deviations in frame acquisition.
