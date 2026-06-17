# APS Production Lessons

These are the recurring APS mistakes we have already found. Treat this as the checklist before generating renderer jobs.

## Source Trace

Every beat must map back to the manuscript with exact source offsets.

- Include `source_span.start_char` and `source_span.end_char`.
- Include `source_trace.source_start`, `source_trace.source_end`, and `source_trace.source_text`.
- If a rendered line only uses part of the source paragraph, include `spoken_text_span`.
- If text is removed or converted into metadata, include `removed_text_spans`.

Why it matters: if a creator disputes a line, we need to prove exactly what changed and why.

## Speakable Text

Do not overload one text field.

- `source_spoken_text` is what appeared inside the manuscript dialogue or narration.
- `render_text` is what TTS should say.
- `text` should match `render_text` for speakable beats.

Allowed cleanup:

- strip quotation marks
- remove a trailing comma from dialogue before attribution

Do not remove:

- question marks
- exclamation marks
- ellipses
- dashes

## Render Grouping

Do not split every paragraph into a render decision.

Adjacent narration with the same moment, format, and emotional phase should be grouped into one renderable block.

Use:

- `render_group: narrative_block`
- `internal_source_spans`

This lets a block like:

- `The train was late.`
- `Again.`
- `Still 8:41.`
- `Still raining.`
- `Still no train.`

render as one natural narration unit while still preserving exact source trace for every paragraph inside the block.

Avoiding over-segmentation reduces:

- render cost
- latency
- review noise
- unnatural pacing

## Dialogue Tags

Do not blindly remove dialogue tags.

Safe automatic removals:

- `said`
- `asked`

Safe conversion to performance metadata, but still track it:

- `whispered`
- `shouted`
- `muttered`

Review required when:

- text is removed beyond `said` or `asked`
- action is embedded in the tag
- the speaker is inferred from context
- a dialogue direction is separated from the spoken line
- multiple speakers appear in one paragraph

Examples that should require review:

- `Mara lied`
- `Mara said, pointing at the door`
- `Then, quietly, he said:`

## Speaker Attribution

The APS must say how a speaker was resolved.

Use:

- `narrator`
- `explicit_tag`
- `inferred_context`
- `dialogue_direction`

Any `inferred_context` speaker should default to `requires_review: true`.

This is especially important for courtroom scenes, group dialogue, jurors, reporters, crowd voices, and unidentified voices.

Do not treat deterministic screen labels as inferred speakers.

For example:

```text
MAYA:
You still coming?
```

should become a deterministic screen-message conversion, not a risky edit.

Use:

- `speaker_attribution: explicit_screen_label`
- `transformation_type: screen_label_conversion`
- `format_type: text_message`

This should auto-approve unless something else is risky.

## Review Flags

Review must be automatic, not polite.

Set `review.requires_review: true` when:

- `confidence < 0.8`
- speaker is inferred from context
- text is removed beyond `said` or `asked`
- dialogue direction is separated from dialogue
- multiple speakers appear in one paragraph
- source trace span differs from segment span

Always include `review.risk_reason` when review is required.

Do not require review for deterministic structural conversions:

- `screen_label_conversion`
- `email_header_conversion`

These are predictable format conversions, not creative edits.

Modern fiction may contain thousands of texts, emails, chat logs, transcripts, and headings. Marking all of them for review would make the system unusable.

## Delivery Variety

Avoid samey production direction.

Every beat needs a controlled `delivery_archetype`.

Allowed values:

- `storm_setup`
- `quiet_reveal`
- `command`
- `disbelief`
- `threat`
- `urgency`
- `final_dread`

Do not use the same `delivery_archetype` more than 3 beats in a row unless `allow_repeated_archetype: true`.

## Emotional Arc

Do not rely only on per-beat emotions.

Each scene should expose its larger emotional movement.

Example:

```json
{
  "scene_arc": {
    "start": "fatigue",
    "early": "humour",
    "middle": "suspicion_to_dread",
    "flashback": "wonder",
    "late": "horror_to_panic",
    "end": "absurdity"
  }
}
```

Beats can then inherit an `arc_phase`, which keeps local direction aligned with the chapter's real progression.

This prevents long stretches of repeated emotions like `rainy commuter fatigue`.

## Format Types

Every beat should say what kind of text structure it came from.

Use `format_type` values such as:

- `prose`
- `dialogue`
- `text_message`
- `email`
- `email_header`
- `flashback`
- `memory_transition`
- `announcement_system`
- `dialogue_direction`
- `screen_header`

Format type affects:

- narration style
- whether a label is speakable
- review rules
- grouping rules
- renderer chunking
- sound design treatment

## Timing

Every beat needs timing placeholders.

Required:

- `timing.pause_before_ms`
- `timing.pause_after_ms`
- `timing.transition_type`
- `estimated_duration_ms`
- `rendered_duration_ms`
- `render_attempts`

These let the timeline builder work before actual audio exists.

## Sound Design

Do not bury sound design inside TTS.

APS can describe:

- acoustic space
- environment sources
- ambience perspective
- SFX intent

But actual ambience/SFX jobs should be generated separately from APS.

TTS jobs should receive voice context and transcript only.

## Renderer Constraints

Gemini render jobs need chunk rules.

Required:

- `renderer_constraints.max_speakers`
- `renderer_constraints.chunk_strategy`
- `renderer_constraints.repeat_context_at_chunk_boundary`

Current Gemini rule:

- `max_speakers: 2`

Complex dialogue scenes must split by moment and speaker limit.

## Voice Profiles

APS should be provider-neutral.

Do not store provider voice IDs in APS.

Prefer:

```json
{
  "voice_profile": {
    "age": "elderly",
    "tone": "calm, knowing",
    "energy": "low_until_danger",
    "style": "quiet authority"
  }
}
```

Renderer jobs can later map this profile to:

- Gemini
- ElevenLabs
- OpenAI
- local voices

APS is the production truth. Provider-specific voice IDs belong in render jobs or voice-mapping tables.

## Validation Gate

Before generating TTS jobs, run the APS validator.

```bash
python3 -m src.aura.aps_validator path/to/chapter.aps.json
```

If validation fails, the chapter must not render.

The production engine can be imperfect. The validator must be strict.
