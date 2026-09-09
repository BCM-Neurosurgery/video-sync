# Program flow

`video-sync` normalizes every supported configuration into the same internal
model before it opens the large NS5 payloads:

```text
YAML -> RunSpec -> SyncJobSpec[] -> selected neural segments -> camera outputs
```

## 1. Normalize configuration

`PathUtils` loads the YAML. `resolve_run_spec()` then converts canonical `jobs`
and the older `sessions`, `nsp_dir`, `flat_dir`, or `base_dir` forms into one
`RunSpec`.

Each `SyncJobSpec` represents one final output window:

- `window: neural` resolves to one NEV/NS5 pair. Its neural interval selects
  the overlapping camera recordings.
- `window: video` resolves to one explicit camera recording group. Its JSON
  realtime bounds select every overlapping NEV/NS5 segment.

Directory selectors expand during normalization. A neural directory used with
`window: neural` creates one job per same-basename NEV/NS5 pair. A video
directory used with `window: video` creates one job per JSON recording group.

Preflight validation checks all selected paths, duplicate output names,
unpaired NEV/NS5 files, missing stitched anchors, and malformed selections
before processing starts.

## 2. Establish a UTC window

Raw data uses `time_anchor: paired_ns5`. The UTC origin comes from the paired
NS5 header and its first data-packet timestamp. Stitched data uses
`time_anchor: first_raw_nev` with the first raw NEV used to construct the
stitched timeline.

For a video-defined job, `read_nsx_time_bounds()` scans only NS5 packet headers
to find candidate UTC intervals. It seeks over signal payloads, so unrelated
NS5 files are not loaded into memory. The default `coverage: require_full`
policy also verifies that the selected intervals continuously cover the JSON
realtime window.

## 3. Load selected neural segments

Only the selected segments are fully loaded. For each one,
`_load_neural_context()` builds the calibrated NEV serial table and opens its
paired NS5:

```python
chunk_serial_df, utc_calibrated = _get_nev_chunk_serial_df(
    nev, ns5, segment.time_anchor, logger
)
```

Legacy stitched configurations without a UTC anchor retain serial-only camera
discovery. Video-defined jobs reject `serial_only`, because selecting the right
raw pair from a directory requires comparable UTC timestamps.

## 4. Join neural events to camera frames

For each camera and recording group, `Videojson.get_camera_df()` reconstructs
the frame sequence. The processor joins it to the NEV serial table on
`chunk_serial`, then slices the configured NS5 channel between the first and
last matched NEV timestamps.

Each `(camera recording, neural segment)` overlap becomes an ordered fragment
containing:

- the source MP4 path;
- the NS5 audio samples used to render that fragment; and
- frame-level NEV, camera, and NS5 mapping rows.

For `coverage: require_full`, the ordered mapped frames must exactly match the
requested source video frames. A missing neural interval therefore fails the
job instead of silently shortening the output.

## 5. Render and export

Fragments from the same MP4 are combined before rendering. If the requested
window crosses MP4 files, the rendered subclips are concatenated in recording
order. Neural fragments for one camera are also concatenated into one mapping,
with `synced_frame_idx` renumbered from zero across the final MP4.

All camera mappings are then combined into one task-level CSV:

```text
<output_dir>/<job>/
├── <job>_<camera_serial>.mp4
└── <job>_frame_mapping.csv
```

The pair `(camera_serial, synced_frame_idx)` identifies one final video frame.
`ns5_file` and `ns5_sample_idx` identify its sample in the original raw NS5,
including when one video window spans several NS5 files.
