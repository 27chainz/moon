---
name: aps-gemini
description: Convert Aster Performance Script JSON into Gemini TTS render requests. Use when preparing audiobook scenes, narration beats, dialogue beats, cast voices, scene memory, or Gemini multi-speaker jobs from APS.
---

# APS Gemini

Use this repo-local skill when converting APS into Gemini Actor requests.

Read:

- `docs/aps/APS_SCHEMA.md`
- `docs/aps/rules/gemini_actor.md`

Process:

1. Load APS JSON.
2. Resolve each `speaker` through the cast sheet or `characters`.
3. Keep stable voice traits in the Gemini direction.
4. Keep exact beat text unchanged.
5. For one speaker, produce a single-speaker Gemini request.
6. For two speakers, produce a Gemini multi-speaker request.
7. For more than two speakers, split the scene into smaller render jobs.
8. Store output paths per beat or scene.

Do not rely on Gemini remembering previous chunks. Include the relevant continuity packet in every request.

