# Presence Production State

Presence production state is the provider-neutral layer between APS and any renderer or immersive audio system.

```text
book text -> clean markdown -> APS -> generated production jobs
```

APS remains the source of truth for exact spoken text and production intelligence. Presence-style data should be treated as generated job data, not the master truth.

See `docs/aster_production_architecture_note.md` for the current architecture decision.

## Export

```powershell
python3 -m src.aura.presence_exporter --aps practice\aps\expected\sample_scene.aps.json --output practice\aps\generated_presence_state.json
```

## Shape

```json
{
  "presence_version": "0.1",
  "source": {},
  "production_packet": {},
  "characters": {},
  "scenes": [
    {
      "scene_id": "scene_001",
      "scene_type": "suspense",
      "emotion": "fearful, quiet, tense",
      "intensity": 0.6,
      "pace": "slow",
      "ambience": {
        "ambience_id": "cellar",
        "loops": ["damp room tone", "distant floorboard creaks"],
        "level": "subtle"
      },
      "spatial_mix": {
        "narrator": "center",
        "mara": "slightly_left",
        "elias": "slightly_right",
        "ambience": "wide_background"
      },
      "segments": []
    }
  ]
}
```

## Segment Contract

Each segment is independently renderable:

- `text` is the exact spoken text.
- `kind` is `narration`, `dialogue`, or another APS beat type.
- `speaker` points to the character manifest.
- `performance` carries emotion, intensity, pace, and delivery.
- `audio` carries ambience, spatial position, and SFX cues.

This is the base for the Presence Engine. Renderer-specific exporters should read this or APS, but they should not own the whole-book production model.
