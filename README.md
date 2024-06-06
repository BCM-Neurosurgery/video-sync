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

# Paths for the output video and audio files
output_video_path: "/path/to/your/output/video_sliced.mp4"
audio_output_path: "/path/to/your/output/valid_audio.wav"
final_output_path: "/path/to/your/output/audio_video_aligned.mp4"

# Directory to save plots
plot_save_dir: "/path/to/your/output/plots"

# Channel name for the audio data
channel_name: "RoomMic2"

# Whether to run in debug mode
debug_mode: true

# Path to save log files
log_file_dir: "/path/to/your/output/logs"
```

### Running the Tool

```
python main.py --config main_configs/config.yaml
```
