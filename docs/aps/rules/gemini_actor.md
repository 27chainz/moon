# APS To Gemini Actor Rules

Gemini TTS is a premium Actor. It accepts natural-language direction, audio tags, and prebuilt voice names.

This file is the canonical Gemini Actor prompt format.

Gemini is not DramaBox. Do not use the DramaBox quoted/unquoted prompt pattern for Gemini.

Official Gemini TTS supports simple patterns:

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

The speaker labels in the prompt must match the speaker labels passed in `MultiSpeakerVoiceConfig`.

## Conversion Rule

APS is our internal production format. Gemini should not receive the raw APS or the full internal continuity packet as its main prompt.

APS compiles into a lean `tts_prompt` shaped like Gemini's advanced prompt examples:

1. `# AUDIO PROFILE`
2. `## THE SCENE`
3. `### DIRECTOR'S NOTES`
4. `### SAMPLE CONTEXT`
5. `#### TRANSCRIPT`

The render request may still store `chapter_context`, `continuity_packet`, `character_states`, and `character_voice_bibles` for audit/debugging, but the runner should prefer `tts_prompt` as the actual Gemini input when present.

The Gemini-facing prompt is the Actor prompt. Internal QA notes, stitch notes, cost notes, and continuity diagnostics must not be placed inside `tts_prompt`; store them as request metadata or manifest QA fields.

```json
{
  "output_path": "data/generated_tests/scene_001.wav",
  "tts_prompt": "# AUDIO PROFILE: Speaker1 (Narrator)\n...\n\n#### TRANSCRIPT\nSpeaker1: [serious] Exact words to speak.",
  "speaker_voices": {
    "Speaker1": "Kore"
  }
}
```

## Prompt Construction

Every Gemini `tts_prompt`, including single-speaker requests, should use the same structure:

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

Use Gemini audio tags only in the compiled Gemini prompt, never in APS `beat.text`. Good common tags include `[whispers]`, `[laughs]`, `[sighs]`, `[gasp]`, `[crying]`, `[trembling]`, `[panicked]`, `[sarcastic]`, `[serious]`, `[shouting]`, `[tired]`, `[curious]`, `[amazed]`, `[mischievously]`, and `[excitedly]`.

Use tags sparingly. Prefer no tag when the scene notes already carry the performance. A tag should mark a real vocal event or meaningful local shift, not restate every beat's emotion. Do not use `[tired]` for quiet resignation or private contentment; leave those lines untagged or use `[serious]` only if needed.

Audio tags are intensity-gated:

- Low sadness should not become `[crying]`.
- Dry wit, understatement, and irony should usually receive no tag; let the voice profile and delivery carry it.
- Shock should usually become `[trembling]` only when heightened; use `[gasp]` only for explicit gasp/sudden-startle moments.
- Anger should not become `[shouting]` unless intensity is very high.

Characters may define `tag_suppress` in APS to block tags that do not fit their stable performance. For example, a restrained narrator may suppress `[excitedly]` and `[laughs]`; Mr. Bennet may suppress `[sarcastic]` so dry wit does not turn into broad mockery.

Speaker labels in `#### TRANSCRIPT` must match `speaker_voices` exactly. Prefer neutral aliases like `Speaker1` and `Speaker2`; store the real character mapping separately in `speaker_aliases`.

## Cast Blocks

Repeat the relevant `# AUDIO PROFILE` block in every chunk. This is intentional because Gemini has no memory between API calls.

Profiles must be generated from APS character data:

- `display_name`
- `role`
- `provider_voice.gemini`
- `voice_bible` or `stable_voice`
- `do_not_change`
- `accent_profile`
- `golden_lines`
- approved voice notes, if present

Do not hand-maintain repeated cast blocks across a full book. The exporter owns this repetition.

## Accent Profiles

When APS includes `accent_profile`, compile it directly into the Audio Profile.

Use feature-based accent direction:

- Good: `South African English cadence; clipped final consonants; dry flattened vowels; direct practical rhythm. Avoid polished British diction, Russian/Eastern European consonants, Australian or Cockney drift, and theatrical villain delivery.`
- Weak: `South African accent.`

Accent labels alone are not reliable enough. The Actor needs audible mechanics and negative constraints.

## Chunk Splitting

Gemini multi-speaker TTS supports up to 2 speaker labels per request. Two characters sharing the same `provider_voice` still count as two speaker labels if they are sent as separate speakers.

Split chunks by speaker-label count, not by voice-name count. A chunk may contain:

- Narrator only
- Narrator + one dialogue character
- Young Narrator + one dialogue character

A chunk must not contain Narrator + Young Narrator + another character. If a scene crosses from adult narration into child-self dialogue, split the chunk and store a stitch QA note outside `tts_prompt`.

## Continuity Rules

- Always use the same `provider_voice` for a character within a production unless the cast sheet explicitly changes it.
- Put stable voice traits in every job's direction.
- Put normalized local emotion and intensity in the beat direction.
- Put nuance in scene/moment context, `delivery`, and `beat_modifier`; do not use prose phrases as emotion tokens.
- Do not rely on Gemini remembering previous chunks.
- Repeat enough Audio Profile and Scene information in each chunk for a cold API call to perform correctly.
- Store stitch warnings, overlap context, and QA concerns in metadata, not inside the Gemini transcript.
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

Retry 500-class Gemini TTS failures. Gemini can occasionally return text tokens instead of audio tokens, causing transient server errors.

Sources:

- https://ai.google.dev/gemini-api/docs/speech-generation
