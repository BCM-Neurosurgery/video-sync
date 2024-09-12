from datetime import datetime, timedelta
from scipy.io.wavfile import write
import matplotlib.pyplot as plt
import os
import json
import pandas as pd
import numpy as np


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
    # division first prevents overflow
    microseconds = ts / resolution * 1000000
    return base_time + timedelta(microseconds=microseconds)


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


def ts2min(ts: float, resolution: int) -> str:
    """Convert number of timestamps to 00:00 format

    Args:
        ts (int): timestamp
        resolution (int): e.g. 30000

    Returns:
        str: length of timestamps in 00:00 format
    """
    total_seconds = ts / resolution
    minutes = int(total_seconds // 60)
    seconds = int(total_seconds % 60)
    return f"{minutes:02}:{seconds:02}"


def to_16bit_binary(number: int) -> str:
    """convert number to 16-bit binary

    Args:
        number (int): e.g. 65535

    Returns:
        str: 1111111111111111
    """
    return format(number, "016b")


def make_bit_column(nev_digital_events_df, bit_number: int):
    """
    Make another column called "Bit{bit_number}"

    Args:
        nev_digital_events_df:
        InsertionReason 	TimeStamps 	UnparsedData 	UnparsedDataBin
    0 	1 	                149848003 	65535 	        1111111111111111
    1 	129 	            149848077 	45 	            0000000000101101
    2 	129 	            149848080 	39 	            0000000000100111
    3 	129 	            149848083 	33 	            0000000000100001

    Returns:
        df
        InsertionReason 	TimeStamps 	UnparsedData 	UnparsedDataBin    Bit{bit_number}
    0 	1 	                149848003 	65535 	        1111111111111111   1
    1 	129 	            149848077 	45 	            0000000000101101   0
    """
    df = nev_digital_events_df.copy()
    df[f"Bit{bit_number}"] = df["UnparsedDataBin"].apply(lambda x: int(x[bit_number]))
    return df


def plot_bit_distribution(df, bit_column: str, save_dir=None):
    """
    Plot the distribution of a specified bit from 'UnparsedDataBin' against timestamps and save the plot if a directory is specified.

    Args:
        df (DataFrame):

        InsertionReason 	TimeStamps 	UnparsedData 	UnparsedDataBin    Bit{bit_number}
    0 	1 	                149848003 	65535 	        1111111111111111   1
    1 	129 	            149848077 	45 	            0000000000101101   0

        bit_column (str): e.g. "Bit0"
        save_dir (str): Directory to save the plot. If None, the plot is not saved.
    """
    # Plotting
    plt.figure(figsize=(15, 8))  # Larger figure size for better visibility
    plt.plot(df["TimeStamps"], df[bit_column], alpha=0.5)
    plt.title(f"Distribution of {bit_column} Over Time")
    plt.xlabel("Timestamp")
    plt.ylabel(f"{bit_column} Value")
    plt.grid(True)

    # Save the plot if a save directory is specified
    if save_dir:
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        file_path = os.path.join(save_dir, f"{bit_column}_distribution.png")
        plt.savefig(file_path)
        plt.close()
        print(f"Plot saved to {file_path}")
    else:
        plt.show()


def plot_all_bits(df):
    """
    Plot all 16 bits against timestamps in the same plot, stacked upon each other.

    Args:
        df (DataFrame): The DataFrame with bit columns.
        df (DataFrame):

        InsertionReason 	TimeStamps 	UnparsedData 	UnparsedDataBin
    0 	1 	                149848003 	65535 	        1111111111111111
    1 	129 	            149848077 	45 	            0000000000101101

        time_column (str): The column name for the timestamps.
    """
    plt.figure(figsize=(15, 10))  # Larger figure size for better visibility

    for i in range(16):
        df_copy = df.copy()
        df_copy = make_bit_column(df_copy, i)
        plt.plot(
            df_copy["TimeStamps"], df_copy[f"Bit{i}"] + i, label=f"Bit{i}"
        )  # Offset each bit for stacking

    plt.title("All 16 Bits Distribution Over Time")
    plt.xlabel("Timestamp")
    plt.ylabel("Bit Value")
    plt.yticks(range(16), [f"Bit{i}" for i in range(16)])
    plt.grid(True)
    plt.legend(loc="upper right")
    plt.show()


def analyze_bit_distribution(df, bit_column: str, save_dir=None):
    """
    Analyze the distribution of bit values in the DataFrame and save the summary as a JSON file if specified.

    Args:

        InsertionReason 	TimeStamps 	UnparsedData 	UnparsedDataBin    Bit{bit_number}
    0 	1 	                149848003 	65535 	        1111111111111111   1
    1 	129 	            149848077 	45 	            0000000000101101   0

        bit_column (str): e.g. "Bit0"
        save_dir (str): The path to save the JSON file. If None, the file is not saved.

    Returns:
        summary (dict): A dictionary containing the analysis summary.
    """
    timestamps = df["TimeStamps"].values
    bits = df[bit_column].values

    one_durations = []
    zero_durations = []
    gaps_between_ones = []
    delays_after_one = []
    delays_after_zero = []
    first_ones_durations = []
    first_zeros_durations = []

    current_bit = bits[0]
    start_time = timestamps[0]
    last_one_end_time = None
    last_zero_end_time = None
    last_one_start_time = None
    last_zero_start_time = None

    for i in range(1, len(bits)):
        if bits[i] != current_bit:
            end_time = timestamps[i - 1]
            duration = int(end_time - start_time)

            if current_bit == 1:
                # End of a chunk of 1s
                one_durations.append(duration)
                if last_one_end_time is not None:
                    # Calculate the gap between the end of the last 1s chunk and the start of the current 1s chunk
                    gaps_between_ones.append(int(start_time - last_one_end_time))
                if last_one_start_time is not None:
                    # Calculate the duration between the first 1s in consecutive 1s groups
                    first_ones_durations.append(int(start_time - last_one_start_time))
                last_one_end_time = end_time
                last_one_start_time = start_time
                # Delay until the next 0 occurs after 1s end
                if i < len(bits) and bits[i] == 0:
                    delays_after_one.append(int(timestamps[i] - end_time))
            else:
                # End of a chunk of 0s
                zero_durations.append(duration)
                if last_zero_start_time is not None:
                    # Calculate the duration between the first 0s in consecutive 0s groups
                    first_zeros_durations.append(int(start_time - last_zero_start_time))
                last_zero_start_time = start_time
                # Delay until the next 1 occurs after 0s end
                if i < len(bits) and bits[i] == 1:
                    delays_after_zero.append(int(timestamps[i] - end_time))

            # Update for the next segment
            current_bit = bits[i]
            start_time = timestamps[i]

    # Handle the last segment if it ends at the last index
    end_time = timestamps[-1]
    duration = int(end_time - start_time)
    if current_bit == 1:
        one_durations.append(duration)
        if last_one_end_time is not None:
            gaps_between_ones.append(int(start_time - last_one_end_time))
        if last_one_start_time is not None:
            first_ones_durations.append(int(start_time - last_one_start_time))
    else:
        zero_durations.append(duration)
        if last_zero_start_time is not None:
            first_zeros_durations.append(int(start_time - last_zero_start_time))

    summary = {
        "one_durations": one_durations,
        "zero_durations": zero_durations,
        "gaps_between_ones": gaps_between_ones,
        "delays_after_one": delays_after_one,
        "delays_after_zero": delays_after_zero,
        "first_ones_durations": first_ones_durations,
        "first_zeros_durations": first_zeros_durations,
    }

    # Save the summary as a JSON file if a save path is specified
    if save_dir:
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        output_json = os.path.join(save_dir, f"{bit_column}_summary.json")
        with open(output_json, "w") as json_file:
            json.dump(summary, json_file, indent=4)
        print(f"Summary saved to {output_json}")

    return summary


def fill_missing_data(nev_digital_events_df, bit_number: int):
    """
    Fill in the missing data points for UnparsedDataBin values so that every timestamp within the range is accounted for.

    Args:
        nev_digital_events_df (DataFrame): The DataFrame containing the data.
        bit_number (int): The nth bit starting from the left.

    Returns:
        filled_df (DataFrame): The DataFrame with missing data points filled.
    """
    # Create a new DataFrame with continuous timestamps
    df = make_bit_column(nev_digital_events_df, bit_number)
    df["TimeStamps"] = df["TimeStamps"].astype(int)
    min_timestamp = df["TimeStamps"].min()
    max_timestamp = df["TimeStamps"].max()
    all_timestamps = pd.DataFrame(
        {"TimeStamps": range(min_timestamp, max_timestamp + 1)}
    )

    # Merge the original DataFrame with the continuous timestamps DataFrame
    filled_df = all_timestamps.merge(df, on="TimeStamps", how="left")

    # Forward fill the missing values in the bit column
    filled_df[f"Bit{bit_number}"] = filled_df[f"Bit{bit_number}"].ffill().bfill()
    filled_df[f"Bit{bit_number}"] = filled_df[f"Bit{bit_number}"].astype(int)

    return filled_df


def split2sections(nums: np.array) -> list:
    """
    Returns a 2-D list with start and end of each consecutive
    secton

    nums: e.g. np.array([2, ...NaN..., 3, ...NaN..., 5...NaN...6...Nan...7])

    Returns:
        [[2, 3], [5, 6, 7]]
    """
    # remove NaN
    nums = nums[~np.isnan(nums)]
    # convert to Int
    nums = nums.astype(int)
    chunks = []
    current_chunk = []
    # Iterate over the array
    for i in range(len(nums)):
        if i == 0:
            current_chunk.append(nums[i])
        else:
            if nums[i] == nums[i - 1] + 1:
                current_chunk.append(nums[i])
            else:
                chunks.append(current_chunk)
                current_chunk = [nums[i]]

    # Add the last chunk if not empty
    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def findMinMax(sections: list):
    """
    sections:
        [[1, 2, 3], [5, 6, 7]]
    Returns:
        [[1,3],[5,7]]
    """
    res = []
    for section in sections:
        res.append([min(section), max(section)])
    return res


# only keep the rows where frame id is consecutive
def keep_valid_audio(df) -> list:
    """
    Only keep the rows of df with valid audio. Keep the rows where the frame_ids are consecutive.
    Discard the rows where the frame id jumps.

    Returns:
        valid audio as 1D np.array
    Algo:
    - this dataframe will start with a int frame id and end with a int frame id
    - get the frame id array, remove NaN, convert to int
    - from that array, return the start and end frame id for each section
    -
    """
    # reset index
    df = df.reset_index(drop=True)
    # get frame id array
    frame_id = df["frame_ids_reconstructed"].to_numpy()
    # split it into consecutive chunks
    frame_id_sections = split2sections(frame_id)
    # get the start and end frame id of each section
    frame_id_start_end = findMinMax(frame_id_sections)
    # since each frame id is unique
    # and the index of all_merged is all incrementing by 1
    indices_to_keep = []
    for s, e in frame_id_start_end:
        chunk_start_index = df[df["frame_ids_reconstructed"] == s].index[0]
        chunk_end_index = df[df["frame_ids_reconstructed"] == e].index[0]
        indices_to_keep.extend(range(chunk_start_index, chunk_end_index + 1))
    return df.iloc[indices_to_keep]["Amplitude"].to_numpy()


def count_discontinuities(df, column_name):
    """
    Count the number of discontinuities in a column of integers with potential missing values.

    A discontinuity is defined as a jump where the difference between consecutive numbers
    is greater than 1, ignoring any NaN values in the column.

    Parameters:
    df (pandas.DataFrame): The input dataframe containing the column to be analyzed.
    column_name (str): The name of the column to be analyzed for discontinuities.

    Returns:
    int: The number of discontinuities in the column.

    Example:
    >>> data = {'numbers': [1, np.nan, np.nan, np.nan, 2, np.nan, np.nan, np.nan, 3, np.nan, np.nan, np.nan, 5, np.nan, np.nan, 8, np.nan, np.nan]}
    >>> df = pd.DataFrame(data)
    >>> count_discontinuities(df, 'numbers')
    2
    """
    non_nan_values = df[column_name].dropna().reset_index(drop=True)
    differences = non_nan_values.diff().fillna(1)
    discontinuities = (differences > 1).sum()
    return discontinuities


def count_unique_values(df, column_name):
    """
    Count the number of unique values in a specified column of a DataFrame.

    Parameters:
    df (pandas.DataFrame): The input dataframe containing the column to be analyzed.
    column_name (str): The name of the column to count unique values in.

    Returns:
    int: The number of unique values in the column.

    Example:
    >>> data = {'numbers': [1, 2, 2, 3, 4, 4, 4, 5]}
    >>> df = pd.DataFrame(data)
    >>> count_unique_values(df, 'numbers')
    5
    """
    unique_values_count = df[column_name].nunique()
    return unique_values_count


def extract_basename(input_path: str) -> str:
    """Extract name from input path

    Args:
        input_path (str): e.g. "/video/video_sync_test_0530_20240530_115639.23512906.mp4"

    Returns:
        str: e.g. video_sync_test_0530_20240530_115639_23512906
    """
    basename = os.path.basename(input_path)
    splitted = os.path.splitext(basename)[0]
    return splitted.replace(".", "_")


def replace_zeros(df, column_name):
    """
    Replaces 0s in the specified column with the correct missing integer value
    if the following conditions are met:

    1. The previous number in the column is exactly 1 less than the expected number.
    2. The next number in the column is exactly 1 greater than the expected number.

    The function assumes that the column contains a series of continuously
    increasing integers, with some missing values represented as 0.

    Parameters:
    -----------
    df : pandas.DataFrame
        The DataFrame containing the column to be processed.

    column_name : str
        The name of the column in the DataFrame that contains the series of integers
        with possible missing values as 0.

    Returns:
    --------
    pandas.DataFrame
        The DataFrame with the specified column updated, where 0s have been replaced
        with the correct missing integer values if they meet the specified conditions.

    Example:
    --------
    >>> data = {'numbers': [1, 2, 3, 0, 5, 6, 7, 10, 11, 0, 13, 14]}
    >>> df = pd.DataFrame(data)
    >>> df = replace_zeros(df, 'numbers')
    >>> print(df)
       numbers
    0        1
    1        2
    2        3
    3        4
    4        5
    5        6
    6        7
    7       10
    8       11
    9       12
    10      13
    11      14
    """
    col = df[column_name].copy()
    for i in range(1, len(col) - 1):
        if col[i] == 0:
            if col[i - 1] + 1 == col[i + 1] - 1:
                col[i] = col[i - 1] + 1
    df[column_name] = col
    return df


def fill_missing_serials_with_gap(data):
    """
    Fills in missing chunk serial numbers where the gap is greater than 1.
    The missing chunks are added with interpolated timestamps between the two existing ones.

    Parameters:
    -----------
    data : list of tuples
        Each tuple contains (timestamp, chunk_serial, UTCTimeStamp).

    Returns:
    --------
    list of tuples
        The list with the missing chunk serials filled in where appropriate.

    Example:
    --------
    >>> data = [(5412181557, 21428921, datetime(2024, 7, 26, 20, 30, 25, 509900)),
                (5412182558, 21428922, datetime(2024, 7, 26, 20, 30, 25, 543267)),
                (5412184559, 21428925, datetime(2024, 7, 26, 20, 30, 25, 609967))]
    >>> result = fill_missing_serials_with_gap(data)
    >>> for row in result:
    >>>     print(row)
    (5412181557, 21428921, datetime.datetime(2024, 7, 26, 20, 30, 25, 509900))
    (5412182558, 21428922, datetime.datetime(2024, 7, 26, 20, 30, 25, 543267))
    (5412183225, 21428923, datetime.datetime(2024, 7, 26, 20, 30, 25, 565500))
    (5412183891, 21428924, datetime.datetime(2024, 7, 26, 20, 30, 25, 587733))
    (5412184559, 21428925, datetime.datetime(2024, 7, 26, 20, 30, 25, 609967))
    """
    filled_data = []

    for i in range(len(data) - 1):
        # Append the current tuple to the result list
        filled_data.append(data[i])

        # Calculate the gap between consecutive chunk serial numbers
        current_serial = data[i][1]
        next_serial = data[i + 1][1]
        gap = next_serial - current_serial

        if gap > 1:
            # Calculate the time delta between the two timestamps
            time_delta = data[i + 1][2] - data[i][2]
            time_tsp_delta = data[i + 1][0] - data[i][0]

            # Populate missing serials
            for j in range(1, gap):
                new_serial = current_serial + j
                new_timestamp = data[i][2] + (time_delta / gap) * j
                new_timestp = data[i][0] + (time_tsp_delta // gap) * j
                filled_data.append((new_timestp, new_serial, new_timestamp))

    # Append the last tuple
    filled_data.append(data[-1])

    return filled_data


def fill_missing_serials_df(df, timestamp_col, serial_col, utc_timestamp_col):
    """
    Fills in missing chunk serial numbers in a DataFrame where the gap is greater than 1.
    The missing chunks are added with interpolated timestamps between the two existing ones.

    Parameters:
    -----------
    df : pandas.DataFrame
        The DataFrame containing the columns to be analyzed.

    timestamp_col : str
        The name of the column containing the numeric timestamps.

    serial_col : str
        The name of the column containing the chunk serial numbers.

    utc_timestamp_col : str
        The name of the column containing the UTC timestamps.

    Returns:
    --------
    pandas.DataFrame
        A new DataFrame with the missing chunk serials filled in where appropriate.
    """
    filled_rows = []

    for i in range(len(df) - 1):
        # Append the current row to the result list
        filled_rows.append(df.iloc[i])

        # Calculate the gap between consecutive chunk serial numbers
        current_serial = df.iloc[i][serial_col]
        next_serial = df.iloc[i + 1][serial_col]
        gap = next_serial - current_serial

        if gap > 1:
            # Calculate the time delta between the two timestamps
            time_delta = (
                df.iloc[i + 1][utc_timestamp_col] - df.iloc[i][utc_timestamp_col]
            )
            time_tsp_delta = df.iloc[i + 1][timestamp_col] - df.iloc[i][timestamp_col]

            # Populate missing serials
            for j in range(1, gap):
                new_serial = current_serial + j
                new_timestamp = df.iloc[i][utc_timestamp_col] + (time_delta / gap) * j
                new_timestp = df.iloc[i][timestamp_col] + (time_tsp_delta // gap) * j

                # Create a new row with interpolated values
                new_row = df.iloc[i].copy()
                new_row[serial_col] = new_serial
                new_row[utc_timestamp_col] = new_timestamp
                new_row[timestamp_col] = new_timestp

                filled_rows.append(new_row)

    # Append the last row
    filled_rows.append(df.iloc[-1])

    # Create a new DataFrame from the filled rows
    filled_df = pd.DataFrame(filled_rows).reset_index(drop=True)

    return filled_df
