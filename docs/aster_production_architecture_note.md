# Aster Production Architecture Note

## Core Principle

APS is the source of truth.

Everything else is generated from APS and can be deleted, regenerated, swapped for another provider, or improved later.

See `docs/audio_rendering_backend_note.md` for the backend rendering pipeline and MVP implementation shape.

```text
Raw book file
-> cleaned book markdown
-> APS
   -> TTS jobs
   -> sound design jobs
   -> ambience jobs
   -> SFX jobs
   -> companion jobs
   -> QA jobs
   -> mix timeline
```

## 1. Raw Book Markdown

The raw book should first be converted into a clean `.md` source file.

This file preserves readable chapter text before production intelligence is added.

```text
book.epub / book.txt / book.pdf
-> book.md
-> APS
```

The markdown file is not the production bible. It is the clean manuscript source.

## 2. APS

APS is the master production file.

It contains:

- characters
- scenes
- dialogue policies
- source tracing
- narrative importance
- emotion
- intensity
- pace
- voice states
- scene context
- moment context
- sound design intent
- QA-critical metadata

Think:

```text
Book
-> APS
```

APS is the equivalent of a screenplay plus production bible.

## 3. TTS Render Jobs

TTS jobs are generated from APS.

They contain only what the TTS provider needs:

```json
{
  "speaker_voices": {},
  "chapter_context": "",
  "transcript": ""
}
```

This is the only thing Gemini TTS should see.

```text
APS
-> TTS jobs
-> Gemini
-> voice audio
```

TTS jobs are disposable render outputs.

## 4. Sound Design Packet

Sound design should be a dedicated packet generated from APS.

Example:

```json
{
  "scene_id": "scene_001",
  "emotion": "tense",
  "importance": 0.92,
  "environment": "old observatory",
  "weather": "heavy rain",
  "listener_position": "inside",
  "sound_sources": [
    {
      "type": "rain",
      "location": "outside"
    },
    {
      "type": "wind",
      "location": "door_gap"
    }
  ]
}
```

Then:

```text
Sound Design Packet
-> SFX/Ambience engine
-> audio assets
```

## 5. SFX And Ambience Jobs

SFX and ambience jobs should be separate from Gemini TTS jobs.

Reason:

Gemini may not generate SFX, and the production system may later use:

- ElevenLabs SFX
- custom asset libraries
- stock audio
- procedural ambience
- future sound models

Example:

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
      "asset_id": "sfx.lantern.small_shift.v1",
      "start_offset_sec": 2.2,
      "duration_sec": 0.8,
      "gain_db": -18
    }
  ]
}
```

These jobs are generated from APS but are not sent to Gemini TTS.

## 6. Mix Timeline

The mix timeline is the final assembly file.

It combines:

- voice tracks
- ambience tracks
- SFX tracks
- spatial positions
- timing
- ducking
- gain

Example:

```json
{
  "voice_track": "audio/chapter_004/segment_001.wav",
  "ambience_track": "ambience/rain_exterior_muffled_loop.wav",
  "sfx_track": "sfx/lantern_small_shift.wav",
  "spatial_position": "center",
  "start_time": 12.4
}
```

Final assembly:

```text
voice
+ ambience
+ SFX
+ spatial mix
-> final chapter audio
```

The mix timeline is also disposable and can be regenerated.

## 7. Scalable Shape

Current simple shape:

```text
Book
-> APS
-> Presence
-> Gemini
```

Target scalable shape:

```text
Book
-> APS
   -> TTS jobs
   -> SFX jobs
   -> ambience jobs
   -> companion jobs
   -> QA jobs
   -> mix timeline
```

## Decision

Use this architecture:

Store:

- APS
- clean source markdown

Generate:

- TTS jobs
- sound design packets
- SFX jobs
- ambience jobs
- companion jobs
- QA jobs
- mix timelines

Output:

- voice audio
- ambience assets
- SFX assets
- final chapter audio

The APS remains the master truth. All renderer-specific and mix-specific files are generated artifacts.
