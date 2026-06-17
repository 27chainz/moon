# Audio Rendering Backend Note

## Backend Shape

The backend is an audio rendering pipeline.

```text
APS
-> job generator
   -> TTS jobs
   -> sound design jobs
   -> ambience jobs
   -> SFX jobs
   -> QA jobs
-> workers
   -> TTS renderer
   -> SFX resolver
   -> ambience resolver
   -> timeline builder
-> audio mixer
-> chapter master
-> final audiobook export
```

APS remains the stored source of truth. Generated jobs, timelines, and rendered files are disposable artifacts that can be regenerated.

## MVP Backend Stack

Recommended starting stack:

- Frontend: React Native / Next.js
- Backend API: FastAPI or Node.js
- Database: Supabase Postgres
- Queue: Redis + BullMQ or Celery
- Storage: Cloudflare R2
- Audio mixing: FFmpeg worker
- TTS: Gemini API
- Payments: Stripe / Apple IAP

## Worker Queue

Use a background job system.

Options:

- BullMQ + Redis for Node
- Celery + Redis for Python
- Inngest or Trigger.dev for simpler hosted workflows

Each chapter becomes a render batch. Each render batch can create child jobs:

- TTS jobs
- SFX jobs
- ambience jobs
- timeline job
- mix job
- QA job

## TTS Renderer

Input:

```json
{
  "speaker_voices": {},
  "chapter_context": "",
  "transcript": ""
}
```

Output:

```text
segment_001.wav
segment_002.wav
segment_003.wav
```

Store rendered voice files in Cloudflare R2. The database stores URLs, status, duration, and metadata.

## SFX Resolver

The SFX resolver maps production intent to concrete assets.

Example:

```text
rain_outside_windows -> ambience/rain_exterior_muffled_loop.wav
wind_under_door -> ambience/wind_door_gap_thin.wav
small lantern movement -> sfx/lantern_small_shift.wav
```

Input can come from APS-generated sound design packets:

```json
{
  "scene_id": "scene_001",
  "environment_sources": [
    {
      "sound": "rainfall",
      "position": "wide_above_and_behind_windows",
      "occlusion": 0.72
    }
  ],
  "sfx_cues": [
    {
      "asset_hint": "lantern_small_shift"
    }
  ]
}
```

## Timeline Builder

The timeline builder is the custom core of the backend.

It calculates:

- start time
- track type
- file URL
- pauses
- interruptions
- ambience loops
- SFX timing
- ducking
- volume
- fades
- spatial pan

Example output:

```json
{
  "chapter_id": "chapter_004",
  "tracks": [
    {
      "track": "voice",
      "file": "segment_001.wav",
      "start_time": 0.0,
      "gain_db": 0
    },
    {
      "track": "ambience",
      "file": "rain_exterior_muffled_loop.wav",
      "start_time": 0.0,
      "duration": 28.4,
      "gain_db": -24,
      "duck_under_voice": true
    },
    {
      "track": "sfx",
      "file": "lantern_small_shift.wav",
      "start_time": 2.2,
      "gain_db": -18
    }
  ]
}
```

The mixer should execute the timeline. The timeline builder decides what should happen.

## Pre-Render Validators

Before generating TTS jobs, run strict APS validation.

```text
APS
-> source trace validator
-> speaker validator
-> dialogue tag validator
-> punctuation validator
-> review flag validator
-> sequence validator
-> delivery archetype validator
-> renderer constraint validator
-> TTS jobs
```

If any validator fails, the chapter must not render.

The production engine can be imperfect. The validator must be strict.

Known APS failure modes and prevention notes live in:

```text
docs/aps_production_lessons.md
```

Current command:

```bash
python3 -m src.aura.aps_validator path/to/chapter.aps.json
```

## Audio Mixer

Use FFmpeg first.

FFmpeg can:

- stitch files
- overlay rain, ambience, music, and SFX
- adjust volume
- fade in and out
- pan left and right
- export WAV, MP3, and M4B

Later options:

- pydub
- librosa
- pedalboard
- moviepy
- DAW-style render engine

For MVP, FFmpeg is enough.

## Storage

Use Cloudflare R2.

Store:

- raw TTS segments
- SFX assets
- ambience loops
- mixed chapter files
- final audiobook exports

The database stores metadata and URLs, not large audio blobs.

## Database

Use Supabase Postgres for:

- books
- chapters
- clean source markdown
- APS JSON
- render batches
- render jobs
- segment status
- audio file paths
- sound assets
- mix timelines
- final chapter masters
- QA status

Possible tables:

```text
books
chapters
chapter_sources
aps_documents
render_batches
render_jobs
audio_segments
sound_assets
mix_timelines
chapter_masters
qa_reviews
```

## Build Order

Recommended build order:

```text
1. APS storage
2. TTS job generation
3. TTS rendering to R2
4. Basic timeline builder
5. FFmpeg chapter stitcher
6. SFX/ambience resolver
7. QA and rerender flow
```

## Product Priority

Do not overbuild spatial audio early.

Prioritize:

```text
1. Voice segments
2. Character performance
3. Basic ambience
4. SFX cues
5. Timeline assembly
6. QA and rerendering
7. Spatial audio
```

The timeline builder is the engine. TTS providers, SFX providers, and storage providers can change later.
