# Gemini APS Test: Pride and Prejudice, Netherfield Letter Scene

This folder is a Gemini-only APS practice run for a public-domain excerpt from Jane Austen's *Pride and Prejudice*.

Files:

- `source.md`: source passage used for the test.
- `aps.json`: Aster Performance Script with chapter context, scene context, cast, and beats.
- `gemini_request.json`: canonical Gemini artifact using `chapter_context`, `transcript`, and `speaker_voices`.
- `render_split_notes.md`: practical notes for splitting this into legal Gemini render jobs.

Important Gemini constraint:

Gemini multi-speaker TTS supports up to 2 speakers per request. This scene includes Narrator, Miss Bingley, Mr. Darcy, Mr. Bingley, and Elizabeth, so it must be split before final rendering.

