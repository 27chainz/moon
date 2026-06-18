# Gemini Production Pipeline

This is the commercial Gemini audiobook path for Aster.

For the recommended infrastructure, storage, queue, playback, and SFX stack, see `docs/aster_tech_stack.md`.

## 1. Generate Source APS

The master production file is `aps.json`. For production, create it with the Gemini Director:

```powershell
python -m src.aura.gemini_director --input path\to\chapter_001.txt --output production\book_001\chapter_001\aps.json --book-id book_001 --title "Book Title" --chapter-id chapter_001 --chapter-title "Chapter 1"
```

It contains:

- book and chapter identity
- production packet
- cast and provider voice locks
- scenes
- beats
- performance metadata

The Gemini Director uses a text model to analyze the chapter. Gemini TTS does not receive this file directly.

For the broader audiobook production model, export provider-neutral Presence state first:

```powershell
python3 -m src.aura.presence_exporter --aps path\to\aps.json --output path\to\presence_state.json
```

This gives audio, SFX, spatial mix, and QA systems the same scene and segment structure without tying them to Gemini.

## 2. Export Gemini Chunks

Convert APS into Gemini-ready request chunks:

```powershell
python -m src.aura.gemini_chapter_exporter --aps path\to\aps.json --output-dir path\to\exported_gemini --max-chunk-words 230
```

This writes:

- `manifest.json`
- `requests/chunk_001.json`
- `requests/chunk_002.json`
- `qa/prompts/chunk_001.md`
- `qa/prompts/chunk_002.md`
- `audio/`
- `render_chapter.py`

The manifest stores direct `chunks` records with:

- `request_file`
- `prompt_preview_file`
- `audio_file`
- `scene_id`
- `scene_position`
- `scene_exit_type`
- `beat_ids`

Each request contains:

- `chapter_context`
- `continuity_packet`
- `scene_position`
- `scene_exit_type`
- `character_states`
- `transcript`
- `speaker_voices`
- `output_file`

Gemini multi-speaker TTS supports two speakers per request, so the exporter splits scenes into legal chunks.

The exporter also uses a word budget to keep render jobs short. The production target is about 1-2 minutes per chunk because longer Gemini TTS renders can lose volume, accent consistency, or performance energy over time. The default is 230 words; use 180-260 words as the normal testing range.

Before rendering, inspect the Markdown prompt previews in `qa/prompts/`. These previews show the exact Gemini-facing `tts_prompt`, speaker map, beat ids, and output path without needing to dig through JSON.

For quota-safe testing, create a render queue instead of rendering the whole chapter:

```powershell
python -m src.aura.render_queue create `
  --manifest path\to\exported_gemini\manifest.json `
  --output path\to\exported_gemini\render_queue_opal_miner.json `
  --chunks 004 005 006 007 008 `
  --purpose "Opal Miner cast bible voice consistency test"
```

## 3. Render Audio With Retry/Resume

Set `GEMINI_API_KEY`, then run:

```powershell
python -m src.aura.gemini_chapter_renderer --manifest path\to\exported_gemini\manifest.json
```

Or from inside the export folder:

```powershell
python render_chapter.py
```

To render only a queue:

```powershell
python -m src.aura.gemini_chapter_renderer `
  --manifest path\to\exported_gemini\manifest.json `
  --queue path\to\exported_gemini\render_queue_opal_miner.json
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

For chunk-level QA:

```powershell
python -m src.aura.chapter_qa `
  --manifest path\to\exported_gemini\manifest.json `
  --chunks 004 005 006 `
  --status needs_rerender `
  --note "Character voice drift."
```

When a chunk becomes the approved reference for a cast member:

```powershell
python -m src.aura.cast_bible approve-reference `
  --cast-bible Production\book_001\cast\cast_bible.json `
  --character-id opal_miner `
  --chapter-id chapter_001 `
  --chunk-id chunk_004 `
  --notes "Best Opal Miner render to date. Accent held and voice identity stayed stable."
```

After all chunks render:

```powershell
python -m src.aura.chapter_audio_compiler --manifest path\to\exported_gemini\manifest.json --output path\to\chapter_001.wav
```

The compiler:

- checks all rendered chunk files exist
- checks sample rate and channel consistency
- normalizes loudness when `pyloudnorm` is installed
- reads direct audio paths from `manifest.chunks`
- applies stitch gaps from `scene_exit_type`
  - `interruption`: `0ms`
  - `natural_pause`: base gap
  - `sentence_end`: base gap
  - `scene_end`: `3x` base gap
- stitches chunks in manifest order
- records chapter-level loudness/statistics
- writes a clean metadata file beside the final audio, e.g. `chapter_001.json` for `chapter_001.wav`
- blocks final compile unless `qa_status` is `approved`

For test compiles only:

```powershell
python -m src.aura.chapter_audio_compiler --manifest path\to\exported_gemini\manifest.json --output path\to\chapter_001.wav --allow-unapproved
```

## 5. Package Playback Assets

The chapter WAV is the production master, not the mobile playback format.

If a chapter has SFX, create the final chapter mix before packaging:

```powershell
python -m src.aura.sfx_mixer `
  --plan Production\book_001\chapter_001\sfx_sample\sfx_plan.sample.json
```

This writes the mixed WAV and a sidecar JSON report. Use the mixed WAV as the playback packaging input.

The SFX mixer supports fixed `level_db` and relative loudness fields such as:

```json
{
  "mix_role": "spot_important",
  "relative_to_voice_db": -10
}
```

Relative loudness uses the local voice window plus the SFX asset level to recommend gain before mixing.

Package the master into HLS assets:

```powershell
python -m src.aura.playback_packager `
  --input path\to\chapter_001.wav `
  --output-dir path\to\playback\chapter_001 `
  --book-id book_001 `
  --chapter-id chapter_001
```

For a command/manifest check without running FFmpeg:

```powershell
python -m src.aura.playback_packager `
  --input path\to\chapter_001.wav `
  --output-dir path\to\playback\chapter_001 `
  --book-id book_001 `
  --chapter-id chapter_001 `
  --dry-run
```

This writes:

- `chapter_001.m3u8`
- `chapter_001_00000.ts`
- `chapter_001_00001.ts`
- `playback_manifest.json`

The app should stream the HLS playlist, not the production WAV.

## Production Notes

- Keep chunks for rerendering and QA.
- Use final chapter audio for app playback.
- If one chunk sounds wrong, rerender only that chunk with `--force` or delete its WAV.
- Do not manually edit generated request files unless debugging a specific chunk.
- Use the manifest's `character_voice_bibles` as the long-range voice consistency anchor across chapters.
- Keep `qa_status` as `pending` until stitch previews and chapter playback pass.
