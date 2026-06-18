# Aster Technical Stack

This document is the working source of truth for Aster's local-to-commercial production stack.

The current goal is not to overbuild a full platform too early. The goal is to keep the local pipeline shippable, while choosing infrastructure that can carry the same contracts into a commercial product.

## Product Shape

```text
Book source
-> Director APS
-> Cast Bible
-> Gemini TTS chunks
-> QA and rerender loop
-> chapter master audio
-> playback packaging
-> app streaming
```

## Current Local Stack

Use this while developing and tuning the audiobook production workflow.

| Layer | Choice | Purpose |
| --- | --- | --- |
| Pipeline language | Python | APS generation, export, render, QA, compile |
| Production format | JSON | APS, Cast Bible, manifests, render queues |
| Director | Gemini text model | Convert chapter text into APS |
| Actor/TTS | Gemini TTS | Generate character and narrator audio |
| Audio chunks | WAV | Lossless local production and QA |
| Audio processing | `soundfile`, `numpy`, `pyloudnorm`, `ffmpeg` | Stitching, loudness, diagnostics, packaging |
| Version control | Git + GitHub | Code, docs, rules, tests |
| Local storage | `Production/` folder | Ignored generated production outputs |
| Tests | `pytest` | Guard exporter, hygiene, compiler, QA behavior |

Local development should keep generated audio, manifests, and chapter outputs outside Git unless a small fixture is intentionally added for tests.

## Near-Future Commercial Stack

This is the recommended stack when Aster moves from local production to a hosted workflow.

| Layer | Recommended Choice | Reason |
| --- | --- | --- |
| Web app | Next.js | Admin dashboard, upload flow, QA screens |
| Mobile app | React Native or Expo | Audiobook playback app |
| Backend API | FastAPI | Python-native orchestration around the existing pipeline |
| Database | Supabase Postgres | Relational records for books, chapters, characters, chunks, QA, costs |
| Auth | Supabase Auth | Fast user/admin auth with Postgres integration |
| Object storage | Cloudflare R2 or Google Cloud Storage | Audio chunks, masters, HLS assets, covers |
| Queue | Google Pub/Sub | Async render jobs, retries, worker decoupling |
| Workers | Google Cloud Run Jobs | Run render/compile tasks to completion |
| AI Director | Gemini text model | APS generation and revision |
| AI Actor | Gemini TTS | Narration and character speech |
| SFX source | Licensed SFX library, later generative SFX | Controlled commercial-safe effects |
| Audio tooling | Python + FFmpeg | Mastering, HLS packaging, final exports |
| Monitoring | Google Cloud logs + Sentry | Job failures, API errors, client issues |
| Payments | Stripe | Creator billing and subscriptions later |

## Why This Stack

Supabase Postgres is the default database choice because Aster's data becomes relational quickly:

- books
- chapters
- scenes
- beats
- characters
- cast bible versions
- chunks
- render attempts
- QA notes
- costs
- playback assets

Firestore-style document storage would work at prototype scale, but chapter QA, rerender history, and cast consistency queries will become awkward.

Cloud Run Jobs fit render workers because audiobook rendering is batch work. A job starts, renders or compiles, writes output, updates status, and exits.

Pub/Sub fits render orchestration because the system needs durable async jobs rather than long HTTP requests.

R2 is attractive for audio delivery because audiobook files are large and egress costs matter. Google Cloud Storage is also acceptable if staying fully inside Google Cloud is operationally simpler.

## Commercial Data Model

Minimum production tables:

```text
books
chapters
characters
cast_bible_versions
aps_documents
render_manifests
render_chunks
render_attempts
qa_reviews
audio_assets
playback_assets
cost_estimates
```

Important records:

- `books`: owner, title, source status, production status
- `chapters`: book id, chapter number, source text path, APS path, QA status
- `characters`: canonical character ids and display names
- `cast_bible_versions`: locked voice identity per book
- `render_chunks`: chunk id, request path, audio path, status, retry count
- `qa_reviews`: human approval notes and rerender reasons
- `audio_assets`: WAV masters, MP3/M4B exports, HLS playlists
- `cost_estimates`: predicted and actual AI cost per book/chapter

## Hosted Pipeline

```text
1. Upload book
2. Split into chapters
3. Create book job
4. Run Gemini Director per chapter
5. Run APS hygiene
6. Create or apply Cast Bible
7. Export Gemini chunks
8. Estimate render cost
9. Require approval if cost exceeds limit
10. Enqueue render chunks
11. Render chunks with Cloud Run workers
12. Generate stitch previews
13. Human QA approves or rerenders chunks
14. Compile chapter master WAV
15. Package playback assets
16. Publish to app library
```

