import os
import subprocess
from scipy.io.wavfile import write as wav_write
import numpy as np
from moviepy import VideoFileClip, VideoClip, AudioFileClip, CompositeAudioClip
from tqdm import tqdm


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


def make_synced_subclip_ffmpeg(
    df_sub, mp4_path, out_dir, session_uuid, fps_video: int = 30
):
    """
    Given:
        - df_sub: DataFrame that has columns ['frame_ids_relative', 'Amplitude'].
        - mp4_path: Path to the input video file (MP4).
        - fps_video: Frame rate of the video (used to convert frames -> seconds).
        - out_dir: Directory where intermediate and final files will be written.
        - session_uuid: A shared UUID for all subclips in the session.

    Steps:
        1) Determine subclip time range (start_sec, end_sec).
        2) Extract that portion from the MP4 using ffmpeg (copy video track).
        3) Write a temporary WAV from the amplitude data.
        4) Mux the extracted video and new WAV into a final MP4, re-encoding audio if needed.
        5) Return the path to the final MP4.
    """
    # 1) Create output paths
    base_name = os.path.splitext(os.path.basename(mp4_path))[0]  # e.g. 'myvideo'
    subclip_video_path = os.path.join(
        out_dir, f"{base_name}_subclip_{session_uuid}.mp4"
    )
    audio_wav_path = os.path.join(out_dir, f"{base_name}_audio_{session_uuid}.wav")
    final_path = os.path.join(out_dir, f"{base_name}_final_{session_uuid}.mp4")

    # 2) Drop NaNs and grab the exact frame list
    df_frames = df_sub.dropna(subset=["mp4_frame_idx"])
    frames = df_frames["mp4_frame_idx"].astype(int).tolist()
    if not frames:
        raise ValueError("No frames to extract!")

    # 3) Write the amplitude array to a WAV file.
    # we should calculate the FPS of the audio from the data based on video duration
    # because it's not exactly 30khz
    audio_samples = df_sub["Amplitude"].values.astype(np.int16)
    exported_video_duration_s = len(frames) / fps_video
    fps_audio = int(len(audio_samples) / exported_video_duration_s)
    print(f"Writing {len(audio_samples)} audio samples to WAV at {fps_audio} Hz.")
    wav_write(audio_wav_path, fps_audio, audio_samples)

    # 4) For very large frame lists, write frame numbers to file
    # and use select_file
    frames_file_path = os.path.join(out_dir, f"{base_name}_frames_{session_uuid}.txt")

    # Write one frame number per line
    with open(frames_file_path, "w") as f:
        for frame in frames:
            f.write(f"{frame}\n")

    vf_filter = f"select_file='{frames_file_path}',setpts=N/{fps_video}/TB"

    ffmpeg_sub = [
        "ffmpeg",
        "-y",
        "-i",
        mp4_path,
        "-vf",
        vf_filter,
        "-fps_mode",
        "cfr",
        "-r",
        str(fps_video),
        "-c:v",
        "libx264",
        subclip_video_path,
    ]

    print("Extracting frames with FFmpeg:")
    print(f"Using frame list file: {frames_file_path}")
    subprocess.run(ffmpeg_sub, check=True)

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


def make_synced_subclip_moviepy(
    df_sub, mp4_path, out_dir, session_uuid, fps_video: int = 30
):
    """
    Memory-efficient MoviePy version: extracts frames by index and muxes with custom audio.
    """
    base_name = os.path.splitext(os.path.basename(mp4_path))[0]
    subclip_video_path = os.path.join(
        out_dir, f"{base_name}_subclip_{session_uuid}.mp4"
    )
    audio_wav_path = os.path.join(out_dir, f"{base_name}_audio_{session_uuid}.wav")
    final_path = os.path.join(out_dir, f"{base_name}_final_{session_uuid}.mp4")

    # 1. Get frame indices
    df_frames = df_sub.dropna(subset=["mp4_frame_idx"])
    frames = df_frames["mp4_frame_idx"].astype(int).tolist()
    if not frames:
        raise ValueError("No frames to extract!")

    # 2. Write audio to WAV
    audio_samples = df_sub["Amplitude"].values.astype(np.int16)
    exported_video_duration_s = len(frames) / fps_video
    fps_audio = int(len(audio_samples) / exported_video_duration_s)
    wav_write(audio_wav_path, fps_audio, audio_samples)

    # 3. Stream frames lazily using a custom VideoClip
    with VideoFileClip(mp4_path) as video:
        input_fps = video.fps
        print(f"Input video FPS: {input_fps}")
        frame_shape = video.get_frame(0).shape
        blank_frame = np.zeros(frame_shape, dtype=np.uint8)

        # Pre-calculate times for each frame index
        time_lookup = [(idx / input_fps if idx != -1 else None) for idx in frames]

        def make_frame(t):
            frame_idx = int(t * fps_video)
            actual_time = time_lookup[frame_idx]
            if actual_time is None:
                return blank_frame
            return video.get_frame(actual_time)

        # Lazy video generation
        clip = VideoClip(make_frame, duration=exported_video_duration_s)
        clip.fps = fps_video
        clip.write_videofile(
            subclip_video_path,
            codec="libx264",
            audio=False,
            fps=fps_video,
            preset="ultrafast",
            threads=2,
        )
        clip.close()

    # 4. Mux video and audio
    video_clip = VideoFileClip(subclip_video_path)
    audio_clip = AudioFileClip(audio_wav_path)
    new_audioclip = CompositeAudioClip([audio_clip])
    video_clip.audio = new_audioclip
    video_clip.write_videofile(
        final_path,
        codec="libx264",
        audio_codec="aac",
        fps=fps_video,
        preset="ultrafast",
        threads=2,
        logger=None,
    )
    video_clip.close()
    audio_clip.close()

    # Optionally clean up intermediates
    # os.remove(subclip_video_path)
    # os.remove(audio_wav_path)

    print(f"Final subclip with audio: {final_path}")
    return final_path
