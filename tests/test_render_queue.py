import json
from pathlib import Path

from src.aura.render_queue import create_render_queue, queue_request_paths


def test_create_render_queue_from_manifest(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest = {
        "chunks": [
            {
                "index": 4,
                "request_file": "requests/chunk_004.json",
                "prompt_preview_file": "qa/prompts/chunk_004.md",
                "audio_file": "audio/chunk_004.wav",
                "scene_id": "scene_002",
                "scene_position": "rising",
                "scene_exit_type": "sentence_end",
            }
        ]
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    output = tmp_path / "render_queue.json"

    queue = create_render_queue(manifest_path, output, ["004"], "Opal Miner test")

    assert output.exists()
    assert queue["chunks"][0]["chunk_id"] == "chunk_004"
    assert queue["chunks"][0]["prompt_preview_file"] == "qa/prompts/chunk_004.md"


def test_queue_request_paths_reads_queue(tmp_path):
    requests = tmp_path / "requests"
    requests.mkdir()
    request = requests / "chunk_004.json"
    request.write_text("{}", encoding="utf-8")
    queue_path = tmp_path / "render_queue.json"
    queue_path.write_text(
        json.dumps({"chunks": [{"request_file": "requests/chunk_004.json"}]}),
        encoding="utf-8",
    )

    assert queue_request_paths(queue_path) == [request]
