# Gemini Production Pipeline

This is the commercial Gemini audiobook path for Aster.

## 1. Source APS

The master production file is `aps.json`.

It contains:

- book and chapter identity
- production packet
- cast and provider voice locks
- scenes
- beats
- performance metadata

Gemini does not receive this file directly.

For the broader audiobook production model, export provider-neutral Presence state first:

```powershell
python3 -m src.aura.presence_exporter --aps path\to\aps.json --output path\to\presence_state.json
```

This gives audio, SFX, spatial mix, and QA systems the same scene and segment structure without tying them to Gemini.

## 2. Export Gemini Chunks

Convert APS into Gemini-ready request chunks:

```powershell
python -m src.aura.gemini_chapter_exporter --aps path\to\aps.json --output-dir path\to\exported_gemini
```

This writes:

- `manifest.json`
- `requests/chunk_001.json`
- `requests/chunk_002.json`
- `audio/`
- `render_chapter.py`

Each request contains:

- `chapter_context`
- `continuity_packet`
- `scene_position`
- `character_states`
- `transcript`
- `speaker_voices`
- `output_file`

Gemini multi-speaker TTS supports two speakers per request, so the exporter splits scenes into legal chunks.

## 3. Render Audio With Retry/Resume

Set `GEMINI_API_KEY`, then run:

```powershell
python -m src.aura.gemini_chapter_renderer --manifest path\to\exported_gemini\manifest.json
```

Or from inside the export folder:

```powershell
python render_chapter.py
```

The renderer:

- skips chunks that already have valid audio
- retries failed chunks
- writes `manifest.render_log.json`
- records per-chunk audio metadata

## 4. Compile Chapter Audio

Before final compilation, create stitch previews:

```powershell
python -m src.aura.stitch_preview --manifest path\to\exported_gemini\manifest.json
```

This writes:

- `qa/stitches/stitch_001.wav`
- `qa/stitches/stitch_002.wav`
- `qa/stitches/stitch_previews.json`

Review these short files before approving the chapter.

After stitch review and chapter QA, approve the manifest:

```powershell
python -m src.aura.chapter_qa --manifest path\to\exported_gemini\manifest.json --status approved --note "Chapter passed stitch and performance QA."
```

After all chunks render:

```powershell
python -m src.aura.chapter_audio_compiler --manifest path\to\exported_gemini\manifest.json --output path\to\chapter_001.wav
```

The compiler:

- checks all rendered chunk files exist
- checks sample rate and channel consistency
- normalizes loudness when `pyloudnorm` is installed
- stitches chunks in manifest order
- writes a timeline metadata file beside the final audio
- blocks final compile unless `qa_status` is `approved`

For test compiles only:

```powershell
python -m src.aura.chapter_audio_compiler --manifest path\to\exported_gemini\manifest.json --output path\to\chapter_001.wav --allow-unapproved
```

## Production Notes

- Keep chunks for rerendering and QA.
- Use final chapter audio for app playback.
- If one chunk sounds wrong, rerender only that chunk with `--force` or delete its WAV.
- Do not manually edit generated request files unless debugging a specific chunk.
- Use the manifest's `character_voice_bibles` as the long-range voice consistency anchor across chapters.
- Keep `qa_status` as `pending` until stitch previews and chapter playback pass.
