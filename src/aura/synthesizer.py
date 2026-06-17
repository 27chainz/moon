import argparse
import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class VoiceReference:
    voice_id: str
    reference_audio: str
    reference_text: str
    display_name: str = ""
    rights_status: str = "prototype_only"
    provider_voice: str = ""


@dataclass
class SynthesisRequest:
    text: str
    voice: VoiceReference
    output_path: str
    performance: Optional[Dict[str, Any]] = None


@dataclass
class SynthesisResult:
    output_path: str
    voice_id: str
    text: str
    sample_rate: Optional[int] = None
    duration_seconds: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class BaseSynthesizer(ABC):
    @abstractmethod
    def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        """Render a synthesis request and return the generated audio location."""


class ManifestSynthesizer(BaseSynthesizer):
    """Writes synth requests for a remote renderer such as the Colab CosyVoice runner."""

    def __init__(self, manifest_path: Path):
        self.manifest_path = manifest_path
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)

    def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        row = request_to_dict(request)
        with self.manifest_path.open("a", encoding="utf-8") as manifest:
            manifest.write(json.dumps(row, ensure_ascii=False) + "\n")

        return SynthesisResult(
            output_path=request.output_path,
            voice_id=request.voice.voice_id,
            text=request.text,
            metadata={"status": "queued", "manifest_path": str(self.manifest_path)},
        )


def request_to_dict(request: SynthesisRequest) -> Dict[str, Any]:
    return {
        "text": request.text,
        "output_path": request.output_path,
        "performance": request.performance or {},
        "voice": asdict(request.voice),
    }


def request_from_dict(payload: Dict[str, Any]) -> SynthesisRequest:
    return SynthesisRequest(
        text=payload["text"],
        output_path=payload["output_path"],
        performance=payload.get("performance") or {},
        voice=VoiceReference(**payload["voice"]),
    )


def write_request(request: SynthesisRequest, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(request_to_dict(request), indent=2), encoding="utf-8")


def read_request(path: Path) -> SynthesisRequest:
    return request_from_dict(json.loads(path.read_text(encoding="utf-8")))


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an Aura synthesis request JSON file.")
    parser.add_argument("--text", required=True)
    parser.add_argument("--voice-id", required=True)
    parser.add_argument("--reference-audio", required=True)
    parser.add_argument("--reference-text", required=True)
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--request-path", type=Path, default=Path("data/synthesis/request.json"))
    args = parser.parse_args()

    request = SynthesisRequest(
        text=args.text,
        voice=VoiceReference(
            voice_id=args.voice_id,
            reference_audio=args.reference_audio,
            reference_text=args.reference_text,
        ),
        output_path=args.output_path,
    )
    write_request(request, args.request_path)
    print(f"Wrote synthesis request: {args.request_path}")


if __name__ == "__main__":
    main()
