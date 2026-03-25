# video2dataset (`@parva101/video2dataset`)

[![CI](https://github.com/Parva101/video2dataset/actions/workflows/ci.yml/badge.svg)](https://github.com/Parva101/video2dataset/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](./LICENSE)
[![FiftyOne Plugin](https://img.shields.io/badge/FiftyOne-plugin-orange.svg)](https://docs.voxel51.com/plugins/index.html)

A production-ready FiftyOne Python plugin that converts YouTube URLs or local
video files into image datasets by extracting representative keyframes.

## Features

- YouTube ingest via `yt-dlp`
- Local video ingest
- Three frame selection strategies:
- `uniform` (every N seconds)
- `scene_change` (histogram-based scene detection)
- `hybrid` (uniform + scene change)
- Optional perceptual hash deduplication (`pHash`)
- Automatic dataset creation + open in FiftyOne App
- Source metadata attached to samples and dataset info

## Operators

- `sample_from_youtube`
- `sample_from_video`

## Requirements

- Python 3.10+
- FiftyOne (latest stable recommended)
- Python packages in [`requirements.txt`](./requirements.txt)
- `ffmpeg` on `PATH` (recommended)

Install dependencies:

```bash
pip install -r requirements.txt
```

## Installation

Install from GitHub:

```bash
fiftyone plugins download https://github.com/Parva101/video2dataset
```

Install only this plugin:

```bash
fiftyone plugins download https://github.com/Parva101/video2dataset --plugin-names @parva101/video2dataset
```

Verify install:

```bash
fiftyone plugins list
fiftyone operators list
```

## Usage

1. Launch FiftyOne App
2. Open Operator Browser
3. Run:
- `Video Sampler: YouTube to dataset`, or
- `Video Sampler: local video to dataset`
4. Configure:
- `dataset_name` (required)
- `strategy`: `uniform | scene_change | hybrid`
- `max_frames`
- `interval_seconds`
- `scene_threshold` (`0` to `1`)
- `dedup` and `dedup_threshold`
- `overwrite_dataset`
- `output_dir` (optional)

## Output schema

Sample fields:

- `filepath`
- `source_type`
- `sampling_strategy`
- `timestamp_sec`
- `frame_number`

Additional YouTube fields:

- `source_url`
- `video_id`
- `title`
- `duration_sec`
- `uploader`

Dataset `info` fields:

- `source_type`
- `source_metadata`
- `extraction_info`

## Development

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
pytest
ruff check .
```

## Troubleshooting

- If YouTube download fails, verify the URL is public and update `yt-dlp`
- If no frames are selected, lower `scene_threshold` or `interval_seconds`
- If dedup removes everything, lower `dedup_threshold` or disable `dedup`
- If dataset exists, enable `overwrite_dataset` or use a different name

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md).

## Security

Report vulnerabilities via [SECURITY.md](./SECURITY.md).

## Changelog

See [CHANGELOG.md](./CHANGELOG.md).

## License

Licensed under Apache-2.0. See [LICENSE](./LICENSE).
