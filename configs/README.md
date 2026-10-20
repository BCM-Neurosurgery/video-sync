# Configuration examples

New configurations should use the `jobs` schema. Choose the example based on
which data defines the synchronized output window:

| Workflow | Configuration |
| --- | --- |
| One raw NEV/NS5 pair | [`raw-neural-window.yaml`](raw-neural-window.yaml) |
| One stitched NEV/NS5 pair | [`stitched-neural-window.yaml`](stitched-neural-window.yaml) |
| One camera MP4 | [`video-window.yaml`](video-window.yaml) |

Copy the closest example, update its paths, and pass the resulting file to
`stitch-videos`:

```sh
cp configs/raw-neural-window.yaml config.yaml
stitch-videos --config config.yaml
```

A configuration can contain multiple entries under `jobs`. A neural selection
can also use `kind: directory` to expand same-basename NEV/NS5 pairs into
separate jobs. The video-window example demonstrates neural directory
discovery.

Legacy `sessions`, `nsp_dir`, `flat_dir`, and `base_dir` configurations remain
supported for compatibility, but should not be used for new configurations.


## UTC for Blackrock NEV 3.0 recordings

Use `first_raw_nev` with the original recording's first NEV from the same NSP.
That file must contain one recording-start packet (ID `65529`, reason `0`).
The reference can precede the first split selected for processing.

```yaml
time_anchor:
  kind: first_raw_nev
  reference_path: "/path/to/NSP1-recording-001.nev"
```

The conversion is:

```python
utc = first_nev_header_utc + timedelta(
    seconds=(event_tick - recording_start_tick) / timestamp_resolution
)
```

Both serial-event conversion and NS5 coverage discovery use this reference.
NS5 sample indices still use each data packet's own starting tick. The first
digital event can arrive after recording starts, so it is not a UTC reference.
See Blackrock's [NEV 3.0 specification, sections 4.1 and 4.10](https://blackrockneurotech.com/wp-content/uploads/LB-0110-7-TOC-File-Format.pdf).

For a neural directory, `reference_path` applies to every selected pair. Limit
that directory/include selection to one recording and one NSP. To select
multiple recordings or NSPs, supply `reference_paths` keyed by resolved segment
name instead. Supplying both forms is an error.

```yaml
time_anchor:
  kind: first_raw_nev
  reference_paths:
    NSP1-recording-014: "/path/to/NSP1-recording-001.nev"
    NSP1-recording-015: "/path/to/NSP1-recording-001.nev"
    NSP2-recording-014: "/path/to/NSP2-recording-001.nev"
```

`first_raw_nev` now requires NEV 3.0 and reads the recording-start event instead
of the first digital event. Missing or multiple starts, malformed files,
different timestamp resolutions, decreasing NEV ticks, and a different start
in a target file are errors. These checks cannot prove that arbitrary files
share a clock; selecting the correct reference remains necessary. Stitched
files must preserve the original ticks. Rebasing ticks requires a different,
explicit time reference.

`paired_ns5` is rejected for version 3.0 files: split-file headers are not a
validated UTC reference for their first samples. Older files retain the legacy
paired convention, with discovery and mapping now using the same offset.
Legacy `flat_dir` configs select `paired_ns5`; migrate 3.0 recordings to the
`jobs` examples above. `embedded` remains available for files whose header
explicitly represents tick zero, and `serial_only` retains serial-only matching.

The result is UTC reconstructed from the recorded computer time and nominal
Blackrock clock frequency. This does not establish absolute clock accuracy or
correct camera/computer clock differences. Serial reception time also differs
from camera exposure time; this change preserves the existing first-byte choice.
