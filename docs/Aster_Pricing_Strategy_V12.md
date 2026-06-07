# ASTER

Pricing & Monetisation Strategy

Version 12 - June 2026

Confidential

Narrative Intelligence Platform | Consumer | Creator | B2B API

## 1. Executive Summary

Aster is a hybrid Narrative Intelligence platform that monetises through three channels:

- Consumer subscriptions
- Creator production services
- B2B/API licensing

The strategic change in Version 12 is the move from a single low-cost renderer assumption to a **multi-renderer audio stack**.

The NIL Engine is no longer defined by one model. It is the orchestration layer that controls rendering quality, voice design, casting, spatial audio, social masking, environmental foley, and long-form production workflow.

Renderer strategy:

| Engine lane | Purpose | Target use |
| --- | --- | --- |
| Gemini Premium Actor | Best available dramatic voice quality | Pro titles, flagship classics, paid author productions |
| Kokoro / CosyVoice / local Actor | Cost-controlled rendering | Pulse, catalogue scale, experiments, fallback |
| Hybrid pipeline | Best margin-quality balance | Use Gemini only where quality matters most |

This changes the old compute assumption:

```text
Old assumption: ~$0.50-$3.00 per book
New assumption: cost depends on renderer and finished audio length
```

For Gemini 2.5 Flash Preview TTS batch pricing, a 10-hour book is estimated at about **$4.50 in audio output cost**, excluding small text input costs and any retries.

This is higher than the original target, but still commercially viable for professional author pricing and premium catalogue production.

## 2. Core Philosophy

### Price to value, not raw compute

Even if premium AI rendering costs $4-$10 per long book, the relevant comparison remains human narration and studio production.

Human audiobook production commonly costs hundreds to thousands of dollars per finished book. Aster can still charge far below that while maintaining strong margins.

### Separate renderer cost from product value

Aster should not expose model choice as a raw commodity to customers. Customers buy outcomes:

- clean narration
- cinematic performance
- fast production
- no exclusivity
- creator-friendly economics

Internally, Aster chooses the cheapest renderer that meets the required quality bar.

### Pre-render everything

All audiobook audio should be generated once, QA'd, stored, and served from CDN. Listener playback must not trigger live inference.

This keeps generation cost fixed per title instead of variable per listen.

## 3. Renderer Economics

### 3.1 Gemini Premium Actor

Current official Google Gemini pricing lists:

| Model | Mode | Input | Audio output |
| --- | --- | ---: | ---: |
| Gemini 2.5 Flash Preview TTS | Standard | $0.50 / 1M text tokens | $10.00 / 1M audio tokens |
| Gemini 2.5 Flash Preview TTS | Batch | $0.25 / 1M text tokens | $5.00 / 1M audio tokens |
| Gemini 2.5 Pro Preview TTS | Standard | $1.00 / 1M text tokens | $20.00 / 1M audio tokens |
| Gemini 2.5 Pro Preview TTS | Batch | $0.50 / 1M text tokens | $10.00 / 1M audio tokens |
| Gemini 3.1 Flash TTS Preview | Standard | $1.00 / 1M text tokens | $20.00 / 1M audio tokens |
| Gemini 3.1 Flash TTS Preview | Batch | $0.50 / 1M text tokens | $10.00 / 1M audio tokens |

Google's pricing page states, in the Gemini TTS pricing section, that audio tokens correspond to 25 tokens per second of audio. Validate actual usage with API invoices before locking production margins.

### 3.2 Gemini Cost Estimate

Formula:

```text
finished_hours * 3600 seconds * 25 audio_tokens_per_second
= output_audio_tokens

output_audio_tokens / 1,000,000 * price_per_1M_audio_tokens
= render cost
```

Estimated Gemini 2.5 Flash Preview TTS costs:

| Finished length | Batch cost at $5/M | Standard cost at $10/M |
| ---: | ---: | ---: |
| 1 hour | $0.45 | $0.90 |
| 3 hours | $1.35 | $2.70 |
| 5 hours | $2.25 | $4.50 |
| 10 hours | $4.50 | $9.00 |
| 15 hours | $6.75 | $13.50 |
| 20 hours | $9.00 | $18.00 |

