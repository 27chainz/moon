import os
import sys
import argparse
from pathlib import Path

# Detect available audio processing backends
BACKEND = None
try:
    import torchaudio
    import torch
    BACKEND = "torchaudio"
except ImportError:
    try:
        import soundfile as sf
        BACKEND = "soundfile"
    except ImportError:
        pass

def convert_with_torchaudio(flac_path: Path, wav_path: Path, target_sr: int):
    import torch
    import torchaudio
    import torchaudio.functional as F

    # Load audio
    waveform, sample_rate = torchaudio.load(str(flac_path))
    
    # Downmix to mono if stereo (standard for AI voice training)
    if waveform.shape[0] > 1:
        waveform = torch.mean(waveform, dim=0, keepdim=True)
        
    # Resample if needed
    if sample_rate != target_sr:
        waveform = F.resample(waveform, sample_rate, target_sr)
        
    # Save as WAV (16-bit PCM)
    torchaudio.save(str(wav_path), waveform, target_sr, encoding="PCM_S", bits_per_sample=16)

def convert_with_soundfile(flac_path: Path, wav_path: Path, target_sr: int):
    import soundfile as sf
    import numpy as np

    # Read FLAC audio
    data, sample_rate = sf.read(str(flac_path))
    
    # Downmix to mono if stereo
    if len(data.shape) > 1:
        data = np.mean(data, axis=1)
        
    # Resample if needed
    if sample_rate != target_sr:
        try:
            import scipy.signal as signal
            num_samples = int(len(data) * target_sr / sample_rate)
            data = signal.resample(data, num_samples)
        except ImportError:
            # Fallback to numpy linear interpolation to avoid strict dependency on scipy
            duration = len(data) / sample_rate
            new_num_samples = int(duration * target_sr)
            data = np.interp(
                np.linspace(0, len(data) - 1, new_num_samples),
                np.arange(len(data)),
                data
            )
            
    # Save as WAV (16-bit PCM)
    sf.write(str(wav_path), data, target_sr, format='WAV', subtype='PCM_16')

def main():
    parser = argparse.ArgumentParser(description="Convert FLAC files in data/raw_wavs/ to WAV format.")
    parser.add_argument(
        "--sr", 
        type=int, 
        choices=[16000, 24000], 
        default=24000, 
        help="Target sample rate in Hz (default: 24000)"
    )
    args = parser.parse_args()

    # Resolve project root and raw_wavs directory
    project_root = Path(__file__).resolve().parent.parent
    raw_wavs_dir = project_root / "data" / "raw_wavs"

    print(f"Scanning directory: {raw_wavs_dir.resolve()}")
    if not raw_wavs_dir.exists():
        print(f"Error: Directory {raw_wavs_dir} does not exist.")
        sys.exit(1)

    # Scan for FLAC files
    flac_files = sorted(
        [p for p in raw_wavs_dir.rglob("*") if p.is_file() and p.suffix.lower() == ".flac"]
    )

    if not flac_files:
        print("No .flac files found to convert.")
        return

    # Check for backend
    if BACKEND is None:
        print("\n[ERROR] No audio backend found!")
        print("Please install one of the following backends to process audio:")
        print("  Option A (Recommended for AI pipelines): pip install torch torchaudio")
        print("  Option B (Lightweight utility):           pip install soundfile numpy (optional: scipy)")
        sys.exit(1)

    print(f"Using audio backend: '{BACKEND}'")
    print(f"Found {len(flac_files)} .flac file(s) to convert to {args.sr}Hz WAV.")

    converted_count = 0
    for flac_path in flac_files:
        wav_path = flac_path.with_suffix(".wav")
        print(f"Converting: {flac_path.name} -> {wav_path.name}...")
        
        try:
            if BACKEND == "torchaudio":
                convert_with_torchaudio(flac_path, wav_path, args.sr)
            else:
                convert_with_soundfile(flac_path, wav_path, args.sr)
                
            # Remove original FLAC file
            flac_path.unlink()
            converted_count += 1
        except Exception as e:
            print(f"  [ERROR] Failed to convert {flac_path.name}: {e}")

    print(f"\nSuccessfully converted {converted_count} file(s) to WAV.")

if __name__ == "__main__":
    main()
