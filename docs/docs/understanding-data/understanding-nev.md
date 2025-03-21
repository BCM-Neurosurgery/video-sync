# Understanding NEV

This guide provides a detailed explanation of the NEV (Neural Event) file structure, focusing on decoding digital event streams (`UnparsedData`) and aligning them with external triggers such as camera recordings. It is intended for researchers and engineers using Blackrock systems in multimodal experimental setups.

## NEV File Structure

NEV files store timestamped events including neural spikes and digital signals. For synchronization purposes, we are primarily concerned with the digital events, which include the following fields:

- **TimeStamps**: High-resolution timestamps (typically 30,000 Hz resolution).
- **InsertionReason**: An 8-bit flag describing why the digital event was logged.
- **UnparsedData**: The raw binary data, either as 16-bit digital states or encoded serial messages.

To read the digital events as a dataframe from a `.nev` file, we can use the `Nev` class in the package. 

```python
nev = Nev(nev_path)
nev_digital_events_df = nev.get_digital_events_df()
```

The digital events dataframe looks like

{{ read_csv('understanding-nev/digital_events_df_first_20_rows.csv') }}


## Understanding `InsertionReason`

The `InsertionReason` field is a bitwise flag. Relevant values include:

| Value | Meaning |
|-------|---------|
| `1`   | A digital channel (e.g., camera trigger) changed |
| `129` | A serial message was received (bit 7 and bit 0 set) |

## Interpreting `UnparsedData`

### Digital Channel Triggers

For `InsertionReason == 1`, `UnparsedData` is a 16-bit integer representing the state of all 16 digital channels. Each bit corresponds to a specific input channel (e.g., camera exposure line). These values are typically used to reconstruct square wave triggers.

### Serial Data

For `InsertionReason == 129`, `UnparsedData` represents 1 byte (7 bits of actual data). The Arduino sends serial data by splitting a 32-bit integer into five 7-bit chunks. Each group of 5 rows with `InsertionReason == 129` corresponds to a full serial message.

### How Trigger and Serial are sent from Arduino

The Arduino transmits both a trigger pulse and a serial-encoded counter value every frame:

The trigger pulse is sent via a digital output pin (e.g., pin 13) to the camera to initiate image capture.
Simultaneously, the counter value is incremented and transmitted over three serial ports — in the current setup, two going to the PCBs (used by the cameras) and one to the audio interface.

To ensure compatibility with the camera's serial input requirements, the counter value (a 32-bit unsigned integer) is split into 5 separate bytes, with each byte containing 7 bits of actual data. This is done because:

- The camera expects each byte to begin with a start bit
- It can only receive one byte at a time, and only uses the lower 7 bits of each byte for data.
- Therefore, transmitting the full 32-bit value requires 5 bytes (since 5 × 7 = 35 bits), with the upper 3 bits simply unused if not needed.

The splitting and transmission are handled by this Arduino function:

```c++
bool send_trigger_sync_to_pcb(void *) {
  digitalWrite(trigger_pin, HIGH);

  byte bytesToSend[5]; // Create an array to store the 5 bytes
  // Split the 32-bit integer into 5 bytes, each carrying 7 bits
  for (int i = 0; i < 5; i++) {
    // Shift right by 7 bits times the index and mask out the lower 7 bits
    bytesToSend[i] = (count >> (7 * i)) & 0x7F;
  }
  //Send each byte over serial
  for (int i = 0; i < 5; i++) {
    Serial1.write(bytesToSend[i]);
    Serial2.write(bytesToSend[i]);
    Serial3.write(bytesToSend[i]);
    Serial1.flush();
    Serial2.flush();
    Serial3.flush();
  }
  digitalWrite(trigger_pin, LOW);
  count = count + 1;
  return true;
}
```

### How Serial Number is reconstructed from 5 Bytes

In this system, a 32-bit integer counter is transmitted from the Arduino in the form of 5 bytes, where each byte encodes 7 bits of actual data. Both the camera system and the BlackRock recording system receive this data and must reconstruct the original 32-bit counter value.

#### From the Camera Side

