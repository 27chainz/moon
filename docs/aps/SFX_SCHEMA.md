# SFX Schema

SFX is a separate Soundstage layer.

Gemini TTS speaks narration and dialogue. Aster places ambience, spot effects, motion effects, and music as separate audio layers during mixing.

```text
voice chapter WAV
+ SFX assets
+ music/room tone
= final chapter mix
```

## Design Principles

- SFX placement is metadata-driven, not prompt-driven.
- SFX must be implied by the source text or scene setting.
- Literary audiobook SFX should be restrained.
- Never cover dialogue.
- Ambience is safer than frequent spot effects.
- Phrase-level timing must have confidence and fallback.
- If timing confidence is low, degrade safely or skip and flag QA.

## APS Location

Put SFX entries on the scene that owns them:

```json
{
  "scene_id": "scene_004",
  "title": "Across The Street",
  "beats": [],
  "sfx": []
}
```

## SFX Types

```text
ambience          scene bed: wind, rain, traffic, crowd murmur
room_tone         subtle interior presence
spot              one-shot sound: knock, crack, glass break
motion            continuing action: footsteps, running, horse movement
background_event  loose event: distant car pass, thunder, far shout
music             intro, outro, scene transition, restrained underscore
transition        non-musical scene transition sound
```

## Placement Levels

### Scene-Level

Use for ambience, room tone, and music beds.

```json
{
  "sfx_id": "sfx_001",
  "type": "ambience",
  "description": "distant city traffic and occasional people in the background",
  "placement": "scene_span",
  "start_beat": "scene_004_beat_001",
  "end_beat": "scene_004_beat_012",
  "level_db": -34,
  "fade_in_ms": 1000,
  "fade_out_ms": 1500
}
```

This requires no word alignment and is the safest first SFX feature.

### Beat-Level

Use when the whole beat carries the action.

```json
{
  "sfx_id": "sfx_002",
  "type": "motion",
  "description": "hurried footsteps on pavement",
  "placement": "beat_span",
  "anchor_beat": "scene_004_beat_006",
  "level_db": -22,
  "duration_policy": {
    "policy": "loop_crossfade",
    "crossfade_ms": 80
  }
}
```

This uses the compiler's beat timing. It is less precise than phrase-level timing, but much more reliable.

### Phrase-Level

Use only when the sound needs to land on a specific phrase inside a longer beat.

```json
{
  "sfx_id": "sfx_003",
  "type": "motion",
  "description": "hurried footsteps on pavement",
  "placement": "phrase_span",
  "anchor_text": "ran hastily across the street",
  "anchor_beat": "scene_004_beat_006",
  "min_alignment_confidence": 0.82,
  "fallback_placement": "beat_span",
  "on_alignment_failure": "degrade_to_fallback",
  "level_db": -22,
  "duration_policy": {
    "policy": "loop_crossfade",
    "crossfade_ms": 80
  }
}
```

Phrase-level timing is a different reliability class from beat timing. It depends on aligning the rendered audio to the source phrase.

If `anchor_text` cannot be found with enough confidence, the mixer must not invent a timestamp. It must use `fallback_placement` or skip the SFX and flag QA.

## Alignment Strategy

Preferred timing sources:

```text
1. Provider-native word/phrase timestamps if available.
2. WhisperX alignment over rendered TTS audio.
3. Beat-level timing fallback.
4. Skip and flag QA.
```

For generated speech, WhisperX is the likely practical default because it transcribes what was actually spoken before alignment. Tools such as aeneas assume the text and audio match closely and may drift when the TTS changes punctuation or phrasing.

Phrase matching should be fuzzy:

```text
source anchor_text
-> ASR/alignment transcript
-> fuzzy edit-distance or embedding match
-> confidence score
-> accept only if confidence >= min_alignment_confidence
```

## Failure Policies

```text
degrade_to_fallback  use fallback_placement
skip_and_flag_qa     do not mix the SFX; write QA warning
```

Use `degrade_to_fallback` for most motion and background events.

Use `skip_and_flag_qa` for sounds that would be harmful if misplaced, such as gunshots, impacts, glass breaks, or any emotionally important one-shot.

## Duration Policies

```text
one_shot        play once at natural length
fixed           play for explicit duration_seconds
trim            trim to target span
match_beat      match beat start/end
match_phrase    match resolved phrase span
loop_crossfade  loop naturally with short crossfades
```

Recommended defaults:

| SFX type | Duration policy |
| --- | --- |
| ambience | `loop_crossfade` |
| room_tone | `loop_crossfade` |
| spot | `one_shot` |
| motion | `loop_crossfade` or `trim` |
| background_event | `one_shot` or `fixed` |
| music | `loop_crossfade` |

Do not time-stretch footsteps heavily. If motion must cover a longer phrase, loop or select a longer asset.

## Ducking

`duck_under_dialogue` is too vague for production. Use explicit ducking parameters:

```json
{
  "ducking": {
    "enabled": true,
    "duck_by_db": 6,
    "attack_ms": 40,
    "release_ms": 250
  }
}
```

The mixer should reduce SFX/music level while speech is active.

## Asset Resolution

The Director should describe the sound. The Resolver chooses a real asset.

```json
{
  "description": "soft mountain wind and muffled falling snow",
  "asset_query": {
    "tags": ["wind", "snow", "mountain", "soft"],
    "mood": "cold restrained literary",
    "avoid": ["storm", "horror", "cartoon"]
  },
  "asset": {
    "asset_id": "ambience_snow_mountain_001",
    "path": "assets/sfx/ambience_snow_mountain_001.wav",
    "license": "commercial",
    "source": "licensed_library"
  }
}
```

Commercial rule: do not use random internet sound files. Every asset must have a known license and source.

## Source Revision Safety

Phrase-level anchors should carry source revision data when available:

```json
{
  "anchor_text": "ran hastily across the street",
  "anchor_beat": "scene_004_beat_006",
  "source_text_hash": "sha256:...",
  "source_revision_id": "chapter_004_v3"
}
```

If the chapter source changes, the pipeline should mark phrase-level anchors as stale until revalidated.

## QA Output

Every SFX mix should write QA metadata:

```json
{
  "sfx_id": "sfx_003",
  "resolved_start_seconds": 84.92,
  "resolved_end_seconds": 87.61,
  "alignment_confidence": 0.88,
  "placement_used": "phrase_span",
  "fallback_used": false,
  "qa_status": "pending"
}
```

If fallback was used:

```json
{
  "sfx_id": "sfx_003",
  "alignment_confidence": 0.61,
  "placement_used": "beat_span",
  "fallback_used": true,
  "qa_warning": "Phrase alignment confidence below threshold."
}
```

## Build Stages

```text
Stage 1: Schema and validator only.
Stage 2: Scene-level ambience mixer.
Stage 3: Beat-level spot and motion placement.
Stage 4: Provider-native timestamps or WhisperX alignment.
Stage 5: Phrase-level SFX with confidence and fallback.
Stage 6: SFX QA previews and approval workflow.
```
