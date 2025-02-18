import cv2
from pyvideosync import utils
from tqdm import tqdm
import pandas as pd
import os


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

    @staticmethod
    def extract_and_combine_videos_from_df(df, output_video, fps=30):
        """
        Extracts specific frames from multiple MP4 files (provided in a DataFrame)
        and combines them into a single output video efficiently without storing frames in memory.

        Parameters:
        - df (pandas.DataFrame): A DataFrame with columns:
            - "mp4_file": Path to the MP4 file.
            - "start_frame_id": Frame to start extracting.
            - "end_frame_id": Frame to stop extracting.
        - output_video (str): Path for the output combined video file.
        - fps (int): Frames per second for the output video.

        Example:
        df = pd.DataFrame({
            "mp4_file": ["video1.mp4", "video2.mp4", "video3.mp4"],
            "start_frame_id": [16000, None, 0],
            "end_frame_id": [18000, None, 2000]
        })
        extract_and_combine_videos_from_df(df, "combined_output.mp4", fps=30)
        """

        # Initialize VideoWriter settings
        frame_size = None
        video_writer = None
        total_frames_to_extract = 0

        # First pass: Determine total frames and frame size
        for _, row in df.iterrows():
            video_path = row["mp4_file"]
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                print(f"Error: Could not open {video_path}")
                continue

            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if frame_size is None:
                frame_size = (
                    width,
                    height,
                )  # Set frame size from the first valid video

            start_frame = (
                row["start_frame_id"] if row["start_frame_id"] is not None else 0
            )
            end_frame = (
                row["end_frame_id"]
                if row["end_frame_id"] is not None
                else int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) - 1
            )
            total_frames_to_extract += max(0, end_frame - start_frame + 1)

            cap.release()

        if frame_size is None:
            print("No valid video files found. Exiting.")
            return

        # Initialize VideoWriter
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        video_writer = cv2.VideoWriter(output_video, fourcc, fps, frame_size)

        # Progress bar
        progress_bar = tqdm(
            total=total_frames_to_extract, desc="Processing Frames", unit="frame"
        )

        # Second pass: Extract and write frames directly to the video
        for _, row in df.iterrows():
            video_path = row["mp4_file"]
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                print(f"Error: Could not open {video_path}")
                continue

            start_frame = (
                row["start_frame_id"] if row["start_frame_id"] is not None else 0
            )
            end_frame = (
                row["end_frame_id"]
                if row["end_frame_id"] is not None
                else int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) - 1
            )

            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)  # Seek to the start frame

            frame_count = start_frame
            while frame_count <= end_frame:
                ret, frame = cap.read()
                if not ret:
                    print("Error reading frame")
                    break  # End of video or read error

                video_writer.write(frame)  # Write frame directly
                progress_bar.update(1)
                frame_count += 1

            cap.release()
            print(f"Processed {video_path}, frames {start_frame} to {end_frame}")

        # Cleanup
        video_writer.release()
        progress_bar.close()
        print(f"Combined video saved as {output_video}")
