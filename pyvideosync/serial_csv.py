"""Export matched camera metadata and Blackrock UTC without rendering video."""

from pathlib import Path

import pandas as pd

SERIAL_CSV_COLUMNS = [
    "patient_id",
    "real_times",
    "serial",
    "frame_id",
    "camera",
    "blackrock_utc_timestamp",
    "source_mp4",
    "source_mp4_frame_idx",
    "nev_file",
    "ns5_file",
]


def patient_id_from_directory(patient_dir) -> str:
    name = Path(patient_dir).name
    if not name.endswith("Datafile") or name == "Datafile":
        raise ValueError(
            "patient_dir must be a patient folder named <patient_id>Datafile"
        )
    return name.removesuffix("Datafile")


def patient_relative_path(path, patient_dir) -> str:
    try:
        return Path(path).resolve().relative_to(Path(patient_dir).resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"source path is outside patient_dir: {path}") from exc


def build_serial_csv(
    joined_frames: pd.DataFrame,
    camera_serial: str,
    real_times: list,
    frame_ids: list,
    patient_dir,
    nev_path,
    ns5_path,
) -> pd.DataFrame:
    """Keep matcher rows; missing-source rows have blank original metadata.

    real_times and frame_id are looked up by the original MP4 row index.
    They are never reconstructed from corrected serials or Blackrock UTC.
    """
    if len(real_times) != len(frame_ids):
        raise ValueError("camera real_times and frame_id lengths differ")
    rows = joined_frames.reset_index(drop=True)
    indices = rows["mp4_frame_idx"].astype("int64")
    if ((indices < -1) | (indices >= len(frame_ids))).any():
        raise ValueError("matched frame index is outside the camera JSON")
    original_times = (
        pd.Series(real_times, dtype="object").reindex(indices).reset_index(drop=True)
    )
    original_ids = (
        pd.Series(frame_ids, dtype="Int64").reindex(indices).reset_index(drop=True)
    )
    utc = pd.to_datetime(rows["UTCTimeStamp"], utc=True)
    if utc.isna().any():
        raise ValueError("matched serial has no Blackrock UTC timestamp")
    paths = {
        path: patient_relative_path(path, patient_dir)
        for path in rows["mp4_file"].unique()
    }
    result = pd.DataFrame(
        {
            "patient_id": patient_id_from_directory(patient_dir),
            "real_times": original_times,
            "serial": rows["chunk_serial"].astype("int64"),
            "frame_id": original_ids,
            "camera": str(camera_serial),
            "blackrock_utc_timestamp": utc.dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "source_mp4": rows["mp4_file"].map(paths),
            "source_mp4_frame_idx": indices,
            "nev_file": patient_relative_path(nev_path, patient_dir),
            "ns5_file": patient_relative_path(ns5_path, patient_dir),
        }
    )
    return result[SERIAL_CSV_COLUMNS]
