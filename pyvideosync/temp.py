import os


def rename_video_files(directory: str):
    """
    Renames video files in the given directory by replacing the 'YFK_' prefix with 'YFKDatafile_'.

    Args:
        directory (str): The path to the directory containing the video files.

    Returns:
        None
    """
    for filename in os.listdir(directory):
        if filename.startswith("YFK_"):
            new_filename = filename.replace(
                "YFK_", "YFKDatafile_", 1
            )  # Replace only the first occurrence
            old_path = os.path.join(directory, filename)
            new_path = os.path.join(directory, new_filename)
            os.rename(old_path, new_path)
            print(f"Renamed: {filename} -> {new_filename}")


# Example usage:
directory_path = "/mnt/datalake/data/emu/YFKDatafile/VIDEO/20250212/"
rename_video_files(directory_path)
