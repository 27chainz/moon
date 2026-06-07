import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.aura.synthesizer import SynthesisRequest, VoiceReference, write_request


@dataclass
class VoiceModifier:
    trait: str
    value: str
    strength: float = 1.0


@dataclass
class BaseVoice:
    voice_id: str
    display_name: str
    reference_audio: str
    reference_text: str
    rights_status: str = "prototype_only"
    traits: Dict[str, Any] = field(default_factory=dict)
    style_notes: str = ""


@dataclass
class DesignedVoice:
    voice_id: str
    display_name: str
    base_voice_id: str
    reference_audio: str
    reference_text: str
    rights_status: str
    modifiers: List[VoiceModifier] = field(default_factory=list)
    style_prompt: str = ""

    def to_voice_reference(self) -> VoiceReference:
        return VoiceReference(
            voice_id=self.voice_id,
            display_name=self.display_name,
            reference_audio=self.reference_audio,
            reference_text=self.reference_text,
            rights_status=self.rights_status,
        )


class VoiceCatalog:
    def __init__(self, path: Path):
        self.path = path
        self.payload = json.loads(path.read_text(encoding="utf-8"))

    def get_base_voice(self, voice_id: str) -> BaseVoice:
        voices = self.payload.get("base_voices", {})
        if voice_id not in voices:
            raise KeyError(f"Base voice '{voice_id}' was not found in {self.path}.")
        return BaseVoice(voice_id=voice_id, **voices[voice_id])


class VoiceDesigner:
    def __init__(self, catalog: VoiceCatalog):
        self.catalog = catalog

    def design(
        self,
        voice_id: str,
        display_name: str,
        base_voice_id: str,
        modifiers: List[VoiceModifier],
    ) -> DesignedVoice:
        base = self.catalog.get_base_voice(base_voice_id)
        style_prompt = build_style_prompt(base, modifiers)
        return DesignedVoice(
            voice_id=voice_id,
            display_name=display_name,
            base_voice_id=base.voice_id,
            reference_audio=base.reference_audio,
            reference_text=base.reference_text,
            rights_status=base.rights_status,
            modifiers=modifiers,
            style_prompt=style_prompt,
        )


def build_style_prompt(base: BaseVoice, modifiers: List[VoiceModifier]) -> str:
    parts = []
    if base.style_notes:
        parts.append(base.style_notes)
    for modifier in modifiers:
        parts.append(f"{modifier.trait}: {modifier.value} ({modifier.strength:.2f})")
    return "; ".join(parts)


def designed_voice_to_dict(voice: DesignedVoice) -> Dict[str, Any]:
    payload = asdict(voice)
    payload["modifiers"] = [asdict(modifier) for modifier in voice.modifiers]
    return payload


def load_modifiers(raw: Optional[str], path: Optional[Path] = None) -> List[VoiceModifier]:
    if path:
        values = json.loads(path.read_text(encoding="utf-8"))
    elif raw:
        values = json.loads(raw)
    else:
        return []
    return [VoiceModifier(**item) for item in values]


def main() -> None:
    parser = argparse.ArgumentParser(description="Design a cast voice from a base voice and modifiers.")
    parser.add_argument("--catalog", type=Path, default=Path("data/vault/voice_catalog.json"))
    parser.add_argument("--base-voice-id", required=True)
    parser.add_argument("--voice-id", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--text", required=True)
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--request-path", type=Path, required=True)
    parser.add_argument(
        "--modifiers-json",
        help='JSON list, e.g. [{"trait":"texture","value":"slightly raspy","strength":0.5}]',
    )
    parser.add_argument("--modifiers-file", type=Path, help="Path to a JSON list of voice modifiers.")
    args = parser.parse_args()

    designer = VoiceDesigner(VoiceCatalog(args.catalog))
    designed_voice = designer.design(
        voice_id=args.voice_id,
        display_name=args.display_name,
        base_voice_id=args.base_voice_id,
        modifiers=load_modifiers(args.modifiers_json, args.modifiers_file),
    )
    request = SynthesisRequest(
        text=args.text,
        voice=designed_voice.to_voice_reference(),
        output_path=args.output_path,
        performance={
            "voice_design": designed_voice_to_dict(designed_voice),
            "style_prompt": designed_voice.style_prompt,
        },
    )
    write_request(request, args.request_path)
    print(f"Wrote designed voice request: {args.request_path}")
    print(f"Style prompt: {designed_voice.style_prompt}")


if __name__ == "__main__":
    main()
