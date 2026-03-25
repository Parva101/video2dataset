import importlib.util
from pathlib import Path

import cv2
import numpy as np
import pytest

PLUGIN_PATH = Path(__file__).resolve().parents[1] / "__init__.py"
SPEC = importlib.util.spec_from_file_location("video2dataset_plugin", str(PLUGIN_PATH))
plugin = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(plugin)


class _Ctx:
    def __init__(self, params):
        self.params = params


def _make_test_video(path, nframes=60, fps=10):
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (320, 240),
    )
    assert writer.isOpened()

    for i in range(nframes):
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        frame[:, :, 0] = (i * 3) % 255
        frame[:, :, 1] = (i * 5) % 255
        frame[:, :, 2] = (i * 7) % 255
        cv2.rectangle(
            frame,
            (i % 200, i % 120),
            (80 + (i % 200), 80 + (i % 120)),
            (255, 255, 255),
            -1,
        )
        writer.write(frame)

    writer.release()


def test_sanitize_name():
    assert plugin._sanitize_name("My Dataset Name") == "My-Dataset-Name"
    assert plugin._sanitize_name("///") == "video-sampler-dataset"


def test_parse_and_validate_params_defaults():
    ctx = _Ctx(params={})
    out = plugin._parse_and_validate_params(ctx)
    assert out["strategy"] == "hybrid"
    assert out["max_frames"] == plugin.DEFAULT_MAX_FRAMES
    assert out["interval_seconds"] == plugin.DEFAULT_INTERVAL_SECONDS


def test_parse_and_validate_params_invalid_strategy():
    ctx = _Ctx(params={"strategy": "invalid"})
    with pytest.raises(ValueError, match="Unsupported strategy"):
        plugin._parse_and_validate_params(ctx)


def test_extract_frames_smoke(tmp_path):
    video_path = tmp_path / "input.mp4"
    _make_test_video(video_path, nframes=90, fps=12)

    frames, info = plugin.extract_frames(
        video_path=str(video_path),
        output_dir=str(tmp_path / "out"),
        strategy="hybrid",
        max_frames=10,
        interval_seconds=0.5,
        scene_threshold=0.2,
        dedup=True,
        dedup_threshold=5,
    )

    assert 1 <= len(frames) <= 10
    assert info["extracted_count"] == len(frames)
    assert info["strategy"] == "hybrid"
    for item in frames:
        assert Path(item["filepath"]).is_file()
