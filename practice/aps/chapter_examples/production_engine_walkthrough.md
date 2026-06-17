# Production Engine Walkthrough

This is a compact example of what one book chapter looks like after it passes through the production engine.

The important idea:

```text
raw chapter text
-> APS
-> Presence production state
-> renderer jobs
-> audio and immersive layers
```

## Step 1: Raw Chapter Text

The manuscript starts as ordinary prose:

```text
Chapter 4: The Lantern Room

Rain tapped against the high windows of the old observatory. Mara held the brass lantern close to her chest, watching its flame shiver each time the wind pressed under the door.

"You said this place was empty," Mara whispered.

Elias did not answer at once. He was staring at the dust on the floor, where a fresh line of footprints crossed the room and vanished behind the telescope.

"It was," he said.
```

At this point the text is not ready for audio. The engine still needs to know who is speaking, what should be spoken literally, what should become performance direction, and what immersive layers belong underneath.

## Step 2: APS

APS is the exact script plus production intelligence. It preserves the words to speak in `text` and moves direction into metadata.

```json
{
  "aps_version": "0.1",
  "book_id": "lantern_room_demo",
  "title": "The Lantern Room",
  "chapter_id": "chapter_004",
  "chapter_title": "The Lantern Room",
  "production_packet": {
    "the_scene": "A quiet suspense chapter inside an abandoned observatory during heavy rain.",
    "director_notes": [
      "Keep narration intimate, tense, and controlled.",
      "Dialogue should be quiet enough to feel unsafe.",
      "Do not read dialogue tags aloud when the spoken line can stand alone."
    ],
    "sample_context": "Literary mystery audiobook with rain, silence, and restrained fear."
  },
  "characters": {
    "narrator": {
      "display_name": "Narrator",
      "role": "narrator",
      "stable_voice": "clear, restrained, literary, observant",
      "provider_voice": {
        "gemini": "Kore",
        "resemble": "calm literary narrator with restrained suspense"
      },
      "do_not_change": ["clarity", "base tone"]
    },
    "mara": {
      "display_name": "Mara",
      "role": "main",
      "stable_voice": "young, guarded, alert, slightly breathy under pressure",
      "provider_voice": {
        "gemini": "Leda",
        "resemble": "young woman, tense and guarded, slightly breathy"
      },
      "do_not_change": ["age", "accent", "base tone"]
    },
    "elias": {
      "display_name": "Elias",
      "role": "main",
      "stable_voice": "older, calm, protective, controlled",
      "provider_voice": {
        "gemini": "Algenib",
        "resemble": "older man, calm and protective, controlled under fear"
      },
      "do_not_change": ["age", "accent", "base tone"]
    }
  },
  "scenes": [
    {
      "scene_id": "scene_001",
      "title": "The Observatory",
      "summary": "Mara and Elias discover fresh footprints in an abandoned observatory.",
      "setting": "old observatory, night, heavy rain, wind under the door",
      "mood": "tense, quiet, mysterious",
      "scene_context": "The characters believe the observatory is abandoned, but fresh footprints prove someone has been inside.",
      "director_notes": [
        "Let the rain create pressure without overpowering the dialogue.",
        "Mara should sound frightened but careful.",
        "Elias should sound calm until the final line, where worry slips through."
      ],
      "character_states": {
        "mara": {
          "base_voice_ref": "mara.stable_voice",
          "scene_voice_state": "same young, guarded, slightly breathy voice, but quieter and more frightened than usual",
          "do_not_recast": true
        },
        "elias": {
          "base_voice_ref": "elias.stable_voice",
          "scene_voice_state": "same older, calm, protective voice, with concern held under control",
          "do_not_recast": true
        }
      },
      "beats": [
        {
          "beat_id": "scene_001_beat_001",
          "kind": "narration",
          "speaker": "narrator",
          "text": "Rain tapped against the high windows of the old observatory. Mara held the brass lantern close to her chest, watching its flame shiver each time the wind pressed under the door.",
          "context": "Scene opening.",
          "performance": {
            "emotion": "quiet tension",
            "intensity": 0.45,
            "pacing": "slow",
            "delivery": "controlled literary suspense"
          }
        },
        {
          "beat_id": "scene_001_beat_002",
          "kind": "dialogue",
          "speaker": "mara",
          "text": "You said this place was empty",
          "context": "Mara whispers. The tag is not spoken.",
          "voice_state": {
            "base_voice_rule": "Keep Mara recognisably young, guarded, alert, and slightly breathy.",
            "temporary_change": "make her quieter, more frightened, and more careful because she is trying not to be heard",
            "do_not_change": ["age", "accent", "base tone"]
          },
          "performance": {
            "emotion": "fear",
            "intensity": 0.7,
            "pacing": "hushed",
            "delivery": "whispered, careful, accusing"
          }
        },
        {
          "beat_id": "scene_001_beat_003",
          "kind": "narration",
          "speaker": "narrator",
          "text": "Elias did not answer at once. He was staring at the dust on the floor, where a fresh line of footprints crossed the room and vanished behind the telescope.",
          "context": "The danger becomes visible.",
          "performance": {
            "emotion": "discovery",
            "intensity": 0.62,
            "pacing": "measured",
            "delivery": "precise, tightening suspense"
          }
        },
        {
          "beat_id": "scene_001_beat_004",
          "kind": "dialogue",
          "speaker": "elias",
          "text": "It was",
          "context": "Elias answers, realizing the room is no longer safe.",
          "voice_state": {
            "base_voice_rule": "Keep Elias recognisably older, calm, protective, and controlled.",
            "temporary_change": "let worry show through the calm without changing his core voice identity",
            "do_not_change": ["age", "accent", "base tone"]
          },
          "performance": {
            "emotion": "controlled alarm",
            "intensity": 0.68,
            "pacing": "brief",
            "delivery": "low, controlled, worried beneath calm"
          }
        }
      ]
    }
  ]
}
```

