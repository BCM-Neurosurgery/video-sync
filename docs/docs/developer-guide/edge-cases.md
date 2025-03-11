# Edge Cases & Real Examples

This section highlights real-world edge cases encountered when synchronizing video and neural data. Each example provides a problem description, a sample JSON snippet, analysis, and a possible solution.

## **1. Frame Counter Anomalies**

### **The Problem**

In some cases, the JSON metadata file may show frame counters that jump unexpectedly. However, the total frame count remains consistent across multiple verification methods, suggesting that frames are not actually lost.

### **Example JSON (Incorrect Frame Sequence)**

```json
{
  "frames": [
    [19393, 19393, 19392, 19393, 19392],
    [19400, 19400, 19399, 19400, 19399]
  ]
}
```

In this case, the frame IDs **jump from 19392 to 19399**, which may indicate a counter issue.

### **Observations**

The JSON metadata suggests that frames skip from 19392 → 19399.

However, when checking the total number of frames in the JSON:

```bash
>>> len(yfb_json["frame_id"])
18000
```

it still returns 18000 frames, meaning that the frames exist but their numbering is inconsistent.

Similarly, probing the corresponding MP4 video file also returns 18000 frames, further confirming that no frames are missing.

### **Conclusion**

This issue is not a missing frame problem, but rather a frame counter anomaly.

### **Download Reference JSON File**
You can download the example JSON file here:  

[YFB_20240505_133351.json](../examples/YFB_20240505_133351.json)

## **2. Chunk Serial Discontinuities in JSON**

### **The Problem**

When analyzing chunk serial data in the JSON files, discontinuities can occur in different forms. These discontinuities can affect downstream processing, requiring careful identification and handling. The types of discontinuities observed in the dataset are:

- Type I Discontinuity: The number drops to zero and then increases to a value greater than 1.
- Type II Discontinuity: The number resets from zero to 1.
- Type III Discontinuity: The difference between consecutive numbers is greater than 1.
- Type IV Discontinuity: The number hits -1.

These discontinuities can impact the integrity of data streams, requiring careful detection and mitigation strategies.

### **Example JSON**

Type I discontinuity

```json
[
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

Type II discontinuity

```json
[
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

### **Observation**

- Type I discontinuities dominate the dataset, with a structured gap pattern of 128 occurring repeatedly.
- Type II discontinuities are rare but show a similar gap pattern to Type I. The chunk serial usually drops to 0, and gradually increases to 127, before dropping to 0 again and resuming from where it left off as if all those data were not missing.
- Type III and Type IV discontinuities are absent, suggesting no extreme jumps or invalid serial numbers.


### **Conclusion**

The analysis highlights a strong pattern of Type I discontinuities, suggesting a structured reset mechanism rather than random errors. The gaps of 128 could indicate an intentional segmentation in the data stream, possibly due to a recording or transmission mechanism. Extra attention is required when handling chunk serial stream in JSON files.

### **Download Example Data**

[2024-07-19_09:10:54_chunk_discontinuities.json](../examples/2024-07-19_09:10:54_chunk_discontinuities.json)

[YFC_20240719_091054.json](../examples/YFC_20240719_091054.json)

[Jupyter Notebook to Reproduce Results](../examples/json_discontinuities.ipynb)
