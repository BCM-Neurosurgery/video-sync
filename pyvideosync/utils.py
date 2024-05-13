from datetime import datetime, timedelta
from scipy.io.wavfile import write
import matplotlib.pyplot as plt
import cv2


def ts2unix(time_origin, resolution, ts) -> datetime:
    """
    Convert a timestamp into a Unix timestamp
    based on the origin time and resolution.

    Args:
        time_origin: e.g. datetime.datetime(2024, 4, 16, 22, 7, 32, 403000)
        resolution: e.g. 30000
        ts: e.g. 37347215

    Returns:
        e.g. 2024-04-16 22:28:17.310167
    """
    base_time = datetime(
        time_origin.year,
        time_origin.month,
        time_origin.day,
        time_origin.hour,
        time_origin.minute,
        time_origin.second,
        time_origin.microsecond,
    )
    return base_time + timedelta(microseconds=(ts * 1000000 / resolution))


def analog2audio(analog, sample_rate: int, out_path: str):
    """
    Convert analog signal to wav audio
    Args:
        analog: np.array
        sample_rate: e.g. 30000
        out_path: e.g. "output_audio.wav"
    """
    write(out_path, sample_rate, analog)


def plot_diff_histogram(df, col):
    """
    Given a df and a col, plot diff vs. col
    col is supposed to be a continuously incrementing col
    """
    df["difference"] = df[col].diff()
    plt.plot(df[col][1:], df["difference"][1:])
    plt.title(f"Difference between consecutive {col}")
    plt.xlabel(col)
    plt.ylabel("Difference")
    plt.grid(True)
    plt.show()


def plot_diff_distribution(df, col):
    """
    Plot the distribution of diff in col
    """
    df = df.copy()
    df["difference"] = df[col].diff()
    value_counts = df["difference"].value_counts().sort_index()

    # Create a bar plot
    plt.figure(figsize=(8, 4))
    ax = value_counts.plot(kind="bar", color="skyblue")
    plt.title("Frequency Distribution of Diff Column")
    plt.xlabel("Unique Values")
    plt.ylabel("Frequency")
    plt.xticks(rotation=45)  # Keeps the x labels vertical for readability
    plt.grid(axis="y", linestyle="--", alpha=0.7)

    # Add text labels above the bars
    for p in ax.patches:
        ax.annotate(
            str(p.get_height()),
            (p.get_x() + p.get_width() / 2, p.get_height()),
            ha="center",
            va="bottom",
        )  # ha is horizontal alignment

    plt.show()


def get_fps(video_path: str) -> float:
    """Get fps of a video

    Args:
        video_path (str): the path to the video

    Returns:
        float: fps
    """
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print("could not open :", video_path)
        return
    return cap.get(cv2.CAP_PROP_FPS)


def frame2min(frames: int, fps: int) -> str:
    """Convert number of frames to length in 00:00 format

    Args:
        frames (int): total number of frames
        fps (int): fps of this video

    Returns:
        str: length of video in 00:00 format
    """
    total_seconds = frames / fps
    minutes = int(total_seconds // 60)
    seconds = int(total_seconds % 60)
    return f"{minutes:02}:{seconds:02}"