In the [camera recording software](https://github.com/BCM-Neurosurgery/MultiCameraTracking/blob/main/multi_camera/acquisition/flir_recording_api.py), each byte is masked with 0x7F to retain only the lower 7 bits. The bytes are then shifted and combined to reconstruct the full 32-bit counter value.

```python
def process_serial_data(self, c):
    serial_msg = []
    frame_count = -1
    if self.gpio_settings['line3'] == 'SerialOn':
        # We expect only 5 bytes to be sent
        if c.ChunkSerialDataLength == 5:
            chunk_serial_data = c.ChunkSerialData
            serial_msg = chunk_serial_data
            split_chunk = [ord(c) for c in chunk_serial_data]

            frame_count = 0
            for i, b in enumerate(split_chunk):
                frame_count |= (b & 0x7F) << (7 * i)
```

#### From the NEV (BlackRock) Side

On the BlackRock system, serial data is captured within the `.nev` file and appears in rows where `InsertionReason == 129`. Each complete serial transmission occupies 5 consecutive rows in the event stream.

The NEV processing workflow involves:

- Filtering valid groups of 5 rows.
- Extracting the UnparsedData field from each row.
- Converting the 5 × 7-bit chunks back into a single integer.
- Apply fix-anomaly scripts to fill in the gaps of the serial stream (Refer to edge cases documentation).

```python
def get_cleaned_digital_events_df(self):
    """
    only keep the rows which satisfy
    1. InsertionReason == 129
    2. the length of such group is 5
    3. 0 <= UnparsedData <= 127 (should be true enforced by hardware)

    Returns
        InsertionReason 	TimeStamps 	UnparsedData
    2 	129 	            1345819 	40
    3 	129 	            1345822 	76
    4 	129 	            1345825 	35
    5 	129 	            1345828 	0
    6 	129 	            1345831 	0
    """
    digital_events_df = self.get_digital_events_df()
    # True indicates a change from 1 -> 129 or 129 -> 1
    digital_events_df["group"] = (
        digital_events_df["InsertionReason"]
        != digital_events_df["InsertionReason"].shift(1)
    ).cumsum()
    # Count the size of each group and assign True where the group size
    # is 5 and the reason is 129
    digital_events_df["keeprows"] = digital_events_df.groupby("group")[
        "InsertionReason"
    ].transform(lambda x: (x == 129) & (x.size == 5))
    digital_events_df = digital_events_df[digital_events_df["keeprows"] == True]
    digital_events_df = digital_events_df.drop(["group", "keeprows"], axis=1)
    return digital_events_df

def bits_to_decimal(self, nums: list) -> int:
    """
    nums: [19, 101, 37, 0, 0]

    Returns:
    619155
    """
    # Convert each number to a 7-bit binary string with leading zeros
    binary_strings = [format(num, "07b") for num in nums][::-1]
    # Concatenate all binary strings into one long binary string
    full_binary_string = "".join(binary_strings)
    # Convert the concatenated binary string to a decimal number
    return int(full_binary_string, 2)

def get_chunk_serial_df(self, timestamp_byte: str = "first"):
    """Reconstruct chunk serial numbers from grouped digital events.

    Processes the cleaned digital events DataFrame by grouping every five consecutive rows,
    reconstructing each chunk serial number from the grouped 7-bit encoded values, and
    associating it with a corresponding timestamp. The timestamp used for each group
    can be explicitly selected as either the first or last byte in the group.

    Args:
        timestamp_byte (str, optional): Which byte's timestamp to use ('first' or 'last').
            Defaults to 'first'. Use 'last' if you want the timestamp representing
            the full completion of the serial transmission (recommended for accurate synchronization).

    Returns:
        pd.DataFrame: A DataFrame containing:
            - `TimeStamps`: Timestamp from the NEV data (based on selected byte).
            - `chunk_serial`: Reconstructed chunk serial number.
            - `UTCTimeStamp`: Human-readable UTC timestamp.

    Raises:
        AssertionError: If unparsed data is unavailable or timestamp_byte parameter is invalid.

    Example:
        >>> nev.get_chunk_serial_df(timestamp_byte='last')
                TimeStamps  chunk_serial              UTCTimeStamp
        0         1345819       583208  2024-04-16 21:48:17.195433
        1         1346821       583209  2024-04-16 21:48:17.228833
    """
    assert self.has_unparsed_data(), "No unparsed data available."
    assert timestamp_byte in [
        "first",
        "last",
    ], "timestamp_byte must be either 'first' or 'last'"

    df = self.get_cleaned_digital_events_df()
    results = []

    for i in range(0, len(df), 5):
        group = df.iloc[i : i + 5]
        if len(group) == 5:
            nums = group["UnparsedData"].tolist()
            decimal_number = self.bits_to_decimal(nums)

            # explicitly choose which byte's timestamp to use
            if timestamp_byte == "first":
                timestamp = group["TimeStamps"].iloc[0]
            else:  # timestamp_byte == 'last'
                timestamp = group["TimeStamps"].iloc[-1]

            unix_time = ts2unix(
                self.timeOrigin, self.timestampResolution, timestamp
            )
            results.append((timestamp, decimal_number, unix_time))

    # Explicitly fill missing serials if necessary
    results = fill_missing_serials_with_gap(results)

    return pd.DataFrame.from_records(
        results, columns=["TimeStamps", "chunk_serial", "UTCTimeStamp"]
    )
```

### Timing Between Trigger and Serial

According to the Arduino code, the trigger pulse is initiated immediately before the serial data transmission begins:

```c++
bool send_trigger_sync_to_pcb(void *) {
  digitalWrite(trigger_pin, HIGH);

  // code to sent serial...

  digitalWrite(trigger_pin, LOW);
  count = count + 1;
  return true;
}
```

When observing the NEV recording, we find that the trigger pulse is captured exactly one timestamp before the first byte of the 5-byte serial transmission. This confirms the ordering and tight timing between the two signals. This relationship is visualized in the following figure:

![Timing Between Trigger and Serial](understanding-nev/cam_expo2.png)

This precise sequencing is essential for synchronizing camera frames with neural recordings. The reliable 1-timestamp offset can be leveraged during analysis to align data streams accurately.
