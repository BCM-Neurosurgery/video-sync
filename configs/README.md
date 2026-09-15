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