Input text cost is comparatively small. Add a production safety buffer for retries, bad generations, chunk stitching, and QA:

```text
Recommended Gemini production buffer: 1.25x to 1.75x raw render cost
```

Example:

```text
10-hour book, Gemini batch raw: ~$4.50
With 1.5x retry/QA buffer: ~$6.75
```

### 3.3 Open-Source Actor Estimate

Kokoro, CosyVoice, and F5-TTS should remain active candidates for cost-controlled generation.

Estimated local/open-source economics depend on GPU rental, speed, and retries. The strategic target remains:

```text
Open-source/local actor target: <$3 per 10-hour book
```

This is still important for:

- Pulse Audio
- high-volume catalogue
- public domain classics
- low-price subscription titles
- avoiding vendor lock-in

### 3.4 Recommended Renderer Policy

| Content type | Default renderer | Reason |
| --- | --- | --- |
| Flagship classic catalogue | Gemini Flash TTS batch | Best launch quality |
| Professional author production | Gemini Flash TTS batch | Quality sells the author tier |
| Pulse short audio | Kokoro/local first, Gemini optional | Keep impulse pricing viable |
| Long Pulse stories | Local or custom quote | Avoid margin leakage |
| B2B API premium tier | Gemini or hybrid | Customer pays for quality/SLA |
| B2B API low-cost tier | Kokoro/CosyVoice/local | Scalable margin |

## 4. Consumer Tiers

### 4.1 Aster Open

Free entry tier for acquisition.

| Feature | Detail |
| --- | --- |
| Reading | Unlimited text reading for Pulse, Original, and Classic titles |
| Audio preview | First 3 chapters of full cinematic audio |
| Ads | Native inline text-only ads between chapters in reading view |
| Goal | Acquire users and create audio-quality pull toward Aster Plus |

### 4.2 Aster Plus

Core recurring revenue product.

| Feature | Detail |
| --- | --- |
| Price | $6.99/month or $59.99/year |
| Audio access | Unlimited audio for eligible Pulse, Original, and Classic titles |
| Fidelity | Full NIL Engine on selected titles; standard AI audio on broad catalogue |
| Ad-free | No ads in reading or listening view |
| Goal | Predictable recurring revenue |

Important revision:

```text
Not every Plus title needs Gemini Premium rendering.
```

Use Gemini where it changes perceived quality. Use local engines for catalogue breadth.

### 4.3 Pro Unlock

Permanent ownership of individual professional titles.

| Feature | Detail |
| --- | --- |
| Price | $2.99-$5.99 per book, author's choice |
| Format | Permanent bimodal bundle: text + cinematic audio |
| Applies to | [PRO] badged titles |
| Creator payout | 70% of each sale to the author |
| Goal | Direct monetisation for professional series |

Gemini rendering supports this tier because render cost is incurred once and recovered across sales/listens.

## 5. Content Badge System

| Badge | Meaning | Audio model | Monetisation |
| --- | --- | --- | --- |
| [ORIGINAL] | Aster proprietary IP | Premium or hybrid NIL | Subscription pool |
| [CLASSIC] | Public domain titles | Premium for flagship, local for broad catalogue | Subscription pool |
| [PULSE] | Community / UGC | Local standard, Gemini optional upgrade | Ads + pool + creator fee |
| [PRO] | Verified professional authors | Gemini Premium or approved hybrid | 70% direct sales + pool |

## 6. Creator Tiers

### 6.1 Pulse Creator Pricing

Pulse is a community writing platform. Text publishing remains free. Audio is an optional platform upgrade.

Revised Pulse Audio pricing should include length limits.

| Tier | Detail |
| --- | --- |
| Pulse Free | Free text hosting and reading. Native ad share. No audio. |
| Pulse Audio Short | $9.99 one-time, up to 2 finished audio hours, local actor default |
| Pulse Audio Plus | $19.99 one-time, up to 5 finished audio hours, local actor default |
| Pulse Premium Render | Gemini quality, priced by quote or add-on |
| Long-form Pulse | Custom quote or move to Pro workflow |

