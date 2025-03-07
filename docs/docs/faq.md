# ❓ FAQ

### 1. What file formats are supported?
`video-sync` supports **NEV, NS5, and JSON** files for synchronization.

### 2. Why does my video output have missing frames?
Ensure your **FFmpeg** installation is up-to-date and that your **config.yaml** is correctly set.

### 3. How do I change the output format?
Modify the `output_format` field in your `config.yaml`:
```yaml
output_format: "mp4"
