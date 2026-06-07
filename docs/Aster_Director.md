# Aster Director

The Director turns manuscript text into a screenplay-like performance plan.

It does not replace the Actor. It prepares the work order the Actor needs.

```text
Manuscript -> Director -> PerformancePlan -> Casting -> Gemini TTS -> WAV chunks
```

## Why AI Is Still Needed

Aster can do basic parsing without AI, but true directing needs an LLM:

- identify recurring characters,
- resolve aliases and pronouns,
- understand scene context,
- infer emotion and subtext,
- decide pacing and delivery,
- summarise memory for future chunks.

Aster's job is to constrain that AI with schemas, validation, memory, and renderer-specific prompts.

## Local Fallback

The current local Director is a fallback parser. It can split prose and quoted dialogue into beats:

```powershell
python -m src.aura.director --input data/manuscripts/sample_scene.txt --output data/plans/sample_scene.performance.json --book-id hollow_stair --title "The Hollow Stair"
```

This produces a JSON `PerformancePlan`. Later, the Gemini Director will fill the same schema with better character detection and performance choices.

## Performance Plan Shape

```json
{
  "book_id": "hollow_stair",
  "title": "The Hollow Stair",
  "characters": {
    "Narrator": {"role": "narrator", "notes": "default narration voice"},
    "Mara": {"role": "character", "notes": "needs casting review"}
  },
  "scenes": [
    {
      "scene_id": "scene_001",
      "summary": "Mara hides in the cellar...",
      "beats": [
        {
          "kind": "dialogue",
          "speaker": "Mara",
          "text": "Please, just stop...",
          "performance": {
            "emotion": "fear",
            "intensity": 0.75,
            "pacing": "breathless",
            "delivery": "quiet panic"
          }
        }
      ]
    }
  ]
}
```

## Next Step

Add `casting.py` so each beat can resolve:

```text
speaker -> cast member -> Gemini provider voice -> render request
```