Reason:

```text
Gemini makes unlimited $9.99 long-form audio too risky.
```

Pulse needs clear production caps to protect margins.

### 6.2 Professional Author Pricing

Professional authors are buying a studio production alternative, not a community feature.

| Tier | Detail |
| --- | --- |
| Cinematic Master | $149-$199 flat fee. Premium NIL Engine. [PRO] badge. 70% direct sales payout. |
| Cinematic Master Plus | $249-$399 for long books, multi-cast complexity, premium QA, or enhanced foley |
| Founding Author | First 20-30 authors receive free or discounted production for launch/social proof |

Recommendation:

```text
Keep $149-$199 for standard-length books.
Add an explicit long-book surcharge or upper length limit.
```

Suggested production boundaries:

| Book length | Pricing |
| ---: | --- |
| Up to 10 finished hours | $149-$199 |
| 10-15 finished hours | $249 |
| 15-20 finished hours | $299-$399 |
| 20+ finished hours | Custom quote |

With Gemini batch rendering, even a 20-hour book raw render cost is estimated around $9 before retries. The margin is still strong, but longer books require more QA and production time.

### 6.3 Creator Payout Model

| Revenue stream | Formula |
| --- | --- |
| Ad share | 50% of ad revenue generated by author's content |
| Subscription pool | 70% of Aster Plus revenue allocated to creator pool, distributed by listening minutes |
| Pro Unlock sales | 70% of each sale to author, processed monthly |
| Pulse Audio fee | Author keeps no fee revenue; this funds production |

## 7. Public Domain Catalogue

The original strategy of using public domain classics remains strong, but the cost assumptions should be split by renderer.

### 7.1 Catalogue Cost

Assume average classic length of 8-12 finished hours.

| Renderer | Estimated cost per 10h title | 50-title catalogue | 100-title catalogue |
| --- | ---: | ---: | ---: |
| Gemini Flash TTS batch raw | ~$4.50 | ~$225 | ~$450 |
| Gemini Flash TTS batch with 1.5x buffer | ~$6.75 | ~$338 | ~$675 |
| Local/open-source target | <$3.00 | <$150 | <$300 |

Recommendation:

```text
Use Gemini for 10-20 flagship classics.
Use local/open-source rendering for catalogue breadth.
```

This creates a premium launch showcase without letting catalogue costs balloon.

### 7.2 Recommended Launch Catalogue Split

| Category | Count | Renderer |
| --- | ---: | --- |
| Flagship cinematic classics | 10-20 | Gemini Premium |
| Broad classic catalogue | 30-80 | Kokoro/CosyVoice/local |
| Comparison demos | 5-10 | Render both local and Gemini for marketing tests |

## 8. Infrastructure & Cost Structure

### 8.1 Year 1 Cost Estimate

The old year-one GPU compute estimate of £100-£300 may still work for local-only rendering, but Gemini premium rendering creates a separate API cost line.

| Cost line | Estimated annual cost |
| --- | ---: |
| Cloud hosting | £600-£1,500 |
| CDN storage and delivery | £200-£600 |
| Local GPU/open-source production | £100-£300 |
| Gemini premium rendering API | £250-£1,500 depending catalogue and author volume |
| Occasional paid ads | £800-£1,500 |
| Legal templates + review | £500-£800 |
| Miscellaneous tools/APIs | £300-£700 |
| Total estimated year 1 overhead | £2,450-£6,900 |

Gemini does not destroy the lean solo-founder model, but it must be tracked separately.

### 8.2 Break-Even

| Metric | Value |
| --- | --- |
| Monthly fixed costs | ~£200-£575/month |
| Aster Plus subscribers to break even | ~4-12 subscribers/month |
| Cinematic Master sales to break even | ~2-4 sales/month |
| Gemini 10h raw render cost | ~$4.50 batch |
| Professional production gross margin | Still >90% at $149-$199 |

