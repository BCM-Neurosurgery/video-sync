import cv2
from pyvideosync import utils
from tqdm import tqdm
import pandas as pd
import os
import subprocess
from fractions import Fraction
from typing import List


class Video:
    """
    A class to parse mp4 files and extract video metadata.

    Attributes:
    ----------
    video_path : str
        The path to the mp4 video file.
    capture : cv2.VideoCapture
        The OpenCV VideoCapture object for the video file.
    frame_count : int
        The total number of frames in the video.
    fps : float
        The frames per second (fps) of the video.
    length : float
        The total length of the video in seconds.
    frame_width : int
        The width of the video frames.
    frame_height : int
        The height of the video frames.
    """

    def __init__(
        self, video_path: str, abs_start_frame=None, abs_end_frame=None
    ) -> None:
        self.video_path = video_path
        self.capture = cv2.VideoCapture(video_path)

        if not self.capture.isOpened():
            raise ValueError(f"Error opening video file {video_path}")

        self.frame_count = int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = self.capture.get(cv2.CAP_PROP_FPS)
        self.length = self.frame_count / self.fps
        self.frame_width = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.frame_height = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.abs_start_frame = abs_start_frame
        self.abs_end_frame = abs_end_frame

    def get_frame_count(self) -> int:
        return self.frame_count

    def get_length(self) -> float:
        return self.length

    def get_length_readable(self) -> str:
        return utils.frame2min(self.frame_count, self.fps)

    def get_fps(self) -> float:
        return self.fps

    def get_frame_width(self) -> int:
        return self.frame_width

    def get_frame_height(self) -> int:
        return self.frame_height

    def get_video_path(self):
        return self.video_path

    def get_video_stats_df(self):
        stats = [
            {
                "video_path": self.get_video_path(),
                "saved_fps": self.get_fps(),
                "duration_readable": self.get_length_readable(),
                "frame_count": self.get_frame_count(),
                "abs_start_frame": self.abs_start_frame,
                "abs_end_frame": self.abs_end_frame,
            }
        ]
        return pd.DataFrame.from_records(stats)

    @staticmethod
    def get_video_fps(input_path: str) -> float:
        """Fetches the frame rate (FPS) of an MP4 video using ffprobe.

        Args:
            input_path (str): Path to the source MP4 file.

        Returns:
            float: The video's frames per second.

        Raises:
            subprocess.CalledProcessError: If the ffprobe command fails.
            ValueError: If the returned frame rate string cannot be parsed.
        """
        # Run ffprobe to get raw r_frame_rate (e.g. "30000/1001" or "30/1")
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=r_frame_rate",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            input_path,
        ]
        raw = subprocess.check_output(cmd, text=True).strip()
        try:
            return float(Fraction(raw))
        except Exception as e:
            raise ValueError(f"Cannot parse frame rate '{raw}'") from e

    @staticmethod
    def pad_blank_frame_end(input_path: str, output_path: str) -> None:
        """Appends a single blank (black) frame to the end of an MP4 video.

        Args:
            input_path (str): Path to the source MP4 file.
            output_path (str): Path where the padded video will be written.

        Raises:
            subprocess.CalledProcessError: If the ffmpeg command fails.
        """
        fps = Video.get_video_fps(input_path)
        frame_duration = 1.0 / fps

        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-i",
            input_path,
            "-vf",
            f"tpad=stop_mode=add:stop_duration={frame_duration}:color=black",
            "-c:v",
            "libx264",
            "-c:a",
            "copy",
            output_path,
        ]
        subprocess.run(ffmpeg_cmd, check=True)

    @staticmethod
    def get_frame_count_ffmpeg(input_path: str) -> int:
        """Counts the total number of video frames in an MP4 file using ffprobe.

        Args:
            input_path (str): Path to the source MP4 file.

        Returns:
            int: The total number of frames in the video.

        Raises:
            subprocess.CalledProcessError: If the ffprobe command fails.
            ValueError: If the frame count cannot be parsed as an integer.
        """
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-count_frames",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=nb_read_frames",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            input_path,
        ]
        raw = subprocess.check_output(cmd, text=True).strip()
        try:
            return int(raw)
        except Exception as e:
            raise ValueError(f"Cannot parse frame count '{raw}'") from e

    @staticmethod
    def extract_frames_to_video(
        mp4_path: str, exported_fps: int, frame_ids: List[int], output_path: str
    ) -> None:
        """Extracts specific frames from an MP4 and exports them as a new video.

        This uses FFmpeg's `select` filter to pick out only the frames whose frame
        numbers are in `frame_ids`, then re-encodes the result at `exported_fps`.

        Args:
            mp4_path (str): Path to the input MP4 video.
            exported_fps (int): Frame rate for the output video.
            frame_ids (List[int]): List of zero-based frame indices to extract.
            output_path (str): Path where the output MP4 will be written.

        Raises:
            subprocess.CalledProcessError: If the FFmpeg command fails.
        """
        # Build select expression: eq(n\,F1)+eq(n\,F2)+...
        select_expr = "+".join(f"eq(n\\,{fid})" for fid in frame_ids)

        vf_filter = f"select='{select_expr}',setpts=N/{exported_fps}/TB"

        ffmpeg_cmd = [
            "ffmpeg",
            "-y",  # overwrite output if exists
            "-i",
            mp4_path,
            "-vf",
            vf_filter,
            "-fps_mode",
            "cfr",  # constant frame rate
            "-r",
            str(exported_fps),  # force output FPS
            "-c:v",
            "libx264",  # encode as H.264
            output_path,
        ]

        subprocess.run(ffmpeg_cmd, check=True)

    @staticmethod
    def export_frame_as_image(
        mp4_path: str, frame_id: int, output_image_path: str
    ) -> None:
        """Exports a single frame from an MP4 video as an image file.

        This uses FFmpeg's `select` filter to grab the frame whose zero-based
        index equals `frame_id`, then writes it out as a single image.

        Args:
            mp4_path (str): Path to the source MP4 video file.
            frame_id (int): Zero-based index of the frame to extract.
            output_image_path (str): Path (including filename and extension,
                e.g. `.png` or `.jpg`) where the extracted frame will be saved.

        Raises:
            subprocess.CalledProcessError: If the FFmpeg command fails.
        """
        # Build the FFmpeg command
        ffmpeg_cmd = [
            "ffmpeg",
            "-y",  # overwrite output if it exists
            "-i",
            mp4_path,  # input file
            "-vf",
            f"select='eq(n\\,{frame_id})'",  # pick exactly that frame
            "-frames:v",
            "1",  # output exactly one frame
            "-update",
            "1",  # write a single image (no sequence)
            output_image_path,
        ]
        # Run the command
        subprocess.run(ffmpeg_cmd, check=True)