Evaluation checks:

- Dialogue tags like `Mara whispered` are not spoken.
- `whispered` becomes performance direction.
- Every spoken line is exact and isolated.
- Character voice mapping is stable and provider-aware.
- Character identity lives in `stable_voice`; temporary changes live in `character_states`, `voice_state`, and `performance`.

## Step 3: Presence Production State

Presence is the whole-chapter production state. It is not Gemini-specific or Resemble-specific. It can feed voice rendering, ambience, spatial audio, SFX, QA, and later companion features.

```json
{
  "presence_version": "0.1",
  "source": {
    "book_id": "lantern_room_demo",
    "chapter_id": "chapter_004",
    "chapter_title": "The Lantern Room"
  },
  "characters": {
    "mara": {
      "character_id": "mara",
      "name": "Mara",
      "stable_voice": "young, guarded, alert, slightly breathy under pressure",
      "provider_voice": {
        "gemini": "Leda",
        "resemble": "young woman, tense and guarded, slightly breathy"
      }
    },
    "elias": {
      "character_id": "elias",
      "name": "Elias",
      "stable_voice": "older, calm, protective, controlled",
      "provider_voice": {
        "gemini": "Algenib",
        "resemble": "older man, calm and protective, controlled under fear"
      }
    }
  },
  "scenes": [
    {
      "scene_id": "scene_001",
      "scene_type": "mystery",
      "emotion": "tense, quiet, mysterious",
      "intensity": 0.61,
      "pace": "slow",
      "scene_context_short": "Mara and Elias are inside an abandoned observatory at night. Rain is outside, and fresh footprints suggest someone else has entered.",
      "moment_contexts": [
        {
          "moment_id": "moment_001",
          "applies_to_segments": ["scene_001_segment_001", "scene_001_segment_002"],
          "description": "The scene begins in the observatory interior. Mara is close to the lantern, the room feels empty but unsafe, and her whispered question challenges Elias's earlier certainty."
        },
        {
          "moment_id": "moment_002",
          "applies_to_segments": ["scene_001_segment_003", "scene_001_segment_004"],
          "description": "The fresh footprints become visible in the dust. Elias now understands the observatory was entered recently, so his calm voice has a thin layer of alarm underneath."
        }
      ],
      "ambience": {
        "ambience_id": "rain",
        "perspective": "inside listening to exterior weather",
        "loops": ["muffled exterior rainfall", "subtle wind through door gap"],
        "level": "subtle",
        "notes": "Rain is outside the observatory, filtered through glass, stone, and distance. Keep below dialogue."
      },
      "acoustic_space": {
        "listener_position": "inside_old_observatory",
        "room_size": "large_tall_room",
        "surface_character": "stone, old wood, glass",
        "interior_reverb": "soft tall-room reflections",
        "perspective": "close interior dialogue with exterior weather pressure"
      },
      "environment_sources": {
        "rain_outside_windows": {
          "sound": "rainfall",
          "location": "outside",
          "position": "wide_above_and_behind_windows",
          "distance": "medium_far",
          "occlusion": 0.72,
          "filter": "low-pass, softened transients",
          "duck_under_dialogue": true
        },
        "wind_under_door": {
          "sound": "thin wind through door gap",
          "location": "threshold",
          "position": "low_front_right",
          "distance": "near",
          "occlusion": 0.35,
          "filter": "narrow, airy",
          "duck_under_dialogue": true
        }
      },
      "spatial_mix": {
        "narrator": "center",
        "mara": "slightly_left",
        "elias": "slightly_right",
        "ambience": "wide_background"
      },
      "segments": [
        {
          "segment_id": "scene_001_segment_001",
          "kind": "narration",
          "speaker": "narrator",
          "moment_context_id": "moment_001",
          "render_context": "Opening beat inside the observatory. Establish quiet suspense, exterior rain pressure, lantern closeness, and the sense that the room may not be empty.",
          "text": "Rain tapped against the high windows of the old observatory. Mara held the brass lantern close to her chest, watching its flame shiver each time the wind pressed under the door.",
          "performance": {
            "emotion": "quiet tension",
            "intensity": 0.45,
            "pace": "slow",
            "delivery": "controlled literary suspense"
          },
          "audio": {
            "spatial_position": "center",
            "sfx_cues": ["faint window rain", "small lantern movement"]
          }
        },
        {
          "segment_id": "scene_001_segment_002",
          "kind": "dialogue",
          "speaker": "mara",
          "moment_context_id": "moment_001",
          "render_context": "Mara whispers from fear and suspicion. She is trying not to be heard, but she is also accusing Elias of being wrong.",
          "text": "You said this place was empty",
          "performance": {
            "emotion": "fear",
            "intensity": 0.7,
            "pace": "hushed",
            "delivery": "whispered, careful, accusing"
          },
          "audio": {
            "spatial_position": "slightly_left",
            "sfx_cues": []
          }
        },
        {
          "segment_id": "scene_001_segment_004",
          "kind": "dialogue",
          "speaker": "elias",
          "moment_context_id": "moment_002",
          "render_context": "Elias has seen the footprints. His answer is short because he realizes the room is not safe, but he is trying not to frighten Mara further.",
          "text": "It was",
          "performance": {
            "emotion": "controlled alarm",
            "intensity": 0.68,
            "pace": "brief",
            "delivery": "low, controlled, worried beneath calm"
          },
          "audio": {
            "spatial_position": "slightly_right",
            "sfx_cues": ["small pause before line"]
          }
        }
      ]
    }
  ]
}
```

