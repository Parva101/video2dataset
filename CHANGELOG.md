# Changelog

All notable changes to this project are documented in this file.

The format is based on Keep a Changelog, and this project follows
Semantic Versioning.

## [1.0.2] - 2026-03-24

### Changed

- Added Linux CI system dependencies (`ffmpeg`, `libgl1`) for reliable
  OpenCV-based tests in GitHub Actions
- Bumped plugin version in `fiftyone.yml` from `1.0.1` to `1.0.2`

## [1.0.1] - 2026-03-24

### Added

- OSS baseline documentation: `LICENSE`, `CONTRIBUTING.md`,
  `CODE_OF_CONDUCT.md`, `SECURITY.md`, and `CHANGELOG.md`
- GitHub community health files: issue templates and PR template
- CI workflow for linting and tests
- Dependabot configuration
- Dev dependency file and basic test suite

### Changed

- Improved README with setup, usage, development, and support sections
- Bumped plugin version in `fiftyone.yml` from `1.0.0` to `1.0.1`
- Improved YouTube download error messaging for clearer operator feedback

## [1.0.0] - 2026-03-24

### Added

- Initial release of `@parva101/video2dataset`
- Operators: `sample_from_youtube`, `sample_from_video`
- Frame extraction strategies: `uniform`, `scene_change`, `hybrid`
- Optional perceptual deduplication and metadata enrichment
