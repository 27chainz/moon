import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional

import torch


VECTOR_DIM = 512


@dataclass
class VoiceIdentity:
    identity_id: str
    display_name: str
    vector_path: str
    vector_dim: int
    extractor: str
    sample_rate: int
    source_files: List[str]
    consent_status: str
    rights_notes: str
    created_at: str


class AcousticVoiceDNAExtractor:
    """Deterministic 512-d acoustic fingerprint used until a neural encoder is plugged in."""

    name = "acoustic_stats_v1"

    def __init__(self, sample_rate: int = 24000, vector_dim: int = VECTOR_DIM):
        self.sample_rate = sample_rate
        self.vector_dim = vector_dim

    def extract(self, audio_paths: Iterable[Path]) -> torch.Tensor:
        features = []
        for audio_path in audio_paths:
            waveform, sample_rate = load_audio(audio_path)
            waveform = to_mono(waveform)
            waveform = resample_if_needed(waveform, sample_rate, self.sample_rate)
            feature = self._clip_feature(waveform)
            features.append(feature)

        if not features:
            raise ValueError("No audio files were provided for identity extraction.")

        vector = torch.stack(features, dim=0).mean(dim=0)
        vector = torch.nan_to_num(vector)
        vector = vector - vector.mean()
        vector = vector / vector.norm(p=2).clamp_min(1e-8)
        return vector.to(torch.float32)

    def _clip_feature(self, waveform: torch.Tensor) -> torch.Tensor:
        waveform = waveform.squeeze(0).to(torch.float32)
        waveform = waveform - waveform.mean()
        waveform = waveform / waveform.abs().max().clamp_min(1e-5)

        window = torch.hann_window(1024, device=waveform.device)
        spectrum = torch.stft(
            waveform,
            n_fft=1024,
            hop_length=256,
            win_length=1024,
            window=window,
            return_complex=True,
        ).abs()
        log_spectrum = torch.log1p(spectrum)

        spectral_mean = resize_1d(log_spectrum.mean(dim=1), 192)
        spectral_std = resize_1d(log_spectrum.std(dim=1), 192)

        frame_rms = spectrum.pow(2).mean(dim=0).sqrt()
        energy_quantiles = torch.quantile(
            frame_rms,
            torch.linspace(0.0, 1.0, 64, device=frame_rms.device),
        )

        freqs = torch.linspace(0.0, self.sample_rate / 2, spectrum.shape[0], device=waveform.device)
        centroid = (spectrum * freqs[:, None]).sum(dim=0) / spectrum.sum(dim=0).clamp_min(1e-8)
        centroid_quantiles = torch.quantile(
            centroid / (self.sample_rate / 2),
            torch.linspace(0.0, 1.0, 64, device=centroid.device),
        )

        feature = torch.cat([spectral_mean, spectral_std, energy_quantiles, centroid_quantiles])
        return feature[: self.vector_dim]


class VoiceVault:
    def __init__(self, root: Path):
        self.root = root
        self.vectors_dir = root / "vectors"
        self.metadata_dir = root / "metadata"
        self.vectors_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

    def create_identity(
        self,
        identity_id: str,
        display_name: str,
        audio_paths: Iterable[Path],
        extractor: Optional[AcousticVoiceDNAExtractor] = None,
        consent_status: str = "unverified",
        rights_notes: str = "",
    ) -> VoiceIdentity:
        extractor = extractor or AcousticVoiceDNAExtractor()
        source_files = [Path(path) for path in audio_paths]
        missing = [str(path) for path in source_files if not path.exists()]
        if missing:
            raise FileNotFoundError(f"Missing source audio file(s): {', '.join(missing)}")

        vector = extractor.extract(source_files)
        vector_path = self.vectors_dir / f"{identity_id}.pt"
        metadata_path = self.metadata_dir / f"{identity_id}.json"
        torch.save(vector, vector_path)

        identity = VoiceIdentity(
            identity_id=identity_id,
            display_name=display_name,
            vector_path=vector_path.relative_to(self.root.parent).as_posix(),
            vector_dim=int(vector.numel()),
            extractor=extractor.name,
            sample_rate=extractor.sample_rate,
            source_files=[path.as_posix() for path in source_files],
            consent_status=consent_status,
            rights_notes=rights_notes,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        metadata_path.write_text(json.dumps(asdict(identity), indent=2), encoding="utf-8")
        return identity

    def load_vector(self, identity_id: str) -> torch.Tensor:
        vector_path = self.vectors_dir / f"{identity_id}.pt"
        if not vector_path.exists():
            raise FileNotFoundError(f"No vector found for identity '{identity_id}'.")
        return torch.load(vector_path, map_location="cpu")


def load_audio(audio_path: Path) -> tuple[torch.Tensor, int]:
    try:
        import torchaudio

        return torchaudio.load(str(audio_path))
    except Exception:
        import soundfile as sf

        data, sample_rate = sf.read(str(audio_path), dtype="float32")
        waveform = torch.as_tensor(data)
        if waveform.ndim == 1:
            waveform = waveform.unsqueeze(0)
        else:
            waveform = waveform.transpose(0, 1)
        return waveform, sample_rate


def to_mono(waveform: torch.Tensor) -> torch.Tensor:
    if waveform.ndim != 2:
        raise ValueError(f"Expected audio tensor shaped [channels, samples], got {tuple(waveform.shape)}")
    if waveform.shape[0] == 1:
        return waveform
    return waveform.mean(dim=0, keepdim=True)


def resample_if_needed(waveform: torch.Tensor, source_rate: int, target_rate: int) -> torch.Tensor:
    if source_rate == target_rate:
        return waveform
    try:
        import torchaudio.functional as F

        return F.resample(waveform, source_rate, target_rate)
    except Exception:
        new_length = int(waveform.shape[-1] * target_rate / source_rate)
        return torch.nn.functional.interpolate(
            waveform.unsqueeze(0),
            size=new_length,
            mode="linear",
            align_corners=False,
        ).squeeze(0)


def resize_1d(values: torch.Tensor, length: int) -> torch.Tensor:
    return torch.nn.functional.interpolate(
        values.view(1, 1, -1),
        size=length,
        mode="linear",
        align_corners=False,
    ).view(-1)


def iter_audio_files(source: Path) -> List[Path]:
    if source.is_file():
        return [source]
    supported = {".wav", ".flac", ".mp3", ".m4a"}
    return sorted(path for path in source.rglob("*") if path.is_file() and path.suffix.lower() in supported)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a static Aura Voice DNA vector.")
    parser.add_argument("--id", required=True, dest="identity_id", help="Stable identity id, e.g. character_a.")
    parser.add_argument("--name", required=True, help="Human-readable identity name.")
    parser.add_argument("--source", required=True, type=Path, help="Audio file or directory of source clips.")
    parser.add_argument("--vault", type=Path, default=Path("data/vault"), help="Vault output directory.")
    parser.add_argument("--consent-status", default="unverified", help="Rights/consent status for the source clips.")
    parser.add_argument("--rights-notes", default="", help="Short notes about source clip permissions.")
    args = parser.parse_args()

    audio_files = iter_audio_files(args.source)
    vault = VoiceVault(args.vault)
    identity = vault.create_identity(
        identity_id=args.identity_id,
        display_name=args.name,
        audio_paths=audio_files,
        consent_status=args.consent_status,
        rights_notes=args.rights_notes,
    )

    print(f"Created identity '{identity.identity_id}' with {len(identity.source_files)} source file(s).")
    print(f"Vector: {identity.vector_path}")


if __name__ == "__main__":
    main()
