# 📥 Installation

## Prerequisites
Before installing `video-sync`, ensure you have the following dependencies:

- **Conda** (for environment management)
- **FFmpeg** (for video and audio processing)

### Installing Miniconda

Miniconda is the light-weight version of Conda, it's recommended for all OS. Visit the [official Miniconda download page](https://www.anaconda.com/docs/getting-started/miniconda/main) to download the installer for your OS.

### Installing FFmpeg
For **Ubuntu/Debian**:
```sh
sudo apt update
sudo apt install ffmpeg
```

For **RHEL (with EPEL enabled)**
```sh
sudo yum install epel-release
sudo yum install ffmpeg
```

For **MacOS**

Ensure [Homebrew](https://brew.sh/) is installed, then run:
```sh
brew install ffmpeg
```

For **Windows**

Use [Chocolatey](https://chocolatey.org/) (recommended):
```sh
choco install ffmpeg
```


## Installing video-sync

Clone the repository:

```sh
git clone git@github.com:BCM-Neurosurgery/video-sync.git
cd video-sync
```

Note: if you don't have permission, reach out to Yewen

For EMU tasks, check out branch `stitch-videos-to-neuro`
```sh
git checkout stitch-videos-to-neuro
```

For TRD tasks, checkout branch `trd`
```sh
git checkout trd
```

Create and activate the Conda environment, then install dependencies:

```sh
conda env create -f environment.yml
conda activate videosync
pip install .
```
