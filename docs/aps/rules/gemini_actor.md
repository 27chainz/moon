# APS To Gemini Actor Rules

Gemini TTS is a premium Actor. It accepts natural-language direction and prebuilt voice names.

`gemini_standard.md` is the canonical Gemini format. Use it as the source of truth.

Gemini is not DramaBox. Do not use the DramaBox quoted/unquoted prompt pattern for Gemini.

Official Gemini TTS patterns:

Single speaker:

```text
Say cheerfully: Have a wonderful day!
```

Multi-speaker:

```text
TTS the following conversation between Joe and Jane:
Joe: How's it going today Jane?
Jane: Not too bad, how about you?
```

The speaker names in the prompt must match the speaker names passed in `MultiSpeakerVoiceConfig`.

## Conversion Rule

APS becomes an internal Gemini render request with separate context and transcript:

```json
{
  "output_path": "data/generated_tests/scene_001.wav",
  "performance": {
    "direction": "Scene and performance direction.",
    "system_instruction": "Chapter and scene context sent as Gemini system instruction.",
    "transcript": "Exact transcript sent as Gemini contents."
  },
  "speakers": [],
  "turns": []
}
```

## Single-Speaker Beat

Use `render_text` as the exact content to speak. Fall back to `text` only for legacy APS that does not include `render_text`.

```json
{
  "text": "Just don't die on me now",
  "render_text": "Just don't die on me now",
  "voice": {
    "voice_id": "andreas_egger",
    "provider_voice": "Kore"
  },
  "performance": {
    "emotion": "fear",
    "intensity": 0.65,
    "style_prompt": "Say with physical strain, short and breathy: Just don't die on me now"
  }
}
```

## Two-Speaker Scene

Gemini multi-speaker TTS supports up to two speakers per request. For larger scenes, split into smaller render jobs.

```json
{
  "performance": {
    "direction": "Make Egger sound strained and afraid, and Hannes dying but dryly defiant.",
    "system_instruction": "Make Egger sound strained and afraid, and Hannes dying but dryly defiant.",
    "transcript": "TTS the following conversation between Egger and Hannes:\nEgger: Are you dead?\nHannes: No, you limping devil!"
  },
  "speakers": [
    {"speaker": "Egger", "voice_id": "andreas_egger", "provider_voice": "Kore"},
    {"speaker": "Hannes", "voice_id": "horned_hannes", "provider_voice": "Algenib"}
  ],
  "turns": [
    {"speaker": "Egger", "text": "Are you dead?"},
    {"speaker": "Hannes", "text": "No, you limping devil!"}
  ]
}
```

## Prompt Construction

Single speaker:

```text
Say in this style: <voice continuity + scene context + beat performance>

<exact beat text>
```

Multi-speaker:

```text
system_instruction:

## CHAPTER CONTEXT
<chapter context>

## THE SCENE
<scene context>

## DIRECTOR'S NOTES
<scene notes and per-speaker performance rules>

## SAMPLE CONTEXT
<genre/performance lane>

contents:

TTS the following conversation between <Speaker A> and <Speaker B>:
<Speaker A>: <exact render_text>
<Speaker B>: <exact render_text>
```

Use Gemini audio tags only when intentionally desired and supported, such as `[whisper]`, `[short pause]`, or `[yawn]`. Do not insert tags into the source text in APS. Tags belong in the generated Gemini prompt only.

## Continuity Rules

- Always use the same `provider_voice` for a character within a production unless the cast sheet explicitly changes it.
- Put stable voice traits in every job's direction.
- Put normalized local emotion and intensity in the beat direction.
- Put nuance in scene/moment context, `delivery`, and `beat_modifier`; do not use prose phrases as emotion tokens.
- Do not rely on Gemini remembering previous chunks.
- For 40+ characters, render scene-by-scene and use the cast sheet as memory.

## Production Packet Fields

Prefer this separation in Gemini requests:

```markdown
system_instruction:

CHAPTER CONTEXT
Chapter-wide setting, tone, continuity, and performance lane.

THE SCENE
Local scene context only if this scene differs from the chapter-level context.

DIRECTOR'S NOTES
Chapter notes first, then scene notes, then per-speaker continuity.

SAMPLE CONTEXT
Chapter sample context, then scene-specific sample context if needed.

contents:

TTS the following conversation between ...
```

Do not put screenplay-style stage directions inside the dialogue lines unless they should be spoken or are supported Gemini audio tags.

Gemini multi-speaker TTS supports up to 2 speakers per request. Do not send Narrator plus two dialogue characters in one multi-speaker request; render narration separately or split the scene.

Sources:

- https://ai.google.dev/gemini-api/docs/speech-generation
