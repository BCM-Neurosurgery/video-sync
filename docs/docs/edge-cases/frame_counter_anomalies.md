# **1. Frame Counter Anomalies**

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

- [YFB_20240505_133351.json](files/YFB_20240505_133351.json)
