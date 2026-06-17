# Gemini TTS Actor

Gemini is Aster's first premium commercial Actor. It is used to validate the quality bar while Aura builds its Director, Casting, Vault, and production workflow.

## Setup

Install the SDK:

```powershell
pip install google-genai
```

Set an API key:

```powershell
$env:GEMINI_API_KEY="your-key"
```

Render a single-speaker request:

```powershell
python -m src.aura.gemini_tts_runner --request data/synthesis/gemini_hello_world.example.json
```

Render a two-speaker request:

```powershell
python -m src.aura.gemini_tts_runner --request data/synthesis/gemini_dialogue.example.json
```

## Request Shape

Single speaker:

```json
{
  "text": "Line to speak.",
  "output_path": "data/generated_tests/out.wav",
  "performance": {
    "style_prompt": "warm cinematic audiobook narration"
  },
  "voice": {
    "voice_id": "gemini_kore",
    "provider_voice": "Kore"
  }
}
```

Multi-speaker:

```json
{
  "output_path": "data/generated_tests/dialogue.wav",
  "performance": {
    "direction": "Make Mara afraid and Elias calm."
  },
  "speakers": [
    { "speaker": "Mara", "provider_voice": "Leda" },
    { "speaker": "Elias", "provider_voice": "Algenib" }
  ],
  "turns": [
    { "speaker": "Mara", "text": "Please, stop." },
    { "speaker": "Elias", "text": "Stay behind me." }
  ]
}
```

## Voice Names

Gemini TTS currently lists 30 prebuilt voices, including `Kore`, `Puck`, `Leda`, `Enceladus`, `Algenib`, `Sulafat`, and others. Use AI Studio's voice library to audition them before assigning cast voices.

## Notes

Gemini TTS is text-in, audio-out and does not support streaming. The docs list a 32k-token context limit for a TTS session, so Aster should chunk books by scene or chapter segment and pre-render audio to storage.

Sources:

- https://ai.google.dev/gemini-api/docs/speech-generation
- https://ai.google.dev/gemini-api/docs/pricing
