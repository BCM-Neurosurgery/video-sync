# 🎥 **video-sync**  
*A Python tool to synchronize NSP data with camera recordings.*

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

## 🚀 Usage
Run `video-sync` with the desired configuration:

```sh
python main.py --config path/to/config.yaml
```

## 🏗️ Features

- ✔️ Synchronizes NEV and NS5 files with camera recordings
- ✔️ Slices video based on valid frames
- ✔️ Aligns audio with video for precise synchronization
- ✔️ Supports configurable processing options

## 📜 License

This project is licensed under the BSD-3-Clause License. See the LICENSE file for details.
