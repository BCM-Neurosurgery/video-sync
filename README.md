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

Choose the example closest to the intended workflow:

| Workflow | Example |
| --- | --- |
| One exact MP4 and its JSON | [`config.single-mp4.example.yaml`](config.single-mp4.example.yaml) |
| One raw NEV/NS5 pair | [`config.raw-pair.example.yaml`](config.raw-pair.example.yaml) |
| One stitched NEV/NS5 pair | [`config.stitched-pair.example.yaml`](config.stitched-pair.example.yaml) |
| Explicit mixed batch | [`config.mixed-batch.example.yaml`](config.mixed-batch.example.yaml) |
| Every raw pair in one directory | [`config.flat.example.yaml`](config.flat.example.yaml) |
| Stitched task directories | [`config.batch.example.yaml`](config.batch.example.yaml) |

New configurations should use the canonical `sessions` structure below. Shared
run options stay at the top level, `video` supplies the default camera
selection, and every session explicitly names its neural files and timestamp
anchor:

```yaml
output_dir: "/path/to/output"
channel_name: "RoomMic2"
keep_intermediates: false
video:
  kind: discover
  recording_dir: "/path/to/VIDEO"
  camera_serials: ["18486638", "23512014"]
sessions:
  - name: "raw-001"
    nev_path: "/path/to/NSP1-001.nev"
    ns5_path: "/path/to/NSP1-001.ns5"
    time_anchor:
      kind: paired_ns5
  - name: "stitched-convo"
    nev_path: "/path/to/convo-NSP-1.nev"
    ns5_path: "/path/to/convo-NSP-1.ns5"
    time_anchor:
      kind: first_raw_nev
      reference_path: "/path/to/first-raw.nev"
```

Use `paired_ns5` for raw pairs. Use `first_raw_nev` for stitched pairs and
provide the first raw NEV used by that stitched timeline. A session can override
the shared video selection. To select exact camera files, key each MP4 by its
camera serial; the JSON remains required for frame/serial metadata:

```yaml
video:
  kind: explicit
  json_path: "/path/to/YFVDatafile_20260217_091320.json"
  mp4_paths:
    "18486638": "/path/to/YFVDatafile_20260217_091320.18486638.mp4"
```

For raw directory batches, `flat_dir` is a discovery shortcut that expands into
the same session model. Each same-basename NEV/NS5 pair is anchored to its
paired NS5 automatically:

```yaml
flat_dir: "/path/to/DATA/session"
keywords: ["NSP1-"]  # optional; omit to process every paired NEV/NS5
cam_recording_dir: "/path/to/VIDEO"
output_dir: "/path/to/output"
channel_name: "RoomMic2"
cam_serial: ["18486638", "23512014"]  # optional
keep_intermediates: false
```

The camera directory is indexed once and reused across every discovered pair.
Unpaired files fail preflight. Stitched-directory `base_dir` batches remain
supported, but when `first_nev_paths` is present it must contain an anchor for
every selected task. Existing `nsp_dir`, `flat_dir`, and `base_dir` configs are
compatibility inputs; all are normalized to `RunSpec`/`SessionSpec` before any
processing starts. See `config.example.yaml`, `config.flat.example.yaml`, and
`config.batch.example.yaml`.

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
