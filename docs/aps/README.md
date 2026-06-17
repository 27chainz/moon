# Aster Performance Script

The Aster Performance Script, or APS, is the production format between the manuscript intelligence layer and the audio renderer.

```text
book text -> Director -> APS -> Presence production state -> Actor-specific prompt -> audio
```

APS has one job: preserve the exact words that should be spoken while attaching the performance information an Actor needs.

## Core Rule

Never mix spoken text and stage direction.

```text
spoken text = exact manuscript words
performance = metadata outside the spoken text
```

This lets the same APS render through different Actors:

- Gemini TTS
- Resemble DramaBox
- Kokoro
- CosyVoice
- future Aster Actor

It also lets non-voice layers read the same chapter:

- ambience
- SFX cues
- spatial placement
- chapter QA

## Folder Map

```text
docs/aps/
  APS_SCHEMA.md
  rules/
    gemini_actor.md
    resemble_dramabox.md

practice/aps/
  inputs/
  expected/
```

Use `practice/aps` to test whether the rules are good enough before running full books.
