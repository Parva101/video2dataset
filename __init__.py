"""
Video sampler plugin for FiftyOne.

This plugin provides operators that:
1. Download a YouTube video, sample frames, and build a dataset
2. Sample frames from a local video file and build a dataset
"""

import logging
import os
import re
import shutil
import tempfile
from pathlib import Path

import cv2
import fiftyone as fo
import fiftyone.operators as foo
import fiftyone.operators.types as types
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

SUPPORTED_STRATEGIES = ("uniform", "scene_change", "hybrid")
DEFAULT_MAX_FRAMES = 100
DEFAULT_INTERVAL_SECONDS = 2.0
DEFAULT_SCENE_THRESHOLD = 0.3
DEFAULT_DEDUP_THRESHOLD = 5


def _sanitize_name(name):
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", str(name)).strip("-")
    return cleaned or "video-sampler-dataset"


def _to_output_root(dataset_name, output_dir=None):
    if output_dir:
        root = Path(os.path.expanduser(output_dir)).resolve()
    else:
        root = (
            Path(os.path.expanduser(fo.config.default_dataset_dir)).resolve()
            / "video_sampler"
            / _sanitize_name(dataset_name)
        )

    root.mkdir(parents=True, exist_ok=True)
    return str(root)


def _extract_absolute_path(value):
    if isinstance(value, dict):
        return value.get("absolute_path")

    if isinstance(value, str):
        return value

    return None


def _parse_and_validate_params(ctx):
    strategy = ctx.params.get("strategy", "hybrid")
    max_frames = int(ctx.params.get("max_frames", DEFAULT_MAX_FRAMES))
    interval_seconds = float(
        ctx.params.get("interval_seconds", DEFAULT_INTERVAL_SECONDS)
    )
    scene_threshold = float(
        ctx.params.get("scene_threshold", DEFAULT_SCENE_THRESHOLD)
    )
    dedup = bool(ctx.params.get("dedup", True))
    dedup_threshold = int(
        ctx.params.get("dedup_threshold", DEFAULT_DEDUP_THRESHOLD)
    )
    overwrite_dataset = bool(ctx.params.get("overwrite_dataset", True))
    output_dir = (ctx.params.get("output_dir") or "").strip() or None

    if strategy not in SUPPORTED_STRATEGIES:
        raise ValueError(
            f"Unsupported strategy '{strategy}'. Expected one of: "
            + ", ".join(SUPPORTED_STRATEGIES)
        )

    if max_frames < 1:
        raise ValueError("max_frames must be >= 1")

    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be > 0")

    if not 0 <= scene_threshold <= 1:
        raise ValueError("scene_threshold must be in [0, 1]")

    if dedup_threshold < 0:
        raise ValueError("dedup_threshold must be >= 0")

    return {
        "strategy": strategy,
        "max_frames": max_frames,
        "interval_seconds": interval_seconds,
        "scene_threshold": scene_threshold,
        "dedup": dedup,
        "dedup_threshold": dedup_threshold,
        "overwrite_dataset": overwrite_dataset,
        "output_dir": output_dir,
    }


def download_youtube_video(url, output_dir):
    """Downloads a YouTube video with yt-dlp and returns (video_path, metadata)."""
    import yt_dlp

    ydl_opts = {
        "format": "best[ext=mp4]/best",
        "outtmpl": os.path.join(output_dir, "%(title)s-%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_path = ydl.prepare_filename(info)
            requested_downloads = info.get("requested_downloads") or []
            if requested_downloads:
                maybe_path = requested_downloads[0].get("filepath")
                if maybe_path and os.path.isfile(maybe_path):
                    video_path = maybe_path
    except Exception as e:
        raise ValueError(
            "Failed to download YouTube video. "
            "Please verify the URL is public/available and try again. "
            f"Details: {e}"
        ) from e

    if not os.path.isfile(video_path):
        raise RuntimeError(f"yt-dlp completed but no file was found at: {video_path}")

    video_metadata = {
        "source_url": url,
        "webpage_url": info.get("webpage_url") or url,
        "video_id": info.get("id"),
        "title": info.get("title", "Unknown"),
        "duration_sec": info.get("duration", 0) or 0,
        "uploader": info.get("uploader") or info.get("channel") or "Unknown",
    }
    return video_path, video_metadata


def compute_frame_difference(frame1, frame2):
    """Computes a histogram-based difference score in [0, 1]."""
    hist1 = cv2.calcHist(
        [frame1], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256]
    )
    hist2 = cv2.calcHist(
        [frame2], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256]
    )
    cv2.normalize(hist1, hist1)
    cv2.normalize(hist2, hist2)

    corr = float(cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL))
    corr = max(-1.0, min(1.0, corr))
    return (1.0 - corr) / 2.0


