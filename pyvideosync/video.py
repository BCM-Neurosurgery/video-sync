import cv2
from pyvideosync import utils
from tqdm import tqdm
import pandas as pd


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

    def __init__(self, video_path: str) -> None:
        self.video_path = video_path
        self.capture = cv2.VideoCapture(video_path)

        if not self.capture.isOpened():
            raise ValueError(f"Error opening video file {video_path}")

        self.frame_count = int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = self.capture.get(cv2.CAP_PROP_FPS)
        self.length = self.frame_count / self.fps
        self.frame_width = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.frame_height = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

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
