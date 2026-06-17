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

APS is our internal production format. Gemini should not receive the raw APS or the full internal continuity packet as its main prompt.

APS compiles into a lean `tts_prompt` shaped like Gemini's advanced prompt examples:

1. `# AUDIO PROFILE`
2. `## THE SCENE`
3. `### DIRECTOR'S NOTES`
4. `### SAMPLE CONTEXT`
5. `#### TRANSCRIPT`

The render request may still store `chapter_context`, `continuity_packet`, `character_states`, and `character_voice_bibles` for audit/debugging, but the runner should prefer `tts_prompt` as the actual Gemini input when present.

```json
{
  "output_path": "data/generated_tests/scene_001.wav",
  "tts_prompt": "# AUDIO PROFILE: Speaker1 (Narrator)\n...\n\n#### TRANSCRIPT\nSpeaker1: [serious] Exact words to speak.",
  "speaker_voices": {
    "Speaker1": "Kore"
  }
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
# AUDIO PROFILE: Speaker1 (Character Name)
Gemini voice: Kore
Role: narrator
Voice identity: stable voice description.
Golden reference lines:
- "Short line from the source."

# AUDIO PROFILE: Speaker2 (Character Name)
Gemini voice: Algenib
Role: supporting
Voice identity: stable voice description.

## THE SCENE
<scene context, setting, mood>

### DIRECTOR'S NOTES
* The following is a speech synthesis request. Do not read these instructions aloud.
* Begin speaking only when you reach TRANSCRIPT.
<scene notes and per-speaker performance rules>

### SAMPLE CONTEXT
<genre/performance lane>

#### TRANSCRIPT
Speaker1: [serious] <exact render_text>
Speaker2: [sarcastic] <exact render_text>
```

Use Gemini audio tags only in the compiled Gemini prompt, never in APS `beat.text`. Good common tags include `[whispers]`, `[laughs]`, `[sighs]`, `[gasp]`, `[crying]`, `[trembling]`, `[panicked]`, `[sarcastic]`, `[serious]`, `[shouting]`, `[tired]`, and `[excited]`.

Speaker labels in `#### TRANSCRIPT` must match `speaker_voices` exactly. Prefer neutral aliases like `Speaker1` and `Speaker2`; store the real character mapping separately in `speaker_aliases`.

## Continuity Rules

- Always use the same `provider_voice` for a character within a production unless the cast sheet explicitly changes it.
- Put stable voice traits in every job's direction.
- Put normalized local emotion and intensity in the beat direction.
- Put nuance in scene/moment context, `delivery`, and `beat_modifier`; do not use prose phrases as emotion tokens.
- Do not rely on Gemini remembering previous chunks.
- For 40+ characters, render scene-by-scene and use the cast sheet as memory.

## Production Packet Fields

Prefer this shape in Gemini requests:

```markdown
# AUDIO PROFILE: Speaker1 (Character Name)
Stable character identity, provider voice, role, and golden lines.

THE SCENE
Local scene context only if this scene differs from the chapter-level context.

DIRECTOR'S NOTES
Chapter notes first, then scene notes, then per-speaker continuity.

SAMPLE CONTEXT
Chapter sample context, then scene-specific sample context if needed.

TRANSCRIPT
Speaker-labeled exact spoken text, with only intentional Gemini audio tags.
```

Do not put screenplay-style stage directions inside the dialogue lines unless they should be spoken or are supported Gemini audio tags.

Gemini multi-speaker TTS supports up to 2 speaker labels per request. Two characters sharing the same `provider_voice` still count as two speaker labels if they are sent as separate speakers. Do not send Narrator plus two dialogue characters in one multi-speaker request; render narration separately or split the scene.

Retry 500-class Gemini TTS failures. Gemini can occasionally return text tokens instead of audio tokens, causing transient server errors.

Sources:

- https://ai.google.dev/gemini-api/docs/speech-generation