## Playback Stack

Do not stream giant production WAV files directly to the app.

Production should keep WAV masters for QA and archival quality, but the playback app should use segmented audio.

Recommended playback pipeline:

```text
chapter_master.wav
-> mastered AAC/MP3
-> HLS segments
-> R2/GCS storage
-> CDN-backed playback URL
-> mobile/web player
```

Recommended HLS output:

```text
chapter_001.m3u8
chapter_001_00000.ts
chapter_001_00001.ts
chapter_001_00002.ts
```

Example packaging command:

```powershell
ffmpeg -i chapter_001_master.wav `
  -c:a aac `
  -b:a 128k `
  -hls_time 6 `
  -hls_playlist_type vod `
  -hls_segment_filename "hls/chapter_001_%05d.ts" `
  "hls/chapter_001.m3u8"
```

Playback metadata should point to the HLS playlist, not the production WAV:

```json
{
  "chapter_id": "chapter_001",
  "master_audio": "chapter_001_master.wav",
  "playback": {
    "format": "hls",
    "playlist": "chapter_001.m3u8",
    "segment_duration_seconds": 6,
    "codec": "aac",
    "bitrate": "128k"
  }
}
```

Local packaging command:

```powershell
python -m src.aura.playback_packager `
  --input Production\book_001\chapter_001\chapter_001.wav `
  --output-dir Production\book_001\chapter_001\playback `
  --book-id book_001 `
  --chapter-id chapter_001
```

Use `--dry-run` when checking the packaging command without running FFmpeg.

## Cross-Device Resume

Cross-device pickup is a backend playback-state feature.

The app should periodically save a user's current position:

```text
user_id + book_id + chapter_id + position_seconds + updated_at
```

Minimum table:

```text
user_playback_progress
- user_id
- book_id
- chapter_id
- position_seconds
- percentage
- updated_at
- device_id
```

Update progress:

- when playback starts
- every 15-30 seconds while playing
- when paused
- when the app backgrounds
- when the user seeks
- when a chapter ends

Resume flow:

```text
1. User opens book on another device.
2. App requests latest playback progress.
3. Backend returns chapter id and position seconds.
4. App loads the chapter HLS playlist.
5. App seeks to position_seconds and resumes playback.
```

Conflict rule for the first version:

```text
Trust the newest updated_at.
```

Later, improve this by tracking book-level absolute position and preferring the furthest logical progress unless the newest event is an explicit seek.

## SFX And Soundstage

SFX should be a separate production layer, not mixed into Gemini TTS prompts.

Gemini TTS should speak narration and dialogue. The Soundstage layer should plan and mix:

- ambience
- spot effects
- room tone
- chapter intro/outro music
- scene transition beds

Recommended SFX metadata shape:

```json
{
  "sfx_id": "sfx_001",
  "type": "ambience",
  "description": "soft mountain wind and muffled falling snow",
  "start_beat": "scene_001_beat_001",
  "end_beat": "scene_001_beat_008",
  "level_db": -28,
  "fade_in_ms": 1200,
  "fade_out_ms": 1800
}
```

For literary audiobooks, SFX should be restrained. The first commercial version should support light ambience and rare spot effects, not full audio drama mixing.

## Cost Controls

Every hosted render should have a cost gate before work starts.

Required fields:

```json
{
  "estimated_director_cost": 0.0,
  "estimated_tts_cost": 0.0,
  "estimated_total_cost": 0.0,
  "hard_limit": 0.0,
  "approval_required": true
}
```

Rules:

- Estimate cost at export time.
- Store cost estimates per book and chapter.
- Block render if estimate exceeds budget.
- Track rerender cost separately.
- Never run whole-book rerenders by accident.

## QA Workflow

Commercial QA should be chunk-first, not whole-book-first.

QA assets:

- prompt previews
- rendered chunk audio
- stitch previews
- chapter master
- chapter playback package

QA statuses:

```text
pending
approved
needs_rerender
rejected
```

Common QA reasons:

```text
voice_drift
bad_accent
bad_pronunciation
energy_jump
volume_jump
stitch_artifact
sfx_too_loud
wrong_speaker
```

## Build Order

Do this in order:

1. Finish local voice consistency tuning.
2. Add SFX schema, not full SFX generation.
3. Add HLS packaging command/tool.
4. Add a local playback manifest.
5. Add a small QA dashboard later.
6. Move metadata into Supabase.
7. Move rendering into Cloud Run Jobs.
8. Add app playback from HLS.

The next practical local step is HLS packaging plus playback manifest generation. That turns a finished chapter WAV into something the future app can actually stream.
