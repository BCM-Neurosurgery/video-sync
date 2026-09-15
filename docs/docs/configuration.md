# ⚙️ Configuration

Before running `video-sync`, choose the configuration that matches which data
defines the synchronized output window:

| Workflow | Configuration |
| --- | --- |
| Raw NEV/NS5 pair | [Download `raw-neural-window.yaml`](https://raw.githubusercontent.com/BCM-Neurosurgery/video-sync/main/configs/raw-neural-window.yaml) |
| Stitched NEV/NS5 pair | [Download `stitched-neural-window.yaml`](https://raw.githubusercontent.com/BCM-Neurosurgery/video-sync/main/configs/stitched-neural-window.yaml) |
| Camera MP4 | [Download `video-window.yaml`](https://raw.githubusercontent.com/BCM-Neurosurgery/video-sync/main/configs/video-window.yaml) |

All three examples use the canonical `jobs` schema. Each job produces one final
output window. A configuration can contain multiple jobs, and directory neural
selections expand same-basename NEV/NS5 pairs into separate jobs.

Use `paired_ns5` for raw pairs. Stitched pairs require `first_raw_nev` plus the
first raw NEV used to construct the stitched timeline. Video-window jobs use
`coverage: require_full` so missing neural coverage fails rather than silently
shortening the requested video.

Copy the closest example to `config.yaml`, replace its placeholder paths, and
run `stitch-videos --config config.yaml`.
