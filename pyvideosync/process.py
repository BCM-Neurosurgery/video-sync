from pyvideosync.video import Video
from pyvideosync.videojson import Videojson
from pyvideosync.nev import Nev
from pyvideosync.nsx import Nsx
from pyvideosync.dataframes import (
    CameraJSONDF,
    NevChunkSerialDF,
    ChunkSerialJoinedDF,
)
import os
from scipy.io.wavfile import write
from moviepy.editor import VideoFileClip, AudioFileClip
from pyvideosync.utils import (
    load_timestamps,
    save_timestamps,
)
import subprocess
import uuid
from scipy.io.wavfile import write as wav_write
import numpy as np


def process_video(abs_start_frame, abs_end_frame, pathutils, logger):
    logger.info("Processing Video...")
    video = Video(pathutils.video_path, abs_start_frame, abs_end_frame)
    selected_video_df = video.get_video_stats_df()
    logger.debug(f"Selected VIDEO:\n{selected_video_df}")
    return video


def process_camera_json(pathutils, logger):
    logger.info("Loading camera JSON file...")
    videojson = Videojson(pathutils.json_path)
    camera_df = videojson.get_camera_df(pathutils.cam_serial)
    CameraJSONDF(camera_df, logger).log_dataframe_info()
    return camera_df


def process_nev_chunk_serial(pathutils, logger):
    logger.info("Getting chunk serial data from NEV...")
    nev = Nev(pathutils.nev_abs_path)
    nev_chunk_serial_df = nev.get_chunk_serial_df()
    NevChunkSerialDF(nev_chunk_serial_df, logger).log_dataframe_info()
    nev.plot_cam_exposure_all(pathutils.cam_exposure_path, 0, 200)
    return nev_chunk_serial_df


def process_ns5_channel_data(pathutils, logger):
    logger.info(f"Getting {pathutils.ns5_channel} in NS5...")
    ns5 = Nsx(pathutils.ns5_abs_path)
    ns5_channel_df = ns5.get_channel_df(pathutils.ns5_channel)
    logger.debug(f"ns5_channel_df:\n{ns5_channel_df}")
    ns5.plot_channel_array(
        pathutils.ns5_channel,
        pathutils.channel_array_path,
    )
    return ns5, ns5_channel_df


def nev_inner_join_camera_json(nev_chunk_serial_df, camera_df, logger):
    logger.info("Merging NEV and Camera JSON...")
    chunk_serial_joined = nev_chunk_serial_df.merge(
        camera_df,
        left_on="chunk_serial",
        right_on="chunk_serial_data",
        how="inner",
    )
    ChunkSerialJoinedDF(chunk_serial_joined, logger).log_dataframe_info()
    return chunk_serial_joined


def ns5_leftjoin_joined(chunk_serial_joined, ns5, ns5_channel_df, logger):
    logger.info("Merging JSON, NEV with NS5...")
    ns5_slice = ns5.get_channel_df_between_ts(
        ns5_channel_df,
        chunk_serial_joined.iloc[0]["TimeStamps"],
        chunk_serial_joined.iloc[-1]["TimeStamps"],
    )
    all_merged = ns5_slice.merge(
        chunk_serial_joined,
        left_on="TimeStamp",
        right_on="TimeStamps",
        how="left",
    )
    return all_merged


def extract_and_save_frames(video, pathutils, logger):
    logger.info("Saving frames from video...")
    frame_list = video.extract_frames(pathutils.frames_output_dir)
    return frame_list


def save_frame_duration_to_file(
    all_merged_concat_df, frame_list, abs_start_frame, pathutils, logger
):
    logger.info("Getting frame durations in fps...")
    all_merged_concat_dropped = all_merged_concat_df.dropna()
    timestamps = all_merged_concat_dropped["TimeStamp"].tolist()
    frame_ids = all_merged_concat_dropped["frame_ids_reconstructed"].tolist()
    # TODO: this approach will discard the last frame
    # calculate the time in s for each frame
    # we know 30000 timestamps = 1s
    # so each timestamp is 1 / 30000s
    frame_duration = [
        (timestamps[i] - timestamps[i - 1]) / 30000 for i in range(1, len(timestamps))
    ]

    logger.info("Creating FFmpeg config file...")
    with open(pathutils.frame_list_path, "w") as f:
        # don't need the last frame
        for i in range(len(frame_ids) - 1):
            frame_index = int(frame_ids[i] - abs_start_frame)
            f.write(f"file '{frame_list[frame_index]}'\n")
            f.write(f"duration {frame_duration[i]}\n")
        # Write the last frame again to signal the end
        last_frame_index = int(frame_ids[i] - abs_start_frame)
        f.write(f"file '{frame_list[last_frame_index]}'\n")


def export_video_variable_fps(pathutils, logger):
    logger.info("Creating video with variable fps...")
    os.system(
        f"ffmpeg -f concat -safe 0 -i {pathutils.frame_list_path} -vsync vfr -pix_fmt yuv420p {pathutils.video_out_path}"
    )


def export_audio(all_merged_concat_df, pathutils, logger):
    audio_sample_rate = 30000  # 30kHz
    audio_data = all_merged_concat_df["Amplitude"].to_numpy()

    logger.info("Saving audio...")
    write(pathutils.audio_out_path, audio_sample_rate, audio_data)


def combine_video_audio(pathutils, logger):
    logger.info("Combining audio and video...")
    os.system(
        f"ffmpeg -i {pathutils.video_out_path} -i {pathutils.audio_out_path} -c:v copy -c:a aac -strict experimental {pathutils.final_video_out_path}"
    )
    logger.info("Video Sync Complete!!!")


