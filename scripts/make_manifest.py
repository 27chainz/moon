import os
import json
from pathlib import Path

def load_transcripts(transcripts_file: Path) -> dict:
    """Parses a transcript file in '<audio_id> <text>' format."""
    transcripts = {}
    if transcripts_file.exists():
        print(f"Loading transcripts from: {transcripts_file.resolve()}")
        try:
            with open(transcripts_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    # Format is '<id> <text>'
                    parts = line.split(" ", 1)
                    if len(parts) == 2:
                        audio_id, text = parts
                        transcripts[audio_id.strip()] = text.strip()
            print(f"Loaded {len(transcripts)} transcripts.")
        except Exception as e:
            print(f"Warning: Failed to parse transcripts: {e}")
    return transcripts

def main():
    # Resolve the project root directory (parent of src/)
    project_root = Path(__file__).resolve().parent.parent
    raw_wavs_dir = project_root / "data" / "raw_wavs"
    transcripts_file = project_root / "data" / "transcripts.txt"
    output_jsonl = project_root / "data" / "dataset.jsonl"

    print(f"Scanning directory: {raw_wavs_dir.resolve()}")
    
    if not raw_wavs_dir.exists():
        print(f"Error: Directory {raw_wavs_dir} does not exist.")
        return

    # Find all .wav files (case-insensitive)
    wav_files = sorted(
        [p for p in raw_wavs_dir.rglob("*") if p.is_file() and p.suffix.lower() == ".wav"]
    )

    print(f"Found {len(wav_files)} .wav file(s).")

    # Load mapping if available
    transcripts = load_transcripts(transcripts_file)

    # Write manifest
    try:
        with open(output_jsonl, "w", encoding="utf-8") as f:
            for wav_path in wav_files:
                # Store path relative to project root for portability across environments
                relative_path = wav_path.relative_to(project_root)
                
                # Use POSIX path separators (forward slashes) for compatibility in voice training pipelines (like NeMo/HF)
                audio_filepath = relative_path.as_posix()
                
                # Match transcript using audio filename stem (e.g. 422-122949-0000)
                audio_id = wav_path.stem
                text = transcripts.get(audio_id, "")
                
                row = {
                    "audio_filepath": audio_filepath,
                    "text": text
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        
        print(f"Manifest written successfully to: {output_jsonl.resolve()}")
    except Exception as e:
        print(f"Error writing manifest: {e}")

if __name__ == "__main__":
    main()
