# Aura Vault

The Vault stores fixed voice identity assets separately from performance cues.

Each identity has:

- `vectors/<identity_id>.pt`: a deterministic 512-d identity tensor.
- `metadata/<identity_id>.json`: source files, extractor version, sample rate, and rights notes.

The first extractor is `acoustic_stats_v1`, a local deterministic fingerprint that lets the pipeline start without downloading a neural speaker encoder. It is intentionally behind the same Vault contract we can later use for ECAPA, WavLM, CosyVoice speaker embeddings, or another consent-safe encoder.

Example:

```powershell
python -m src.aura.vault --id character_a --name "Character A" --source data/cleaned_wavs --consent-status verified --rights-notes "Use only clips with explicit permission."
```
