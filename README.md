# video-sync
A Python tool to synchronize NSP data with camera recordings.

## Introduction
`video-sync` is a Python-based tool designed to synchronize Neural Signal Processing (NSP) data with camera recordings. This tool processes NEV, NS5 files, and camera JSON files, slices the video based on valid frames, and aligns audio with video.

## Prerequisites
- Python 3.9
- `conda` for environment management

## Installation

At the root directory, create and activate a conda environment, then install the necessary packages:

```sh
conda create -n videosync python=3.9
conda activate videosync
pip install -e .
pip install -r requirements.txt
```

## Configuration Template
Create a `config.yaml` file inside pyvideosync/main_configs/config.yaml with the following structure:

```
# Camera serial number
cam_serial: "23512906"

# Paths to NEV and NS5 files
nev_path: "/path/to/your/NSP1.nev"
ns5_path: "/path/to/your/NSP1.ns5"

# Path to the camera JSON file
json_path: "/path/to/your/video_sync.json"

# Path to the input video file
video_path: "/path/to/your/video.mp4"

# Paths for the output files
output_dir: "/path/to/output/dir"

# Channel name for the audio data
channel_name: "RoomMic2"

# Whether to run in debug mode
debug_mode: true
```

### Running the Tool

```
python main.py --config main_configs/config.yaml
```

## Workflow

- Verify initial file integrity
  - Minimal file paths check, save memory/time
  - Focus on NSP1 for now
  - Each NSP1 group should have exactly 1 nev/ns5/ns3
  - Each mp4/json group should have exactly 1 JSON

- If integrity check passed, prompt for input
  - Ask the user exactly which video file he/she wants to sync
  - Secondary integrity check

- Continue to sync

### TODOs

**CORE**
- [X] Log config YAML file
- [X] Save output based on input names and timestamps
- [X] main.py save log to each video section
- [X] Do not plot, instead just save plots to dir
- [X] When config path does not exist
- [X] Make it work for videos other than the 1st one
- [X] Handle multiple videos and multiple jsons
- [ ] Make a docker file
- [ ] Multiple cam serial numbers

**User-interaction**
- [X] Make a menu program
- [ ] Confirm with user if the video has already been processed

**Performance**
- [X] Remove intermediate video files after program completes
- [ ] Does not have to go through all NEV/NS5 files in NSP
- [ ] Process video once?
- [ ] NS5 do not read the entire file

**Data-integrity**
- [ ] Verify the input video frame vs. camera JSON
  - So far, all the saved videos seem to be complete - no missing frames.
  - Need more tests to see what happens if there are any missing frames.

- [ ] Investigate causes of 0s in camera json
- [ ] Populate missing values if possible

**Readability**
- [ ] Figure out a way to get rid of all hard-coded string names
