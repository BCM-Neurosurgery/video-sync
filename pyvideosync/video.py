import cv2
from pyvideosync import utils
from tqdm import tqdm
import pandas as pd
import os
import numpy as np
import soundfile as sf
import subprocess
from moviepy import VideoFileClip, AudioFileClip
from moviepy.audio.AudioClip import AudioArrayClip
import scipy.io.wavfile as wav
import uuid
from scipy.io.wavfile import write as wav_write


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

    def slice_video(self, output_file: str, frames_to_keep: list, output_fps: float):
        """
        Slices the video to only keep the frames specified in frames_to_keep and saves it to output_file
        with the specified FPS.

        Parameters:
        ----------
        output_file : str
            The path to save the output video file.
        frames_to_keep : list
            A list of frame indices to keep in the output video.
        output_fps : float
            The frames per second for the output video.
        """
        # Reinitialize the capture to ensure it starts from the beginning
        self.capture = cv2.VideoCapture(self.video_path)
        if not self.capture.isOpened():
            raise ValueError(f"Error reopening video file {self.video_path}")

        # Get video properties
        frame_width = self.get_frame_width()
        frame_height = self.get_frame_height()
        total_frames = self.get_frame_count()

        # Define the codec and create VideoWriter object
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")  # or 'XVID'
        out = cv2.VideoWriter(
            output_file, fourcc, output_fps, (frame_width, frame_height)
        )

        frames_to_keep = set(frames_to_keep)  # Convert list to set for fast lookup

        # Initialize the progress bar
        pbar = tqdm(total=total_frames, desc="Processing video", unit="frame")

        current_frame_index = 0
        while True:
            ret, frame = self.capture.read()
            if not ret:
                break

            if current_frame_index in frames_to_keep:
                out.write(frame)

            current_frame_index += 1
            pbar.update(1)

        pbar.close()
        # Release everything when job is finished
        self.capture.release()
        out.release()
        cv2.destroyAllWindows()

    def extract_frames(self, frames_dir) -> list:
        """Extract frames from a video file and store them in memory.

        Args:
            video_path (str): Path to the input video file.

        Returns:
            list: A list of frames extracted from the video. Each frame is represented as a numpy array.
        """
        frame_list = []
        frame_id = 0

        total_frames = self.get_frame_count()

        with tqdm(total=total_frames, desc="Extracting frames") as pbar:
            while self.capture.isOpened():
                ret, frame = self.capture.read()
                if not ret:
                    break
                frame_path = os.path.join(frames_dir, f"frame_{frame_id}.png")
                cv2.imwrite(frame_path, frame)
                frame_list.append(frame_path)
                frame_id += 1
                pbar.update(1)
        self.capture.release()
        return frame_list

    # @staticmethod
    # def make_synced_subclip(df_sub, mp4_path, fps_video=30, fps_audio=30000):
    #     """
    #     Given a sub-DataFrame for a single mp4_file, where
    #     frame_ids_relative runs from e.g. 11797..18000,
    #     produce a MoviePy clip for exactly that frame range
    #     (subclip of the MP4) plus the corresponding audio.
    #     """
    #     # 1) Identify which frames we need
    #     min_frame = df_sub["frame_ids_relative"].min()
    #     max_frame = df_sub["frame_ids_relative"].max()

    #     # 2) Convert frames to seconds, subclip only that portion
    #     start_sec = min_frame / fps_video
    #     # +1 so we include the last frame—MoviePy’s subclip end is exclusive by default
    #     end_sec = (max_frame + 1) / fps_video

    #     video_clip = VideoFileClip(mp4_path).subclipped(start_sec, end_sec)

    #     # 4) Write amplitude array to a temporary WAV file
    #     audio_samples = df_sub["Amplitude"].values
    #     audio_name = os.path.basename(mp4_path).replace(".mp4", ".wav")
    #     audio_path = f"/home/auto/CODE/utils/video-sync/Testing/YFITesting/02242025/18486634/{audio_name}"
    #     wav.write(audio_path, fps_audio, audio_samples)

    #     # 3) Build the raw audio array for that sub-range
    #     #    (Already filtered by df_sub, so just take the amplitude column.)
    #     # audio_samples = df_sub["Amplitude"].values.astype(np.float32)
    #     # # wav.write("scipy_audio.wav", fps_audio, audio_samples)
    #     # audio_samples /= 32768.0
    #     # audio_samples = audio_samples.reshape(-1, 1)  # Make it mono shape (N, 1)
    #     # fps_audio *= 2  # Double the audio FPS since we did the reshape
    #     audio_clip = AudioFileClip(audio_path)

    #     # 4) Match audio duration to the subclip's duration, if needed
    #     subclip_duration = video_clip.duration  # (should be end_sec - start_sec)
    #     print(f"Subclip duration: {subclip_duration}")

    #     # If your audio is precisely aligned in time, you can also just let it run.
    #     # But often it's good to clamp or set explicitly:
    #     audio_clip = audio_clip.set_duration(subclip_duration)

    #     # 5) Attach the audio to the subclip
    #     final_subclip = video_clip.set_audio(audio_clip)

    #     final_subclip.write_videofile(
    #         f"/home/auto/CODE/utils/video-sync/Testing/YFITesting/02242025/18486634/{os.path.basename(mp4_path).replace('.mp4', '.mp4')}",
    #         codec="libx264",
    #         audio_codec="aac",
    #     )

    #     return final_subclip
