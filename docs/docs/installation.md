# 📥 Installation

## Prerequisites
Before installing `video-sync`, ensure you have the following dependencies:

- **Conda** (for environment management)
- **FFmpeg** (for video and audio processing)

### Installing FFmpeg on Linux
For **Ubuntu/Debian**:
```sh
sudo apt update
sudo apt install ffmpeg
```

For **RHEL(with EPEL enabled)**
```sh
sudo yum install epel-release
sudo yum install ffmpeg
``` 

### Installing video-sync

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