Evaluation checks:

- This is the base production object for the chapter.
- Segments can be rendered independently.
- Significant segment changes include a short `moment_context` so renderers know where they are in the scene.
- Ambience and spatial metadata are attached without polluting spoken text.
- SFX cues are separate from dialogue.

## Step 4: Gemini Render Job

Gemini receives a smaller renderer-specific job. It does not need the entire Presence state, only the context, voices, and transcript for a legal chunk.

```json
{
  "output_file": "audio/chapter_004/chunk_001.wav",
  "model": "gemini-2.5-pro-preview-tts",
  "chapter_context": "## CHAPTER CONTEXT\nA quiet suspense chapter inside an abandoned observatory during heavy rain.\n\n## THE SCENE\nThe characters believe the observatory is abandoned, but fresh footprints prove someone has been inside.\n\n## CURRENT MOMENT\nThe scene begins in the observatory interior. Mara is close to the lantern, the room feels empty but unsafe, and her whispered question challenges Elias's earlier certainty. Keep the rain outside and muffled through the windows.\n\n## DIRECTOR'S NOTES\n- Keep narration intimate, tense, and controlled.\n- Mara should sound frightened but careful.\n- Elias should sound calm until the final line, where worry slips through.\n\n## CONTINUITY PACKET\nThis is the opening render chunk for chapter_004. Preserve the rain-soaked suspense tone.",
  "speaker_voices": {
    "Narrator": "Kore",
    "Mara": "Leda"
  },
  "transcript": "TTS the following conversation exactly as written:\n\nNarrator: [quiet tension, slow, controlled literary suspense] Rain tapped against the high windows of the old observatory. Mara held the brass lantern close to her chest, watching its flame shiver each time the wind pressed under the door.\n\nMara: [fear, hushed, whispered, careful, accusing] You said this place was empty"
}
```

Evaluation checks:

- Gemini gets only legal speaker count chunks.
- The transcript is exact.
- Performance tags guide delivery but are generated outside APS source text.
- Continuity is repeated because renderers should not rely on memory.

## Step 5: 3D/4D Ambience Direction

For now, ignore provider-specific formats like DramaBox. The more important production idea is that ambience should have physical perspective.

If rain is outside and the characters are inside, we should not simply play clear rain loudly under the scene. The script should describe the listener position, the sound source position, and the material between them.