def align_audio_video(video_path, audio_path, output_path):
    """
    Align the audio with the video and save the result to a new file.

    Args:
        video_path (str): Path to the input video file.
        audio_path (str): Path to the input audio file.
        output_path (str): Path to save the output video file with aligned audio.
    """
    video_clip = VideoFileClip(video_path)
    audio_clip = AudioFileClip(audio_path)
    video_clip = video_clip.set_audio(audio_clip)
    video_clip.write_videofile(
        output_path, codec="libx264", audio_codec="aac", logger="bar"
    )


def ffmpeg_concat_mp4s(mp4_paths, output_path):
    """
    Given a list of MP4 subclips (same format),
    create a filelist and run ffmpeg concat demuxer
    to stitch them together without re-encoding.
    """
    # 1) Write a temporary filelist
    list_file = os.path.join(os.path.dirname(output_path), "concat_filelist.txt")
    with open(list_file, "w") as f:
        for p in mp4_paths:
            # Escape path if it has spaces, though using quotes is usually enough
            f.write(f"file '{p}'\n")

    # 2) ffmpeg concat
    #    -f concat : use the concat demuxer
    #    -safe 0   : allow absolute paths
    #    -c copy   : do not re-encode, just copy streams
    cmd = [
        "ffmpeg",
        "-y",  # overwrite
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        list_file,
        "-c",
        "copy",
        output_path,
    ]
    print("Running FFmpeg concat:")
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)

    # (Optional) remove the temporary filelist
    os.remove(list_file)

    print(f"Concatenated video written to: {output_path}")
    return output_path


def make_synced_subclip_ffmpeg(df_sub, mp4_path, fps_audio=30000, out_dir="/tmp"):
    """
    Given:
        - df_sub: DataFrame that has columns ['frame_ids_relative', 'Amplitude'].
        - mp4_path: Path to the input video file (MP4).
        - fps_video: Frame rate of the video (used to convert frames -> seconds).
        - fps_audio: Sampling rate for the exported WAV.
        - out_dir: Directory where intermediate and final files will be written.

    Steps:
        1) Determine subclip time range (start_sec, end_sec).
        2) Extract that portion from the MP4 using ffmpeg (copy video track).
        3) Write a temporary WAV from the amplitude data.
        4) Mux the extracted video and new WAV into a final MP4, re-encoding audio if needed.
        5) Return the path to the final MP4.
    """
    video = Video(mp4_path)

    # 1) Identify which frames we need
    min_frame = df_sub["frame_ids_relative"].min()
    max_frame = df_sub["frame_ids_relative"].max()

    # 2) Convert frames to seconds
    start_sec = min_frame / video.fps
    # +1 so we include the last frame—ffmpeg’s -to is inclusive enough, but let’s be explicit
    end_sec = (max_frame + 1) / video.fps
    duration_sec = end_sec - start_sec

    print(
        f"Subclip frames: [{min_frame}, {max_frame}] => times: [{start_sec:.3f}, {end_sec:.3f}] => {duration_sec:.3f}s"
    )

    # Create output paths
    base_name = os.path.splitext(os.path.basename(mp4_path))[0]  # e.g. 'myvideo'
    unique_id = str(uuid.uuid4())[:8]  # random suffix to avoid collisions
    subclip_video_path = os.path.join(out_dir, f"{base_name}_subclip_{unique_id}.mp4")
    audio_wav_path = os.path.join(out_dir, f"{base_name}_audio_{unique_id}.wav")
    final_path = os.path.join(out_dir, f"{base_name}_final_{unique_id}.mp4")

    # 3) Extract video subclip with FFmpeg
    ffmpeg_cmd_subclip = [
        "ffmpeg",
        "-y",  # Overwrite existing output
        "-i",
        mp4_path,  # Input video file
        "-vf",
        f"select='between(n,{min_frame},{max_frame})',setpts=N/30/TB",  # Select frames & set timing
        "-vsync",
        "cfr",  # Constant frame rate (CFR)
        "-r",
        "30",  # Force 30 FPS
        "-c:v",
        "libx264",  # Re-encode as H.264
        subclip_video_path,
    ]

    print("Running FFmpeg subclip extraction:")
    print(" ".join(ffmpeg_cmd_subclip))
    subprocess.run(ffmpeg_cmd_subclip, check=True)

    # 4) Write the amplitude array to a WAV file
    #    Double-check shape and sample rate so final audio is correct length.
    audio_samples = df_sub["Amplitude"].values.astype(np.int16)

    # For a 206s audio track at 30,000 Hz (mono), you'd expect:
    # num_samples = 206 * 30000 = 6,180,000 samples
    # If you see double that, you might need to fix shape or fps_audio.
    print(f"Writing {len(audio_samples)} audio samples to WAV at {fps_audio} Hz.")
    wav_write(audio_wav_path, fps_audio, audio_samples)

    # 5) Mux the extracted video (no audio) with the new WAV
    #    We'll copy video (-c:v copy) and encode audio as AAC (-c:a aac).
    #    -shortest ensures it stops if one track is shorter.
    ffmpeg_cmd_mux = [
        "ffmpeg",
        "-y",
        "-i",
        subclip_video_path,  # video
        "-i",
        audio_wav_path,  # audio
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        final_path,
    ]
    print("Running FFmpeg mux:")
    print(" ".join(ffmpeg_cmd_mux))
    subprocess.run(ffmpeg_cmd_mux, check=True)

    # (Optional) Clean up intermediate subclip video and WAV
    # os.remove(subclip_video_path)
    # os.remove(audio_wav_path)

    print(f"Final subclip with audio: {final_path}")
    return final_path
