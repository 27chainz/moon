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
  "mood": "somber, cold, physically strained",
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
  "context": "Egger says this aloud to himself while carrying Hannes.",
  "performance": {
    "emotion": "fear disguised as irritation",
    "intensity": 0.55,
    "pacing": "short and breathy",
    "delivery": "half command, half plea; spoken through exertion"
  }
}
```

## Rules

- Preserve source text exactly in `text`.
- Do not put stage directions in `text`.
- Use stable character ids, not only display names.
- Keep each beat renderable.
- Narration uses `speaker: "narrator"`.
- Dialogue uses the character id.
- Store emotion and delivery separately from text.
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