```json
{
  "environment_sources": [
    {
      "source_id": "rain_outside_windows",
      "kind": "ambience",
      "sound": "rainfall",
      "diegetic": true,
      "listener_position": "inside_old_observatory",
      "source_location": "outside",
      "spatial_position": "wide_above_and_behind_windows",
      "distance": "medium_far",
      "occlusion": {
        "barrier": "old glass windows and stone walls",
        "amount": 0.72,
        "filter": "low-pass, softened transients"
      },
      "room_response": {
        "interior_reflection": "soft tall-room reflections",
        "exterior_directness": "reduced"
      },
      "mix": {
        "level": "subtle",
        "width": "wide",
        "movement": "slow random window-side shimmer",
        "duck_under_dialogue": true
      }
    }
  ]
}
```

Evaluation checks:

- Is the sound source inside or outside?
- Where is the listener positioned?
- What material blocks or filters the sound?
- How far away is the sound?
- Should it duck under dialogue?
- Does it feel like space, not just a loop?

## Step 6: Final Production Timeline

The final chapter timeline can point at rendered audio, ambience beds, SFX, and stitch metadata.

```json
{
  "chapter_id": "chapter_004",
  "timeline": [
    {
      "segment_id": "scene_001_segment_001",
      "voice_audio": "audio/chapter_004/segment_001.wav",
      "ambience": [
        {
          "file": "ambience/rain_exterior_muffled_loop.wav",
          "position": "wide_above_and_behind_windows",
          "occlusion": 0.72,
          "level": "subtle"
        },
        {
          "file": "ambience/wind_door_gap_thin.wav",
          "position": "low_front_right",
          "occlusion": 0.35,
          "level": "very_subtle"
        }
      ],
      "spatial_position": "center",
      "sfx": ["sfx/window_rain_soft.wav", "sfx/lantern_small_shift.wav"]
    },
    {
      "segment_id": "scene_001_segment_002",
      "voice_audio": "audio/chapter_004/segment_002.wav",
      "ambience": [
        {
          "file": "ambience/rain_exterior_muffled_loop.wav",
          "position": "wide_above_and_behind_windows",
          "occlusion": 0.72,
          "level": "ducked_under_dialogue"
        }
      ],
      "spatial_position": "slightly_left",
      "sfx": []
    },
    {
      "segment_id": "scene_001_segment_004",
      "voice_audio": "audio/chapter_004/segment_004.wav",
      "ambience": [
        {
          "file": "ambience/rain_exterior_muffled_loop.wav",
          "position": "wide_above_and_behind_windows",
          "occlusion": 0.72,
          "level": "ducked_under_dialogue"
        }
      ],
      "spatial_position": "slightly_right",
      "sfx": ["sfx/short_silence_tension.wav"]
    }
  ],
  "qa": {
    "spoken_text_exact": true,
    "dialogue_tags_removed_when_safe": true,
    "voice_consistency_checked": false,
    "stitch_review_status": "pending"
  }
}
```

Evaluation checks:

- Voice, ambience, spatial, and SFX layers can be mixed separately.
- QA can check exact text and production quality.
- Bad chunks can be rerendered without rebuilding the whole chapter.

## Context Packet Rule

The renderer should not receive isolated lines with only emotion tags. At meaningful changes in the scene, the production engine should insert a short current-moment context paragraph.

This is not spoken. It tells the audio model where we are dramatically, physically, and emotionally.

```json
{
  "render_context_packet": {
    "applies_to_segments": ["scene_001_segment_003", "scene_001_segment_004"],
    "current_moment": "The fresh footprints become visible in the dust. Elias now understands the observatory was entered recently, so his calm voice has a thin layer of alarm underneath.",
    "physical_context": "Mara and Elias are still inside the observatory. Rain remains outside, muffled through glass and stone.",
    "performance_context": "Do not restart the scene. Continue from quiet suspicion into controlled alarm.",
    "not_spoken": true
  }
}
```

When to generate a new context packet:

- new location
- new speaker dynamic
- emotional turn
- reveal or discovery
- action shift
- time jump
- ambience/acoustic change
- renderer chunk boundary

For scale, these packets should be generated by the Narrative Analysis Engine first, then reviewed only when confidence is low or narrative importance is high.

## What To Judge

Use this checklist when evaluating whether the production engine output is good enough:

- Does every `text` field contain only words that should be spoken?
- Are dialogue tags converted into performance metadata when safe?
- Are character IDs stable across the chapter?
- Are voice notes specific enough for repeatable casting?
- Does each scene have emotion, intensity, pace, ambience, and spatial data?
- Does each significant scene shift include a short current-moment context paragraph?
- Does ambience include listener position, source location, occlusion, and filtering?
- Can a renderer consume chunks without needing hidden memory?
- Can audio/SFX/spatial systems use the same chapter state?
- Can QA trace every rendered line back to a source beat?
