# **2. Chunk Serial Discontinuities in JSON**

### **The Problem**

When analyzing chunk serial data in the JSON files, discontinuities can occur in different forms. These discontinuities can affect downstream processing, requiring careful identification and handling. The types of discontinuities observed in the dataset are:

- Type I Discontinuity: The number drops to zero and then increases to a value greater than 1.
- Type II Discontinuity: The number resets from zero to 1.
- Type III Discontinuity: The difference between consecutive numbers is greater than 1.
- Type IV Discontinuity: The number hits -1.

These discontinuities can impact the integrity of data streams, requiring careful detection and mitigation strategies.

### **Examples**

Type I discontinuity ([YFC_20240719_091054.json](files/YFC_20240719_091054.json))

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

Type II discontinuity ([YFC_20240719_091054.json](files/YFC_20240719_091054.json))

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

Type III discontinuities ([YFB_20240504_052717.json](files/YFB_20240504_052717.json))

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


Type IV discontinuities ([YFC_20240719_091054.json](files/YFC_20240719_091054.json))

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

### **Observation**

Running the [script](notebooks/json_discontinuities.ipynb) to detect discontinuities on [YFC_20240719_091054.json](files/YFC_20240719_091054.json), we get [2024-07-19_09:10:54_chunk_discontinuities.json](files/2024-07-19_09:10:54_chunk_discontinuities.json)

By observation along with other json files:

- Type I discontinuities occur the most frequent with almost all JSON, with a structured gap pattern of 128 occurring repeatedly.
- Type II discontinuities occur usually once in each JSON. The chunk serial usually drops to 0, and gradually increases to 127, before dropping to 0 again and resuming from where it left off as if all those data were not missing.
- Type III discontinuities are rare but they do occur
- Type IV discontinuities often appear in the very beginning of file, suggesting its relation with booting up.


### **Conclusion**

The analysis highlights a strong pattern of Type I discontinuities, suggesting a structured reset mechanism rather than random errors. The gaps of 128 could indicate an intentional segmentation in the data stream, possibly due to a recording or transmission mechanism. Extra attention is required when handling chunk serial stream in JSON files.

### **Download Example Data**

- [2024-07-19_09:10:54_chunk_discontinuities.json](files/2024-07-19_09:10:54_chunk_discontinuities.json)
- [YFC_20240719_091054.json](files/YFC_20240719_091054.json)
- [Jupyter Notebook to Reproduce Results](notebooks/json_discontinuities.ipynb)
