# video2dataset (`@parva101/video2dataset`)

A FiftyOne Python plugin that converts YouTube URLs or local video files into image datasets by extracting representative frames.

## What it does

- Downloads a YouTube video with `yt-dlp` or reads a local video file
- Extracts frames using one of three strategies:
- `uniform` (every N seconds)
- `scene_change` (histogram-based scene detection)
- `hybrid` (uniform + scene change)
- Optionally removes near-duplicate frames using perceptual hash deduplication
- Creates a persistent FiftyOne dataset and stores source metadata
- Automatically opens the dataset in the FiftyOne App

## Plugin operators

- `sample_from_youtube`
- `sample_from_video`

## Requirements

- FiftyOne (latest recommended)
- Python packages in [`requirements.txt`](./requirements.txt)
- `ffmpeg` available on PATH (recommended for robust video handling)

Install plugin dependencies:

```bash
pip install -r requirements.txt
```

## Install the plugin

From GitHub:

```bash
fiftyone plugins download https://github.com/Parva101/video2dataset
```

Or install only this plugin name:

```bash
fiftyone plugins download https://github.com/Parva101/video2dataset --plugin-names @parva101/video2dataset
```

## Usage

1. Launch FiftyOne App
2. Open the Operator Browser
3. Run either:
- `Video Sampler: YouTube to dataset`
- `Video Sampler: local video to dataset`
4. Configure parameters:
- `dataset_name` (required)
- `strategy`: `uniform | scene_change | hybrid`
- `max_frames`
- `interval_seconds`
- `scene_threshold` (0 to 1)
- `dedup` and `dedup_threshold`
- `overwrite_dataset`
- `output_dir` (optional)

## Output dataset schema

Each sample includes:

- `filepath`
- `source_type`
- `sampling_strategy`
- `timestamp_sec`
- `frame_number`

For YouTube runs, metadata also includes fields such as:

- `source_url`
- `video_id`
- `title`
- `duration_sec`
- `uploader`

Dataset-level info includes:

- `source_type`
- `source_metadata`
- `extraction_info`

## Local development

```bash
fiftyone app debug
```

Then refresh/restart after plugin edits to pick up changes.

## Troubleshooting

- If YouTube download fails, verify URL accessibility and update `yt-dlp`
- If no frames are kept, increase `max_frames`, lower `scene_threshold`, or disable dedup
- If a dataset already exists, enable `overwrite_dataset` or choose a new name

## License

Apache-2.0

