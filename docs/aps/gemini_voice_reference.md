# Gemini TTS Voice Reference

Gemini TTS supports these prebuilt voice names in the `voice_name` field.

Use these as the base voice or "instrument" for a character. Aster then layers the character's `voice_bible`, accent traits, scene direction, and performance tags on top.

| Voice | Base Quality |
| --- | --- |
| Zephyr | Bright |
| Puck | Upbeat |
| Charon | Informative |
| Kore | Firm |
| Fenrir | Excitable |
| Leda | Youthful |
| Orus | Firm |
| Aoede | Breezy |
| Callirrhoe | Easy-going |
| Autonoe | Bright |
| Enceladus | Breathy |
| Iapetus | Clear |
| Umbriel | Easy-going |
| Algieba | Smooth |
| Despina | Smooth |
| Erinome | Clear |
| Algenib | Gravelly |
| Rasalgethi | Informative |
| Laomedeia | Upbeat |
| Achernar | Soft |
| Alnilam | Firm |
| Schedar | Even |
| Gacrux | Mature |
| Pulcherrima | Forward |
| Achird | Friendly |
| Zubenelgenubi | Casual |
| Vindemiatrix | Gentle |
| Sadachbia | Lively |
| Sadaltager | Knowledgeable |
| Sulafat | Warm |

## Selection Notes

- Pick the base voice for age, weight, and texture first.
- Use prompt direction for performance, not to fight the base voice.
- For accents, describe concrete speech traits and avoid-list failures.
- Minor characters may share a base voice if they never appear in the same scene and have distinct `voice_bible` descriptions.
- Once a character voice works, lock the base voice and voice profile in the character bible.

## Current Test Finding

For the Opal Miner test, `Algenib` with a lean prompt performed better than heavily directing `Fenrir`.

Useful profile:

```text
Gruff adult man with clipped consonants, dry vowels, direct rhythm, and practical phrasing. Suggest South African English while avoiding Russian, Eastern European, Australian, Cockney, or theatrical villain tones.
```
