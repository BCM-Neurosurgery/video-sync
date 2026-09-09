### **The Problem**

In some cases, JSON files within a group of camera recordings may have a slightly different timestamp than the corresponding MP4 files. In other cases, the JSON file may be missing entirely. This inconsistency can create issues when synchronizing video and metadata.

### **Examples**

#### **Example 1: JSON Timestamp Mismatch**

In this example, the JSON file has a different timestamp (163417), whereas all the MP4 files share another timestamp (163418). However, they should belong to the same recording session, as each recording spans 10 minutes.

```bash
[auto@elias video-sync]$ ls /mnt/datalake/data/emu/YFCDatafile/VIDEO/20240719/ | grep 20240719_1634
YFC_20240719_163417.json
YFC_20240719_163418.18486634.mp4
YFC_20240719_163418.18486638.mp4
YFC_20240719_163418.23512014.mp4
YFC_20240719_163418.23512906.mp4
```

In this case, the JSON file appears to have been created slightly earlier than the MP4 files, likely due to the way timestamps are assigned during recording.

#### **Example 2: Missing JSON File**

In this case, there is no JSON file for the group of MP4 files recorded at 153936.

```bash
[auto@elias video-sync]$ ls /mnt/datalake/data/emu/YFCDatafile/VIDEO/20240719/ | grep 20240726_1539
YFC_20240726_153936.18486634.mp4
YFC_20240726_153936.18486638.mp4
YFC_20240726_153936.23512014.mp4
YFC_20240726_153936.23512906.mp4
```

This suggests that the metadata file (JSON) was not generated, potentially due to an issue during recording or a forceful program exit.

### **Observations and Possible Causes**

- Program Termination: A forceful exit (e.g., process killed, unexpected shutdown) may prevent the JSON file from being written properly or fully.
    
- File Write Order: The JSON metadata file may be generated slightly before or after the video files, leading to a minor timestamp discrepancy.

### **Potential Solutions**

- Post-Processing Fix: Implement a script to detect mismatched JSON files and reassign them to the correct MP4 group based on proximity.

- Ignore if the json files are missing.
