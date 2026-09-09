"""Tests for video/audio assembly helpers."""

from unittest.mock import patch

from pyvideosync.process import _mux_video_audio


def test_mux_copies_video_stream_to_preserve_frame_count():
    with patch("pyvideosync.process.subprocess.run") as run:
        _mux_video_audio("video.mp4", "audio.wav", "output.mp4")

    command = run.call_args.args[0]
    assert command[command.index("-c:v") + 1] == "copy"
    assert command[command.index("-c:a") + 1] == "aac"
    assert command[-1] == "output.mp4"
    run.assert_called_once_with(command, check=True)


if __name__ == "__main__":
    test_mux_copies_video_stream_to_preserve_frame_count()
    print("PASS  test_mux_copies_video_stream_to_preserve_frame_count")
