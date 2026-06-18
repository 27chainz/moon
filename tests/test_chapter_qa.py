import json

from src.aura.chapter_qa import set_chunk_qa_status


def test_set_chunk_qa_status(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "chunks": [
                    {"index": 4, "audio_file": "chunk_004.wav"},
                    {"index": 5, "audio_file": "chunk_005.wav"},
                ]
            }
        ),
        encoding="utf-8",
    )

    manifest = set_chunk_qa_status(manifest_path, ["004", "chunk_005"], "needs_rerender", "voice drift")

    assert manifest["chunks"][0]["qa_status"] == "needs_rerender"
    assert manifest["chunks"][1]["qa_status"] == "needs_rerender"
    assert manifest["chunks"][0]["qa_notes"][0]["note"] == "voice drift"
