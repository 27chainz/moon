# Aura Actor

Phase 1 proves the rendering foundation:

```text
SynthesisRequest -> CosyVoice runner -> WAV
```

Local product code owns the stable request contract in `synthesizer.py`. Colab owns the GPU runtime and executes `cosyvoice_colab_runner.py` inside the `cosyvoice` conda environment.

Phase 2 starts with voice design:

```text
BaseVoice + modifiers -> DesignedVoice -> SynthesisRequest
```

The first implementation is orchestration-only. It stores the chosen base reference and modifier metadata in the request. Later, the Actor can learn to use `style_prompt`, multiple reference clips, post-processing, or embedding edits.

Example local request:

```powershell
python -m src.aura.synthesizer --text "Hello. This is Aura speaking for the first time." --voice-id prototype_voice_001 --reference-audio /content/reference_24k_mono.wav --reference-text "Exact transcript here." --output-path /content/aura_hello_world.wav --request-path data/synthesis/aura_hello_world.json
```

Example Colab render:

```python
!conda run -n cosyvoice python /content/aura/cosyvoice_colab_runner.py --request /content/aura_hello_world.json
```
