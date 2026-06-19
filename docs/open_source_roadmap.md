# Aster Open-Source Integration Roadmap

This document outlines the strategic open-source models and libraries slated for integration into the Aster production pipeline. These tools represent the transition from a powerful TTS wrapper into an elite, automated, end-to-end editorial audio studio.

## Phase 1: The Flawless QA Loop (Zero-Defect Rendering)

Before accelerating top-of-funnel generation, we must guarantee that output from the Gemini TTS engine meets strict, objective quality standards without requiring human listening time for every chunk.

### 1. Voice Identity Guard: `resemblyzer`
* **The Problem:** Gemini TTS can occasionally "drift" and change a character's voice between chunks, despite prompt instructions. Human QA is currently required to catch this.
* **The Solution:** [Resemblyzer](https://github.com/resemble-ai/resemblyzer) extracts a 256-dimensional mathematical embedding of a voice from raw audio.
* **The Aster Vision:** Every rendered chunk is automatically compared against the character's `approved_reference_render` in the Cast Bible. If the cosine similarity drops below a set threshold, the chunk is automatically flagged for drift and re-rendered.

### 2. Hallucination & Accuracy Guard: `whisper`
* **The Problem:** TTS engines can occasionally hallucinate words, skip dense sentences, or mispronounce key terms, rendering a chunk unusable.
* **The Solution:** [OpenAI's Whisper](https://github.com/openai/whisper) is a highly robust, open-source speech-to-text model.
* **The Aster Vision:** Whisper automatically transcribes every generated audio chunk. A diff is run against the expected `render_text` in the APS. Any deviation (missed words, hallucinations) immediately fails the chunk's QA check, forcing a re-render.

### 3. Robotic Artifact Guard: `torchaudio-squim`
* **The Problem:** Sometimes an engine outputs audio with the right words and voice, but suffers from metallic artifacts, static, or sounds "robotic."
* **The Solution:** [Torchaudio SQUIM](https://pytorch.org/audio/main/tutorials/squim_tutorial.html) (Speech Quality and Intelligibility Measures) provides objective scoring of audio quality (predicting human MOS scores) without needing a clean reference track.
* **The Aster Vision:** SQUIM acts as the final gatekeeper in the automated QA loop. Any chunk scoring below an "editorial grade" threshold (e.g., 4.0/5.0) is rejected as a corrupted render.

### 4. Emotion & Performance Verification: `praat-parselmouth` / `wav2vec2-emotion`
* **The Problem:** We can verify the *words* (Whisper) and the *voice* (Resemblyzer), but how do we know if the *acting* is right? If the AI Director requested a high-intensity performance, did Gemini actually deliver it?
* **The Solution:** [Praat-Parselmouth](https://github.com/YannickJadoul/Parselmouth) is a Python interface for the Praat software, the industry standard for phonetic analysis. 
* **The Aster Vision:** Instead of trying to classify "furious" with a black-box emotion model, Aster directly measures pitch variance, speaking rate, and energy contour using Parselmouth. If the measured intensity doesn't match the APS `intensity` value, it automatically flags for a "bad take."

### 5. Multi-Speaker Drift Catching: `pyannote-audio`
* **The Problem:** A chunk is generated for a single character, but Gemini hallucinates and voice-swaps mid-sentence. Resemblyzer might miss this if the *average* chunk embedding still looks close enough to the reference.
* **The Solution:** [pyannote.audio](https://github.com/pyannote/pyannote-audio) is an open-source neural speaker diarization toolkit.
* **The Aster Vision:** This is a zero-cost, high-value QA check. If Aster renders a 1-speaker chunk, but `pyannote` detects 2 distinct speaker clusters within the audio, Aster knows immediately that a mid-chunk voice swap occurred and instantly trashes the file.

### 6. Pronunciation Guard: `phonemizer` / `MFA`
* **The Problem:** Fantasy/Sci-Fi character names (e.g., "Daenerys", "Kelsier") are frequently mispronounced by TTS engines, ruining immersion.
* **The Solution:** [Montreal Forced Aligner (MFA)](https://github.com/MontrealCorpusTools/Montreal-Forced-Aligner) or `phonemizer`.
* **The Aster Vision:** The Cast Bible holds an IPA (International Phonetic Alphabet) pronunciation guide for custom nouns. Aster's QA loop extracts the phonetics of the rendered chunk and fails the render if a golden noun is pronounced incorrectly.

---

## Phase 2: Top-of-Funnel Automation (The "Zero-to-One" Pipeline)

Once the rendering pipeline is bulletproof, the focus shifts to removing the manual bottleneck of creating the APS JSON.

### 4. The AI Director: `booknlp`
* **The Problem:** Manually tagging a 400-page book to determine "who is speaking" for every single line is an immense bottleneck.
* **The Solution:** [BookNLP](https://github.com/dbamman/booknlp) is an NLP pipeline specifically trained on literature for character identification, coreference resolution (mapping "he said" to the right character), and dialogue attribution.
* **The Aster Vision:** Users drop a raw `.epub` into Aster. BookNLP parses the text, extracts all unique characters, drafts a preliminary Cast Bible, and generates a fully attributed APS JSON ready for the Gemini Director to inject performance notes.

---

## Phase 3: Premium Polish & Delivery

These tools elevate the final output from "great audio" to an immersive, interactive media experience.

### 7. The Immersive Soundstage: `audiocraft` (AudioGen)
* **The Problem:** Aster's SFX layering relies on a static, pre-downloaded library of audio assets.
* **The Solution:** Meta's [AudioGen / AudioCraft](https://github.com/facebookresearch/audiocraft) generates high-fidelity sound effects and environmental acoustics purely from text prompts.
* **The Aster Vision:** Instead of fetching `wind_04.wav`, the AI Director simply tags a scene with `"acoustics": "howling wind through a wooden cabin window"`. Aster dynamically generates a bespoke 30-second environmental track and feeds it seamlessly into the SFX mixer.

### 8. Interactive Playback: `stable-ts`
* **The Problem:** The final output is currently a flat `.wav` file, preventing modern interactive playback features.
* **The Solution:** [Stable Whisper (`stable-ts`)](https://github.com/jianfch/stable-ts) provides hyper-accurate, word-level timestamps for audio.
* **The Aster Vision:** Aster outputs a perfectly synced `.vtt` or JSON mapping alongside the final chapter audio. This allows companion apps to feature "karaoke-style" text highlighting as the audio plays, matching the premium UX of Spotify and elite reading apps.

### 10. Dynamic Pacing & Silence Control: `silero-vad` & `auto-editor`
* **The Problem:** Pacing is what makes an audiobook feel human. Generative TTS engines often leave weirdly long gaps between sentences or rush them together.
* **The Solution:** [Silero VAD](https://github.com/snakers4/silero-vad) for lightning-fast speech detection, paired with [auto-editor](https://github.com/WyattBlue/auto-editor).
* **The Aster Vision:** Aster uses `auto-editor` to automatically detect and trim dead air, long pauses, and silence beyond what `silero` catches. If it detects >1.5 seconds of dead air where the AI Director didn't request a `[pause]`, it automatically splices and tightens the gap, enforcing perfect dramatic timing without human editors.

### 11. [PAUSED] 3D Spatial Audio
* **The Concept:** Applying HRTFs (Head-Related Transfer Functions) using libraries like `spaudiopy` to create 3D spatial positioning for audio.
* **Why it's explicitly halted:** While the library call is simple, the architectural burden is massive:
  1. **Creative Cost Multiplication:** The APS has no concept of 3D space. Every single footstep and door close would require a human director to assign spatial metadata (angle, elevation, distance), multiplying production time across every chapter.
  2. **Mono Stem Pipeline:** HRTF convolution requires pristine mono source signals. If dialogue and SFX are already mixed into a stereo bed, they cannot be spatialized. This would require remixing the entire pipeline to keep stems isolated until the absolute final master.
  3. **HRTF Calibration Failures:** Generic HRTFs often sound worse than plain stereo to a large percentage of users. Because ear shapes vary, a "behind" sound can perceptually localize as "above" for the wrong listener. We will not ship a premium feature that measurably degrades UX for a fraction of the audience.

### 12. HLS Streaming Packaging: `ffmpeg-python` & `m3u8`
* **The Problem:** You cannot stream a massive 500MB `.wav` chapter file directly to a mobile app efficiently. It will buffer constantly and consume massive amounts of data.
* **The Solution:** The industry standard is HLS (HTTP Live Streaming), utilizing [ffmpeg-python](https://github.com/kkroening/ffmpeg-python) to chunk the audio, and [m3u8](https://github.com/globocom/m3u8) to build the playlists.
* **The Aster Vision:** Once the final chapter `.wav` is mastered, Aster automatically chops it into 6-second `.ts` segments and generates the `.m3u8` playlist. Aster then pushes these lightweight chunks to Cloudflare R2, allowing the end-user app to instantly stream the audiobook seamlessly, just like Spotify or Netflix.

---

## Phase 4: Studio-Grade Mastering

### 13. Pristine Voice Extraction: `demucs` & `deepfilternet`
* **The Problem:** You have an amazing 10-second reference clip for a character, but there is background music, wind, or room echo ruining the clone.
* **The Solution:** [DeepFilterNet](https://github.com/Rikorose/DeepFilterNet) for lightweight hiss/noise suppression, and Meta's [Demucs](https://github.com/facebookresearch/demucs) for full stem separation.
* **The Aster Vision:** Aster runs a cheap `deepfilternet` pass on all reference audio to clear out faint hiss or room tone. If heavy background music is detected, it escalates to a full `demucs` pass to strip the music, ensuring the TTS engine clones *only* the pristine, studio-dry vocal.

### 14. Target Studio Matchering: `matchering`
* **The Problem:** Even with limiters, it's incredibly difficult to manually EQ Aster's output to sound exactly like a $50k professional studio production.
* **The Solution:** [Matchering](https://github.com/sergree/matchering) is an open-source Python library for automatic audio mastering based on a reference track.
* **The Aster Vision:** You feed Aster a 30-second clip of a Penguin Random House audiobook. Aster automatically analyzes it and applies the exact EQ curve, frequency response, and loudness profile to your generated chapter. Aster doesn't just sound good—it sounds exactly like your favorite studio.

---

## Next Steps
The immediate priority is implementing **Phase 1 (The Flawless QA Loop)**, starting with `resemblyzer` to permanently close the voice consistency gap.
