# Cast Bible

The cast bible is the book-level source of truth for character voice identity.

APS files are chapter-level production plans. A Gemini Director may generate a slightly different voice description from chapter to chapter. The cast bible prevents that drift by locking the reusable identity fields for each character.

This Markdown file is the guide. The actual cast bible is JSON.

## Location

Recommended production location:

```text
Production/book_001/cast/cast_bible.json
```

## Shape

```json
{
  "cast_bible_version": "0.1",
  "book_id": "book_001",
  "title": "Book Title",
  "source_chapter_id": "chapter_001",
  "version_history": [
    {
      "version": "0.1",
      "date": "2026-06-18",
      "changed_by": "human",
      "change": "Initial extraction from chapter_001",
      "affected_characters": ["opal_miner"]
    }
  ],
  "enforcement": {
    "override_from_cast_bible": [
      "provider_voice",
      "stable_voice",
      "voice_bible",
      "do_not_change",
      "accent_profile",
      "energy_profile",
      "tag_suppress",
      "approved_reference_note",
      "approved_reference_render"
    ],
    "preserve_from_chapter_aps": [
      "display_name",
      "role",
      "scene-specific performance",
      "beat performance metadata"
    ],
    "manual_recast_required_for": [
      "provider_voice",
      "stable_voice",
      "voice_bible",
      "accent_profile",
      "energy_profile"
    ]
  },
  "rules": [
    "Use these cast entries as the source of truth for voice identity across chapters."
  ],
  "characters": {
    "opal_miner": {
      "display_name": "Opal Miner",
      "role": "supporting_character",
      "stable_voice": "stable identity description",
      "provider_voice": {
        "gemini": "Algenib"
      },
      "do_not_change": [
        "South African English cadence",
        "clipped consonants",
        "dry flattened vowels",
        "blunt practical rhythm",
        "gravelly texture",
        "same Algenib base voice across chunks"
      ],
      "voice_bible": "long-range voice identity anchor",
      "golden_lines": ["Short source line."],
      "approved_reference_note": "human-approved render note",
      "approved_reference_render": {
        "chapter_id": "chapter_001",
        "chunk_id": "chunk_004",
        "render_date": "2026-06-18",
        "notes": "Best approved render for this character."
      },
      "accent_profile": {
        "label": "South African English",
        "features": [
          "clipped final consonants",
          "dry flattened vowels",
          "direct practical rhythm",
          "blunt phrasing"
        ],
        "avoid": [
          "polished British diction",
          "Russian or Eastern European consonants",
          "Australian or Cockney drift",
          "theatrical villain delivery"
        ]
      },
      "energy_profile": {
        "baseline_intensity": 0.55,
        "entry_instruction": "Enter as the same already-established character, not as a fresh take.",
        "do_not_do": [
          "Do not reset energy at chunk boundaries.",
          "Do not open with a newly invented voice."
        ]
      },
      "tag_suppress": ["[excitedly]"],
      "casting_lock": "stable"
    }
  }
}
```

## Commands

Extract a cast bible from an approved APS:

```powershell
python -m src.aura.cast_bible extract `
  --aps Production\book_001\chapter_001\aps_v3_clean.json `
  --output Production\book_001\cast\cast_bible.json
```

Apply a cast bible to a new APS:

```powershell
python -m src.aura.cast_bible apply `
  --aps Production\book_001\chapter_002\aps.json `
  --cast-bible Production\book_001\cast\cast_bible.json `
  --output Production\book_001\chapter_002\aps_cast_locked.json
```

Export Gemini chunks with the cast bible applied:

```powershell
python -m src.aura.gemini_chapter_exporter `
  --aps Production\book_001\chapter_002\aps.json `
  --cast-bible Production\book_001\cast\cast_bible.json `
  --output-dir Production\book_001\chapter_002\exported_gemini `
  --max-chunk-words 230
```

## Rules

- The cast bible overrides chapter APS fields for voice identity.
- The `enforcement` block is the human-readable contract for what the `apply` command does.
- Scene emotion may change; base vocal identity must not.
- Do not recast `provider_voice`, `stable_voice`, `voice_bible`, `accent_profile`, or `do_not_change` without human approval.
- Use `version_history` whenever a human changes a voice, accent, energy profile, or approved reference.
- Use `energy_profile` to lock baseline performance energy. This does not replace scene emotion; it prevents chunk-boundary and chapter-boundary reset.
- Keep golden lines short and representative.
- Use `approved_reference_note` to capture what worked in listening tests.
- Use `approved_reference_render` to point future QA back to the render that proved the voice works.
