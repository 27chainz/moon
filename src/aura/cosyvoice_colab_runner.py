import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

import torchaudio


def load_request(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Render an Aura synthesis request with CosyVoice on Colab.")
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--cosyvoice-root", default="/content/CosyVoice")
    parser.add_argument("--model-dir", default="pretrained_models/CosyVoice2-0.5B")
    args = parser.parse_args()

    sys.path.insert(0, args.cosyvoice_root)

    from cosyvoice.cli.cosyvoice import CosyVoice2

    payload = load_request(args.request)
    voice = payload["voice"]
    output_path = Path(payload["output_path"])
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cosyvoice = CosyVoice2(args.model_dir)
    results = cosyvoice.inference_zero_shot(
        payload["text"],
        voice["reference_text"],
        voice["reference_audio"],
        stream=False,
    )

    for result in results:
        torchaudio.save(str(output_path), result["tts_speech"], cosyvoice.sample_rate)

    result_path = output_path.with_suffix(output_path.suffix + ".json")
    result_payload = {
        "output_path": str(output_path),
        "voice_id": voice["voice_id"],
        "text": payload["text"],
        "sample_rate": cosyvoice.sample_rate,
        "performance": payload.get("performance") or {},
    }
    result_path.write_text(json.dumps(result_payload, indent=2), encoding="utf-8")
    print(f"Saved: {output_path}")
    print(f"Metadata: {result_path}")


if __name__ == "__main__":
    main()
