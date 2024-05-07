from datetime import datetime, timedelta
from scipy.io.wavfile import write
import numpy as np
import matplotlib.pyplot as plt


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


def jsonts2datetime(ts: int) -> str:
    """
    Convert a json ts to a human-readable datetime
    ts: e.g. 19510020193080
    """
    full_bits = bin(ts)[2:]  # Get the binary without '0b' prefix
    seconds_bits = full_bits[:-32]  # Assuming the last 32 bits are nanoseconds
    nanoseconds_bits = full_bits[-32:]

    # Convert these bits to integers
    seconds = int(seconds_bits, 2)
    nanoseconds = int(nanoseconds_bits, 2)

    # Construct datetime
    dt = datetime.fromtimestamp(seconds + nanoseconds / 1e9)

    # Print the formatted datetime
    print(dt.strftime("%Y-%m-%d %H:%M:%S.%f"))


def analog2audio(analog, sample_rate: int, out_path: str):
    """
    Convert analog signal to wav audio
    Args:
        analog: np.array
        sample_rate: e.g. 30000
        out_path: e.g. "output_audio.wav"
    """
    write(out_path, sample_rate, analog)


def find_subarray_starting_with_sequence(arr, sequence):
    # Convert the sequence to a numpy array for efficient comparison
    sequence = np.array(sequence)
    sequence_length = len(sequence)

    # Iterate through the array to find the sequence
    for i in range(len(arr) - sequence_length + 1):  # +1 to include end point
        # Check if the subarray starting at index i matches the sequence
        if np.array_equal(arr[i : i + sequence_length], sequence):
            # Return the subarray starting from this index
            return arr[i:]

    # Return None if no matching subarray is found
    return None


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
