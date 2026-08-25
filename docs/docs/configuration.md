# ⚙️ Configuration

Before running `video-sync`, you need to configure it using a YAML configuration file.

A sample configuration file is provided in the repo and is also available to
download below. Rename the example template to `config.yaml` and replace its
placeholder paths.

New configurations should use the `jobs` list shown in the example. Each job
defines one output window using either `window: neural` or `window: video`. The
`flat_dir` and `base_dir` forms remain available as directory-discovery
shortcuts; all forms are normalized to the same run and job model before
processing.

The following command renames the example config file to `config.yaml`
```sh
cp config.example.yaml config.yaml
```

[📥 Download config.example.yaml](examples/config.example.yaml)
