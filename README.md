# 🎥 **video-sync**  
*A Python tool to synchronize NSP data with camera recordings.*

## 📖 Documentation

For detailed documentation, please go to https://bcm-neurosurgery.github.io/video-sync/

## 📌 Introduction  
`video-sync` is a Python-based tool designed to synchronize **Neural Signal Processing (NSP) data** with camera recordings. It processes **NEV, NS5 files, and camera JSON files**, slices videos based on valid frames, and aligns audio with video. This ensures precise synchronization of neural and video data for analysis.

## 🛠️ Prerequisites  
Ensure you have the following installed before proceeding:  

- **Conda** (for environment management)  
- **FFmpeg** (for video and audio processing)

### Installing FFmpeg on Linux  

For **Ubuntu/Debian**:  
```sh
sudo apt update
sudo apt install ffmpeg
```

For **RHEL (with EPEL enabled)**:
```sh
sudo yum install epel-release
sudo yum install ffmpeg
```

## 📥 Installation
Clone the repository and set up the environment:
```sh
git clone git@github.com:BCM-Neurosurgery/video-sync.git
cd video-sync
```

Create and activate the Conda environment, then install dependencies:
```sh
conda env create -f environment.yml
conda activate videosync
pip install .
```

## ⚙️ Configuration
Before running the tool, configure it properly using a YAML configuration file.

A sample configuration is provided:
```sh
cp config.example.yaml config.yaml
```

For flat raw-data sessions, each NEV is automatically anchored to the matching
NS5 header time and first packet timestamp. For stitched NSP sessions whose
output begins inside the first raw chunk, set `first_nev_path` to that raw NSP1
NEV instead. The calibrated UTC selects the camera files; chunk serials provide
the exact frame-level alignment.

To process a directory of raw NSP files, use one configuration for the whole
directory:

```yaml
flat_dir: "/path/to/DATA/session"
cam_recording_dir: "/path/to/VIDEO"
output_dir: "/path/to/output"
channel_name: "RoomMic2"
keywords: ["NSP1-"]  # optional; omit to process every paired NEV/NS5
cam_serial: ["18486638", "23512014"]  # optional; omit to auto-detect
keep_intermediates: false
```

One invocation discovers and processes every same-basename NEV/NS5 pair:

```sh
stitch-videos --config path/to/config.yaml
```

The camera directory is indexed once and reused across all pairs. Outputs are
written directly under `<output_dir>/<NSP basename>/`; no per-pair configs or
post-processing moves are needed. The batch continues past individual failures
but exits nonzero after the summary if any requested pair did not complete.
Unpaired NEV or NS5 basenames fail preflight before processing starts.

For exact inputs or mixed raw/stitched runs, use `sessions:`. Every entry names
one NEV/NS5 pair, its time-anchor strategy, and optionally its own video
selection. Shared video discovery can remain at the top level:

```yaml
output_dir: "/path/to/output"
channel_name: "RoomMic2"
video:
  kind: discover
  recording_dir: "/path/to/VIDEO"
  camera_serials: ["18486638", "23512014"]
sessions:
  - name: "raw-001"
    nev_path: "/path/to/NSP1-001.nev"
    ns5_path: "/path/to/NSP1-001.ns5"
    time_anchor: "paired_ns5"
  - name: "stitched-convo"
    nev_path: "/path/to/convo-NSP-1.nev"
    ns5_path: "/path/to/convo-NSP-1.ns5"
    time_anchor:
      kind: "first_raw_nev"
      reference_path: "/path/to/first-raw.nev"
```

Use `video.kind: explicit` with `json_path` and `mp4_paths` to restrict a
session to exact camera files. See `config.sessions.example.yaml` for all three
forms. Existing `nsp_dir`, `flat_dir`, and `base_dir` configs remain supported;
they are normalized to the same session model before processing.

## 🚀 Usage
Activate conda environment and run `stitch-videos` with the path to configuration in terminal:

```sh
conda activate videosync
stitch-videos --config path/to/config.yaml
```

## 📷 EMU Camera Serials

- 18486634 F1
- 23512908 F2
- 18486644 F3
- 18486638 B1
- 23512014 B2
- 23512906 R1
- 23512012 R2
- 23505577 R3

## 🏗️ Features

- ✔️ Synchronizes NEV and NS5 files with camera recordings
- ✔️ Slices video based on valid frames
- ✔️ Aligns audio with video for precise synchronization
- ✔️ Writes one task-level CSV mapping every camera's synced frames to source
  frames, Arduino chunk serials, NEV timestamps, and source NS5 sample indices
- ✔️ Supports configurable processing options

Each task's final outputs are flat and camera-explicit:

```text
<output_dir>/<task>/
├── <task>_<camera_serial>.mp4
└── <task>_frame_mapping.csv
```

Use `(camera_serial, synced_frame_idx)` to identify one row in the combined CSV.

## 📜 License

This project is licensed under the BSD-3-Clause License. See the LICENSE file for details.
