"""
Configure Paths
"""

import yaml
import os
import sys


class PathUtils:
    def __init__(self, config_path: str, timestamp) -> None:
        """Load and validate config

        Args:
            config_path (str): abs path to config.yaml
        """
        self.config_path = config_path
        self._timestamp = timestamp
        self._config = self.load_config(config_path)
        self._output_dir = self.config["output_dir"]
        self._cam_serial = self.config["cam_serial"]
        self._nsp_dir = self.config["nsp_dir"]
        self._cam_recording_dir = self.config["cam_recording_dir"]
        self._ns5_channel = self.config["channel_name"]
        self._video_to_process = None
        self._video_output_dir = None
        self._video_path = None
        self._chunk_output_dir = None
        self._frames_output_dir = None

    def load_config(self, config_path):
        """
        Load a YAML configuration file.

        Args:
            config_path (str): Path to the YAML configuration file.

        Returns:
            dict: Loaded configuration as a dictionary.
        """
        if not os.path.exists(config_path):
            print(f"Configuration file '{config_path}' does not exist.")
            sys.exit(1)

        try:
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)
            return config
        except yaml.YAMLError as e:
            print(f"Error loading configuration file '{config_path}': {e}")

    def is_config_valid(self):
        """Return True if config has all the required fields"""
        required_fields = [
            "cam_serial",
            "nsp_dir",
            "cam_recording_dir",
            "output_dir",
            "channel_name",
        ]
        missing_fields = [
            field for field in required_fields if field not in self._config
        ]
        return missing_fields == []

    @property
    def config(self):
        return self._config

    @property
    def output_dir(self):
        return self._output_dir

    @property
    def cam_serial(self):
        return self._cam_serial

    @property
    def nsp_dir(self):
        return self._nsp_dir

    @property
    def cam_recording_dir(self):
        return self._cam_recording_dir

    @property
    def ns5_channel(self):
        return self._ns5_channel

    @property
    def timestamp(self):
        if self._timestamp is None:
            raise ValueError("timestamp is not set")
        return self._timestamp

    @property
    def video_path(self):
        """Abs path to video.mp4"""
        return os.path.join(self.cam_recording_dir, self.video_to_process)

    @property
    def json_path(self) -> str:
        """Abs path to video.json"""
        mp4_basename = self.video_to_process.split(".")[0]
        return os.path.join(self.cam_recording_dir, f"{mp4_basename}.json")

    @property
    def video_output_dir(self):
        """Define the output directory for the video"""
        if self._video_output_dir is None:
            raise ValueError("video_output_dir is not set")
        return self._video_output_dir

    @video_output_dir.setter
    def video_output_dir(self, video_output_dir):
        if video_output_dir is None:
            raise ValueError("video_output_dir cannot be empty")
        self._video_output_dir = video_output_dir

    @property
    def chunk_output_dir(self):
        if self._chunk_output_dir is None:
            raise ValueError("chunk_output_dir is not set")
        return self._chunk_output_dir

    def set_chunk_output_dir(self, i):
        """Define the chunk output dir depending on ith iteration"""
        self._chunk_output_dir = os.path.join(self.video_output_dir, str(i))
        os.makedirs(self._chunk_output_dir, exist_ok=True)

    @property
    def frames_output_dir(self):
        """Directory to save the frames extracted from the video"""
        return os.path.join(self.video_output_dir, "frames")

    @property
    def video_out_path(self):
        """Abs path for output video.mp4"""
        return os.path.join(
            self.video_output_dir,
            f"video_{self.cam_serial}_sliced_{self.timestamp}.mp4",
        )

    @property
    def audio_out_path(self):
        return os.path.join(
            self.video_output_dir,
            f"audio_{self.cam_serial}_sliced_{self.timestamp}.wav",
        )

    @property
    def final_video_out_path(self):
        return os.path.join(
            self.video_output_dir,
            f"final_{self.cam_serial}_aligned_{self.timestamp}.mp4",
        )

    def make_frames_output_dir(self):
        os.makedirs(self.frames_output_dir, exist_ok=True)

    @property
    def nev_abs_path(self):
        """Return abs nev path"""
        if self._nev_abs_path is None:
            raise ValueError("nev_abs_path is not set")
        return self._nev_abs_path

    @property
    def ns5_abs_path(self):
        """Return abs ns5 path"""
        if self._ns5_abs_path is None:
            raise ValueError("ns5_abs_path is not set")
        return self._ns5_abs_path

    @property
    def cam_exposure_path(self):
        return os.path.join(self.chunk_output_dir, "cam_exposure_all.png")

    @property
    def channel_array_path(self):
        return os.path.join(self.chunk_output_dir, f"ns5_{self.ns5_channel}.png")

    @property
    def frame_list_path(self):
        """Path to save frame list txt"""
        return os.path.join(self.video_output_dir, "frame_list.txt")

    def set_nev_paths(self, nev_rel_path):
        """Set nev paths"""
        self._nev_rel_path = nev_rel_path
        self._nev_abs_path = os.path.join(self._nsp_dir, self._nev_rel_path)

    def set_ns5_paths(self, ns5_rel_path):
        """Set ns5 paths"""
        self._ns5_rel_path = ns5_rel_path
        self._ns5_abs_path = os.path.join(self._nsp_dir, self._ns5_rel_path)
