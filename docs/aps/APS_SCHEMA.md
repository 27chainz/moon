# APS Schema

APS is JSON.

Required top-level fields:

```json
{
  "aps_version": "0.1",
  "book_id": "book_001",
  "title": "Book Title",
  "chapter_id": "chapter_001",
  "chapter_title": "Chapter Title",
  "production_packet": {},
  "characters": {},
  "scenes": []
}
```

## Production Packet

APS uses production packets to give the Actor enough context before audio generation.

Use one chapter-level packet at the top:

```json
{
  "production_packet": {
    "the_scene": "Chapter-wide dramatic setup and context.",
    "director_notes": [
      "Chapter-wide performance rules.",
      "Narration style, dialogue energy, genre tone, and continuity rules."
    ],
    "sample_context": "The overall performance lane for this chapter."
  }
}
```

Then add a scene-level packet only when the scene changes, the emotional weather changes, or a new cast/setting is introduced.

```json
{
  "scene_context": "Local scene context.",
  "director_notes": [
    "Local performance instruction for this scene."
  ],
  "sample_context": "Local performance lane."
}
```

Compilation rule:

```text
chapter production packet
+ scene production packet
+ cast continuity
+ exact transcript
= actor prompt
```

## Character

```json
{
  "andreas_egger": {
    "display_name": "Andreas Egger",
    "role": "main",
    "stable_voice": "plain-spoken, physically strained, emotionally restrained",
    "provider_voice": {
      "gemini": "Kore",
      "resemble": "middle-aged alpine laborer, rough but controlled"
    },
    "do_not_change": ["accent", "age", "base tone"]
  }
}
```

## Scene

```json
{
  "scene_id": "scene_001",
  "title": "Mountain Descent",
  "summary": "Egger carries the dying Hannes through the snow.",
  "setting": "Alpine mountain path, February 1933, heavy snow",
  "scene_arc": {
    "start": "fatigue",
    "middle": "fear",
    "end": "relief"
  },
  "scene_context": "Sensory and dramatic context the Actor should understand before rendering.",
  "director_notes": [
    "Specific vocal performance instruction.",
    "Pacing, rhythm, accent, intensity, or emotional rules."
  ],
  "sample_context": "Comparable performance lane, genre, or casting reference.",
  "beats": []
}
```

## Beat

```json
{
  "beat_id": "scene_001_beat_004",
  "kind": "dialogue",
  "speaker": "andreas_egger",
  "text": "Just don't die on me now",
  "render_text": "Just don't die on me now",
  "source_trace": {
    "source_id": "source_document.text",
    "source_start": 120,
    "source_end": 148,
    "source_text": "\"Just don't die on me now,\" he said.",
    "spoken_text_span": {
      "source_start": 121,
      "source_end": 146,
      "text": "Just don't die on me now"
    },
    "removed_text_spans": [
      {
        "source_start": 148,
        "source_end": 155,
        "text": "he said",
        "reason": "Neutral attribution removed after speaker resolution."
      }
    ]
  },
  "context": "Egger says this aloud to himself while carrying Hannes.",
  "performance": {
    "emotion": "fear",
    "intensity": 0.55,
    "beat_modifier": 0.1,
    "pacing": "short and breathy",
    "delivery": "half command, half plea; spoken through exertion"
  }
}
```

`performance.emotion` is a normalized TTS emotion token, not a prose note. Put nuance in
`context`, `delivery`, scene/moment context, or `beat_modifier`.

Preferred hierarchy:

```text
scene_arc
-> moment_context
-> performance.emotion + performance.intensity + beat_modifier
```

Preferred beat provenance is `source_trace` plus `render_text`.
`source_span`, `internal_source_spans`, and `source_spoken_text` are legacy/debug fields and should be derived when needed instead of stored on every beat.

## Rules

- Preserve source text exactly in `text`.
- Use `render_text` as the canonical spoken text for production; it may omit safe labels or dialogue tags captured in `source_trace.removed_text_spans`.
- Do not put stage directions in `text`.
- Use stable character ids, not only display names.
- Keep each beat renderable.
- Narration uses `speaker: "narrator"`.
- Dialogue uses the character id.
- Store normalized emotion, intensity, and delivery separately from text.
- Put broad render guidance in `scene_context`, `director_notes`, and `sample_context`.
- Keep `director_notes` performable. Avoid abstract literary analysis that cannot be heard.

## Actor Prompt Packet

For high-quality renderers such as Gemini or DramaBox, APS should compile scene-level context into a production packet before the spoken transcript.

```markdown
## THE SCENE
Alpine mountain path, February 1933. Heavy snow muffles the world. Egger is carrying a dying man on his back.

## DIRECTOR'S NOTES
- The narration should be restrained, cold, and literary.
- Egger's dialogue should sound physically strained, afraid, and practical.
- Hannes should sound old, weak, dryly funny, and occasionally startlingly clear.

## SAMPLE CONTEXT
Bleak literary audiobook scene with sparse mountain silence and understated dread.
```

The production packet is not spoken as dialogue. It guides the Actor.
