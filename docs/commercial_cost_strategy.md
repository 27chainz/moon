# Commercial Cost & Quality Strategy

This document outlines the strategic decisions regarding API costs, model selection, and margin optimization for Aster at a commercial scale.

## Core Audio Engine Decision: Gemini Audio vs. F5-TTS

**Decision:** We will exclusively use **Gemini Audio** (specifically the cinematic "Journey" or multimodal expressive voices) for the core narrative performance, despite F5-TTS being open-source and free (minus GPU compute).

**Reasoning:**
F5-TTS is a powerful zero-shot voice cloner, but it is purely a TTS model. Gemini is a massive, multi-modal reasoning engine. When Gemini reads a transcript, it inherently understands the semantic context—it knows when a character is sarcastic, terrified, or out of breath, and adjusts its pacing and inflection automatically. For an elite, editorial-grade audiobook, acting and emotional resonance are the most critical factors. Gemini delivers this; F5-TTS merely reads words in a cloned voice.

## Cost Optimization Strategies

Even using premium APIs, we can keep the production cost of a 10-hour audiobook under ~$15 by implementing the following pipeline optimizations:

### 1. Hybrid Casting (The "Main Cast" Routing)
We do not need to spend $16/1M characters on a background guard who speaks one line.
*   **Strategy:** The AI Director will assign an `importance` or `tier` score to every character in the Cast Bible. 
*   **Routing:** 
    *   `Tier 1` (Narrator, Protagonists, Antagonists) route to the premium Gemini Audio API.
    *   `Tier 2` (Background characters, crowds, minor NPCs) route to cheaper Google Cloud Neural voices ($4/1M) or a local F5-TTS Cloud Run container.

### 2. Minimizing "Blast Radius" on Rerolls
If the QA Gauntlet (`pyannote`, `resemblyzer`, `SQUIM`) detects a glitch at the end of a 3-minute generated audio file, discarding and rerolling it wastes 3 minutes of paid API credits.
*   **Strategy:** Maintain strict chunk limits during the APS export phase. By keeping generation chunks tight (e.g., 200-250 words maximum), a failed QA check only throws away ~30 seconds of paid audio. This mathematically limits the financial penalty of TTS hallucinations or robotic artifacts.

### 3. Strict Mix Separation & Caching
Changes to the sound design (Ambience, SFX) should never incur TTS API costs.
*   **Strategy:** The generated `.wav` files for voices must be permanently cached locally (or in Cloudflare R2) the moment they pass QA. If a human editor or the AI Director decides the "rain is too loud" in the final mix, Aster simply adjusts the timeline metadata and reruns the FFmpeg mixing script locally. We never re-ping the Gemini API unless the actual *text* or *performance* needs to change.

### 4. Zero Egress Streaming (Cloudflare R2)
Traditional cloud providers (AWS S3, Google Cloud Storage) charge massive egress fees when end-users stream audio, which can destroy the margins of an audiobook startup.
*   **Strategy:** All final `.m3u8` HLS playlists and `.ts` audio segments must be hosted on Cloudflare R2. Cloudflare charges $0 for bandwidth egress, meaning thousands of users can stream the audiobook without adding a single cent to the variable production/hosting cost.