Even with Gemini, the professional tier remains highly profitable because the price is anchored to human narration alternatives, not compute.

## 9. Competitive Positioning

Aster should position around **premium AI performance at creator-friendly economics**.

| Dimension | ACX / Audible | Generic TTS apps | Aster |
| --- | --- | --- | --- |
| Creator royalty | 25-40% | Usually none | 70% direct sales |
| Exclusivity | Often restrictive | N/A | None |
| Audio quality | Human narrators | Variable | Gemini premium + NIL orchestration |
| Production cost | $1,200-$4,800/book | Low but generic | $149-$399 author service |
| Performance direction | Human narrator | Minimal | Director + Casting + Actor stack |
| Catalogue economics | Expensive | Cheap | Hybrid renderer control |

The new competitive message:

```text
Studio-quality AI audiobook production without studio pricing or platform lock-in.
```

## 10. Product Strategy Recommendation

### 10.1 Do Not Choose One Renderer

Gemini is the current quality leader, but Aster should not become a thin wrapper around Gemini.

Use:

```text
Gemini = premium quality Actor
Kokoro/CosyVoice/local = cost-control Actor
Aura NIL Engine = orchestration, casting, QA, foley, spatial mix, product workflow
```

### 10.2 Revised MVP

Build the renderer abstraction first:

```text
BaseSynthesizer
  GeminiSynthesizer
  KokoroSynthesizer
  CosyVoiceSynthesizer
```

Then run a cost-quality bake-off:

| Test | Goal |
| --- | --- |
| Same scene, Gemini vs Kokoro vs CosyVoice | Compare quality |
| 30-minute classic chapter | Estimate real cost and retry rate |
| Multi-character dialogue | Test casting and distinctness |
| 3-chapter preview | Test launch funnel quality |

### 10.3 Pricing Decision

Adopt a two-audio-tier internal model:

| Internal render class | Customer-facing label | Use |
| --- | --- | --- |
| Standard AI Audio | Aster Audio | Pulse, broad catalogue |
| Premium NIL Audio | Cinematic Audio | Pro, flagship classics, paid upgrades |

Customers do not need to know the model name. They need to know the quality level.

## 11. Pre-Launch Priority Checklist

- Validate Gemini API actual billed token usage on 10-30 minute samples
- Run Kokoro/CosyVoice/Gemini bake-off on the same manuscript scene
- Add hard length caps to Pulse Audio pricing
- Keep professional author pricing separate from Pulse pricing
- Update catalogue cost target to account for premium flagship renders
- Build multi-renderer `BaseSynthesizer` abstraction
- Pre-render all audio and store on CDN
- Publish creator payout formula
- Run Van Westendorp survey for Aster Plus
- Recruit 20-30 founding authors
- Produce 10-20 Gemini flagship classics and 30-80 local-rendered classics
- Prepare legal terms for AI-generated audio and creator rights

## 12. Key Risks

| Risk | Mitigation |
| --- | --- |
| Gemini pricing changes | Maintain Kokoro/CosyVoice fallback |
| Vendor lock-in | Keep renderer abstraction and store source requests |
| Long-form drift | Chunk chapters, QA outputs, retry bad segments |
| Pulse margin leakage | Add length caps and local default renderer |
| Quality inconsistency across engines | Separate Standard Audio from Cinematic Audio |
| Legal/API policy changes | Track provider terms and keep open-source route viable |

## 13. Bottom Line

Gemini should become Aster's **premium rendering benchmark** and likely the default for paid professional production.

It should not become the entire business.

The revised Aster strategy is:

```text
Use Gemini where quality creates pricing power.
Use open-source/local renderers where cost control creates scale.
Use Aura's NIL Engine as the proprietary orchestration layer above both.
```

This preserves the original business model while making the quality ceiling much higher.

## Sources

- Google Gemini API pricing: https://ai.google.dev/gemini-api/docs/pricing
- Google Gemini speech generation docs: https://ai.google.dev/gemini-api/docs/speech-generation
