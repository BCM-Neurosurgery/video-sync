from pyvideosync.video import Video
import os
import subprocess
import uuid
from scipy.io.wavfile import write as wav_write
import numpy as np


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


def make_synced_subclip_ffmpeg(df_sub, mp4_path, out_dir="/tmp"):
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
    # 1) Create output paths
    base_name = os.path.splitext(os.path.basename(mp4_path))[0]  # e.g. 'myvideo'
    unique_id = str(uuid.uuid4())[:8]  # random suffix to avoid collisions
    subclip_video_path = os.path.join(out_dir, f"{base_name}_subclip_{unique_id}.mp4")
    audio_wav_path = os.path.join(out_dir, f"{base_name}_audio_{unique_id}.wav")
    final_path = os.path.join(out_dir, f"{base_name}_final_{unique_id}.mp4")

    # 2) Identify which frames we need
    # this frame_ids_reconstructed should not have -1s
    # so we can safely use min/max
    min_frame = df_sub["frame_ids_relative"].min()
    max_frame = df_sub["frame_ids_relative"].max()

    # 3) Write the amplitude array to a WAV file.
    # we should calculate the FPS of the audio from the data based on video duration
    # because it's not exactly 30khz
    audio_samples = df_sub["Amplitude"].values.astype(np.int16)
    exported_video_duration_s = (max_frame - min_frame + 1) / 30
    fps_audio = int(len(audio_samples) / exported_video_duration_s)
    print(f"Writing {len(audio_samples)} audio samples to WAV at {fps_audio} Hz.")
    wav_write(audio_wav_path, fps_audio, audio_samples)

    # 4) Extract video subclip with FFmpeg
    ffmpeg_cmd_subclip = [
        "ffmpeg",
        "-y",  # Overwrite existing output
        "-i",
        mp4_path,  # Input video file
        "-vf",
        f"select='between(n,{min_frame},{max_frame})',setpts=N/30/TB",  # Select frames & set timing
        "-fps_mode",
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