def compute_phash(frame, hash_size=8):
    """Computes perceptual hash of a BGR frame."""
    import imagehash

    pil_image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    return imagehash.phash(pil_image, hash_size=hash_size)


def extract_frames(
    video_path,
    output_dir,
    strategy="hybrid",
    max_frames=DEFAULT_MAX_FRAMES,
    interval_seconds=DEFAULT_INTERVAL_SECONDS,
    scene_threshold=DEFAULT_SCENE_THRESHOLD,
    dedup=True,
    dedup_threshold=DEFAULT_DEDUP_THRESHOLD,
):
    """
    Extracts frames from a video using the selected strategy.

    Returns:
        (frame_results, extraction_info)
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if fps <= 0:
        fps = 0.0

    duration = (total_frames / fps) if fps > 0 else 0.0
    interval_frames = max(1, int(round(interval_seconds * fps))) if fps > 0 else 30

    os.makedirs(output_dir, exist_ok=True)

    candidates = []
    prev_frame = None
    frame_idx = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        timestamp = (frame_idx / fps) if fps > 0 else 0.0
        should_extract = False

        if strategy == "uniform":
            should_extract = frame_idx % interval_frames == 0
        elif strategy == "scene_change":
            if prev_frame is None:
                should_extract = True
            else:
                should_extract = (
                    compute_frame_difference(prev_frame, frame) > scene_threshold
                )
        elif strategy == "hybrid":
            is_interval = frame_idx % interval_frames == 0
            if prev_frame is None:
                is_scene_change = True
            else:
                is_scene_change = (
                    compute_frame_difference(prev_frame, frame) > scene_threshold
                )
            should_extract = is_interval or is_scene_change
        else:
            cap.release()
            raise ValueError(f"Unsupported strategy: {strategy}")

        if should_extract:
            candidates.append(
                {
                    "frame": frame.copy(),
                    "frame_number": frame_idx,
                    "timestamp_sec": round(timestamp, 3),
                }
            )

        prev_frame = frame
        frame_idx += 1

    cap.release()

    if not candidates:
        raise RuntimeError(
            "No frames were selected. Try reducing scene_threshold or interval_seconds."
        )

    if dedup:
        deduped = []
        hashes = []
        for candidate in candidates:
            frame_hash = compute_phash(candidate["frame"])
            is_duplicate = any(abs(frame_hash - h) <= dedup_threshold for h in hashes)
            if not is_duplicate:
                deduped.append(candidate)
                hashes.append(frame_hash)
        candidates = deduped

    if not candidates:
        raise RuntimeError(
            "All candidate frames were removed by deduplication. "
            "Try lowering dedup_threshold or disabling dedup."
        )

    if len(candidates) > max_frames:
        indices = np.linspace(0, len(candidates) - 1, max_frames, dtype=int)
        candidates = [candidates[i] for i in indices]

    frame_results = []
    for idx, candidate in enumerate(candidates):
        frame_name = (
            f"frame_{idx:04d}_f{candidate['frame_number']:06d}_"
            f"t{candidate['timestamp_sec']:.3f}.jpg"
        )
        frame_path = os.path.join(output_dir, frame_name)
        ok = cv2.imwrite(frame_path, candidate["frame"])
        if not ok:
            raise RuntimeError(f"Failed to write extracted frame: {frame_path}")

        frame_results.append(
            {
                "filepath": frame_path,
                "frame_number": candidate["frame_number"],
                "timestamp_sec": candidate["timestamp_sec"],
            }
        )

    extraction_info = {
        "video_path": video_path,
        "fps": round(fps, 3),
        "total_frames": total_frames,
        "duration_sec": round(duration, 3),
        "strategy": strategy,
        "interval_seconds": interval_seconds,
        "scene_threshold": scene_threshold,
        "dedup": dedup,
        "dedup_threshold": dedup_threshold,
        "candidate_count": len(candidates),
        "extracted_count": len(frame_results),
    }
    return frame_results, extraction_info


def _make_dataset(
    dataset_name,
    frame_results,
    extraction_info,
    source_metadata,
    source_type,
    strategy,
    overwrite_dataset,
):
    if fo.dataset_exists(dataset_name):
        if overwrite_dataset:
            fo.delete_dataset(dataset_name)
        else:
            raise ValueError(
                f"Dataset '{dataset_name}' already exists. "
                "Enable overwrite_dataset or pick a different name."
            )

    dataset = fo.Dataset(name=dataset_name, persistent=True)

    samples = []
    for frame in frame_results:
        sample = fo.Sample(filepath=frame["filepath"])
        sample["source_type"] = source_type
        sample["sampling_strategy"] = strategy
        sample["timestamp_sec"] = frame["timestamp_sec"]
        sample["frame_number"] = frame["frame_number"]

        for key, value in source_metadata.items():
            sample[key] = value

        samples.append(sample)

    dataset.add_samples(samples)
    dataset.info["source_type"] = source_type
    dataset.info["source_metadata"] = source_metadata
    dataset.info["extraction_info"] = extraction_info
    dataset.save()
    return dataset


def _build_common_inputs(inputs):
    strategy_choices = types.RadioGroup()
    strategy_choices.add_choice("uniform", label="Uniform (every N seconds)")
    strategy_choices.add_choice("scene_change", label="Scene-change only")
    strategy_choices.add_choice("hybrid", label="Hybrid (uniform + scene-change)")
    inputs.enum(
        "strategy",
        strategy_choices.values(),
        label="Sampling strategy",
        description="How frames should be selected from the video",
        default="hybrid",
        view=strategy_choices,
    )

    inputs.int(
        "max_frames",
        label="Max frames",
        description="Maximum number of frames to keep in the dataset",
        min=1,
        default=DEFAULT_MAX_FRAMES,
    )
    inputs.float(
        "interval_seconds",
        label="Interval seconds",
        description="Used by uniform/hybrid modes",
        min=0.1,
        default=DEFAULT_INTERVAL_SECONDS,
    )
    inputs.float(
        "scene_threshold",
        label="Scene threshold",
        description="Scene-change sensitivity in [0, 1]. Lower is more sensitive.",
        min=0,
        max=1,
        default=DEFAULT_SCENE_THRESHOLD,
    )
    inputs.bool(
        "dedup",
        label="Perceptual dedup",
        description="Remove near-duplicate frames using pHash",
        default=True,
    )
    inputs.int(
        "dedup_threshold",
        label="Dedup threshold",
        description="Smaller values are stricter. 0 keeps only exact pHash matches.",
        min=0,
        default=DEFAULT_DEDUP_THRESHOLD,
    )
    inputs.bool(
        "overwrite_dataset",
        label="Overwrite dataset if it exists",
        description="Deletes an existing dataset with the same name before writing",
        default=True,
    )
    inputs.str(
        "output_dir",
        label="Output directory (optional)",
        description=(
            "Directory where extracted frame images are stored. "
            "Leave empty to use FiftyOne's default dataset directory."
        ),
        required=False,
    )


class SampleFromYouTube(foo.Operator):
    @property
    def config(self):
        return foo.OperatorConfig(
            name="sample_from_youtube",
            label="Video Sampler: YouTube to dataset",
            description=(
                "Download a YouTube video, extract representative frames, "
                "and create a FiftyOne image dataset."
            ),
            dynamic=True,
            execute_as_generator=True,
            allow_immediate_execution=True,
            allow_delegated_execution=True,
            default_choice_to_delegated=False,
        )

    def resolve_input(self, ctx):
        inputs = types.Object()
        inputs.str(
            "youtube_url",
            label="YouTube URL",
            description="Paste a full YouTube URL",
            required=True,
        )
        inputs.str(
            "dataset_name",
            label="Dataset name",
            description="Name for the FiftyOne dataset to create",
            required=True,
        )
        _build_common_inputs(inputs)

        return types.Property(
            inputs,
            view=types.View(label="Sample dataset from YouTube"),
        )

    def execute(self, ctx):
        youtube_url = (ctx.params.get("youtube_url") or "").strip()
        dataset_name = (ctx.params.get("dataset_name") or "").strip()
        params = _parse_and_validate_params(ctx)

        if not youtube_url:
            raise ValueError("youtube_url is required")
        if not dataset_name:
            raise ValueError("dataset_name is required")

        output_root = _to_output_root(dataset_name, params["output_dir"])
        download_dir = tempfile.mkdtemp(prefix="video_sampler_download_")
        frames_dir = os.path.join(output_root, "frames")
        shutil.rmtree(frames_dir, ignore_errors=True)

        yield ctx.ops.set_progress(
            progress=0.05, label="Downloading video from YouTube..."
        )
        video_path, source_metadata = download_youtube_video(youtube_url, download_dir)

        yield ctx.ops.set_progress(
            progress=0.35, label="Extracting representative frames..."
        )
        frame_results, extraction_info = extract_frames(
            video_path=video_path,
            output_dir=frames_dir,
            strategy=params["strategy"],
            max_frames=params["max_frames"],
            interval_seconds=params["interval_seconds"],
            scene_threshold=params["scene_threshold"],
            dedup=params["dedup"],
            dedup_threshold=params["dedup_threshold"],
        )

        source_metadata["source_url"] = youtube_url
        source_metadata["source_video_path"] = video_path
        source_metadata["output_frames_dir"] = frames_dir

        yield ctx.ops.set_progress(progress=0.85, label="Creating FiftyOne dataset...")
        dataset = _make_dataset(
            dataset_name=dataset_name,
            frame_results=frame_results,
            extraction_info=extraction_info,
            source_metadata=source_metadata,
            source_type="youtube",
            strategy=params["strategy"],
            overwrite_dataset=params["overwrite_dataset"],
        )

        yield ctx.ops.set_progress(
            progress=1.0,
            label=(
                f"Created dataset '{dataset.name}' with {len(frame_results)} frames"
            ),
        )
        yield ctx.ops.open_dataset(dataset.name)


class SampleFromVideo(foo.Operator):
    @property
    def config(self):
        return foo.OperatorConfig(
            name="sample_from_video",
            label="Video Sampler: local video to dataset",
            description=(
                "Select a local video file, extract representative frames, "
                "and create a FiftyOne image dataset."
            ),
            dynamic=True,
            execute_as_generator=True,
            allow_immediate_execution=True,
            allow_delegated_execution=True,
            default_choice_to_delegated=False,
        )

    def resolve_input(self, ctx):
        inputs = types.Object()
        inputs.file(
            "video_file",
            label="Video file",
            description="Choose a local video file",
            required=True,
            view=types.FileExplorerView(
                button_label="Choose video...",
                choose_button_label="Select",
            ),
        )
        inputs.str(
            "dataset_name",
            label="Dataset name",
            description="Name for the FiftyOne dataset to create",
            required=True,
        )
        _build_common_inputs(inputs)

        return types.Property(
            inputs,
            view=types.View(label="Sample dataset from local video"),
        )

    def execute(self, ctx):
        video_path = _extract_absolute_path(ctx.params.get("video_file"))
        dataset_name = (ctx.params.get("dataset_name") or "").strip()
        params = _parse_and_validate_params(ctx)

        if not video_path:
            raise ValueError("video_file is required")
        if not os.path.isfile(video_path):
            raise ValueError(f"Video file not found: {video_path}")
        if not dataset_name:
            raise ValueError("dataset_name is required")

        output_root = _to_output_root(dataset_name, params["output_dir"])
        frames_dir = os.path.join(output_root, "frames")
        shutil.rmtree(frames_dir, ignore_errors=True)

        yield ctx.ops.set_progress(
            progress=0.2, label="Extracting representative frames..."
        )
        frame_results, extraction_info = extract_frames(
            video_path=video_path,
            output_dir=frames_dir,
            strategy=params["strategy"],
            max_frames=params["max_frames"],
            interval_seconds=params["interval_seconds"],
            scene_threshold=params["scene_threshold"],
            dedup=params["dedup"],
            dedup_threshold=params["dedup_threshold"],
        )

        source_metadata = {
            "source_video_path": video_path,
            "output_frames_dir": frames_dir,
        }

        yield ctx.ops.set_progress(progress=0.85, label="Creating FiftyOne dataset...")
        dataset = _make_dataset(
            dataset_name=dataset_name,
            frame_results=frame_results,
            extraction_info=extraction_info,
            source_metadata=source_metadata,
            source_type="local_video",
            strategy=params["strategy"],
            overwrite_dataset=params["overwrite_dataset"],
        )

        yield ctx.ops.set_progress(
            progress=1.0,
            label=(
                f"Created dataset '{dataset.name}' with {len(frame_results)} frames"
            ),
        )
        yield ctx.ops.open_dataset(dataset.name)


def register(p):
    p.register(SampleFromYouTube)
    p.register(SampleFromVideo)
