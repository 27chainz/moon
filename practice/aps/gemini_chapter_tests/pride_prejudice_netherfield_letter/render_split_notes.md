# Render Split Notes

This passage has five voices:

- Narrator
- Miss Bingley
- Mr. Darcy
- Mr. Bingley
- Elizabeth

Gemini multi-speaker TTS supports up to two speakers per request, so the production pipeline should split this chapter section into jobs.

Recommended first-pass jobs:

1. `job_001_narrator_setup`
   - Speaker: Narrator
   - Model: single-speaker Gemini TTS
   - Content: opening narration through Elizabeth observing Darcy and Miss Bingley.

2. `job_002_miss_bingley_darcy_letter`
   - Speakers: Miss Bingley, Mr. Darcy
   - Model: multi-speaker Gemini TTS
   - Content: Miss Bingley flattering Darcy while he writes.

3. `job_003_bingley_darcy_caroline`
   - Speakers: Mr. Bingley, Mr. Darcy
   - Model: multi-speaker Gemini TTS
   - Content: Bingley teasing Darcy about writing.
   - Miss Bingley's inserted line should be split into a separate adjacent job or restructured carefully.

4. `job_004_elizabeth_darcy_bingley_argument`
   - Split into alternating two-speaker jobs:
     - Elizabeth + Darcy
     - Elizabeth + Bingley
     - Darcy + Bingley

Production warning:

Do not send all five speakers in one Gemini request. The canonical artifact can represent a chapter, but render jobs must obey the provider limit.

