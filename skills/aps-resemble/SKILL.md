---
name: aps-resemble
description: Convert Aster Performance Script JSON into Resemble DramaBox prompts where quoted text is spoken literally and unquoted text is stage direction. Use when preparing DramaBox render prompts from APS beats, character voice descriptions, and performance metadata.
---

# APS Resemble

Use this repo-local skill when converting APS into Resemble DramaBox prompts.

Read:

- `docs/aps/APS_SCHEMA.md`
- `docs/aps/rules/resemble_dramabox.md`

Process:

1. Load APS JSON.
2. Resolve the beat speaker to stable character voice notes.
3. Put speaker description, scene context, and performance cues outside quotes.
4. Put only exact spoken text inside quotes.
5. Do not put words like `Sigh`, `Gasp`, or `Cough` inside quotes.
6. Use short stage directions.

Template:

```text
<speaker description>. <scene/performance direction>, "<exact beat text>"
```

