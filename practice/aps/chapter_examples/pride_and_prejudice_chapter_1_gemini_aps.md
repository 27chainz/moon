# Practice APS: Pride and Prejudice, Chapter 1

Source: Jane Austen, *Pride and Prejudice*, Chapter 1. Public domain text available through Project Gutenberg.

Purpose: show how a book chapter becomes a Gemini-ready Aster Performance Script.

## Source Chapter

### Chapter 1

It is a truth universally acknowledged, that a single man in possession of a good fortune, must be in want of a wife.

However little known the feelings or views of such a man may be on his first entering a neighbourhood, this truth is so well fixed in the minds of the surrounding families, that he is considered the rightful property of some one or other of their daughters.

"My dear Mr. Bennet," said his lady to him one day, "have you heard that Netherfield Park is let at last?"

Mr. Bennet replied that he had not.

"But it is," returned she; "for Mrs. Long has just been here, and she told me all about it."

Mr. Bennet made no answer.

"Do you not want to know who has taken it?" cried his wife impatiently.

"You want to tell me, and I have no objection to hearing it."

This was invitation enough.

"Why, my dear, you must know, Mrs. Long says that Netherfield is taken by a young man of large fortune from the north of England; that he came down on Monday in a chaise and four to see the place, and was so much delighted with it, that he agreed with Mr. Morris immediately; that he is to take possession before Michaelmas, and some of his servants are to be in the house by the end of next week."

"What is his name?"

"Bingley."

"Is he married or single?"

"Oh! Single, my dear, to be sure! A single man of large fortune; four or five thousand a year. What a fine thing for our girls!"

"How so? How can it affect them?"

"My dear Mr. Bennet," replied his wife, "how can you be so tiresome! You must know that I am thinking of his marrying one of them."

"Is that his design in settling here?"

"Design! Nonsense, how can you talk so! But it is very likely that he may fall in love with one of them, and therefore you must visit him as soon as he comes."

"I see no occasion for that. You and the girls may go, or you may send them by themselves, which perhaps will be still better; for as you are as handsome as any of them, Mr. Bingley may like you the best of the party."

"My dear, you flatter me. I certainly have had my share of beauty, but I do not pretend to be anything extraordinary now. When a woman has five grown-up daughters, she ought to give over thinking of her own beauty."

"In such cases, a woman has not often much beauty to think of."

"But, my dear, you must indeed go and see Mr. Bingley when he comes into the neighbourhood."

"It is more than I engage for, I assure you."

"But consider your daughters. Only think what an establishment it would be for one of them. Sir William and Lady Lucas are determined to go, merely on that account, for in general, you know, they visit no newcomers. Indeed you must go, for it will be impossible for us to visit him if you do not."

"You are over-scrupulous, surely. I dare say Mr. Bingley will be very glad to see you; and I will send a few lines by you to assure him of my hearty consent to his marrying whichever he chooses of the girls; though I must throw in a good word for my little Lizzy."

"I desire you will do no such thing. Lizzy is not a bit better than the others; and I am sure she is not half so handsome as Jane, nor half so good-humoured as Lydia. But you are always giving her the preference."

"They have none of them much to recommend them," replied he; "they are all silly and ignorant like other girls; but Lizzy has something more of quickness than her sisters."

"Mr. Bennet, how can you abuse your own children in such a way? You take delight in vexing me. You have no compassion for my poor nerves."

"You mistake me, my dear. I have a high respect for your nerves. They are my old friends. I have heard you mention them with consideration these last twenty years at least."

"Ah, you do not know what I suffer."

"But I hope you will get over it, and live to see many young men of four thousand a year come into the neighbourhood."

"It will be no use to us, if twenty such should come, since you will not visit them."

"Depend upon it, my dear, that when there are twenty, I will visit them all."

Mr. Bennet was so odd a mixture of quick parts, sarcastic humour, reserve, and caprice, that the experience of three and twenty years had been insufficient to make his wife understand his character. Her mind was less difficult to develop. She was a woman of mean understanding, little information, and uncertain temper. When she was discontented, she fancied herself nervous. The business of her life was to get her daughters married; its solace was visiting and news.

## Gemini APS Output

```json
{
  "aps_version": "0.1",
  "book_id": "pride_and_prejudice",
  "title": "Pride and Prejudice",
  "chapter_id": "chapter_001",
  "chapter_title": "Chapter 1",
  "production_packet": {
    "the_scene": "A comic domestic opening in the Bennet household. The chapter establishes the marriage-market stakes of the neighbourhood and introduces the rhythm of Mr. and Mrs. Bennet's marriage.",
    "director_notes": [
      "The narration must sound elegant, ironic, and dry, not broad or cartoonish.",
      "Keep the period tone polished and socially observant.",
      "Dialogue should move with lively drawing-room timing.",
      "Do not modernise delivery or add slang.",
      "Preserve exact source text."
    ],
    "sample_context": "Classic literary comedy of manners with dry narration and polished domestic banter."
  },
  "characters": {
    "narrator": {
      "display_name": "Narrator",
      "role": "narrator",
      "stable_voice": "wry, elegant, lightly ironic literary narrator; clear and restrained",
      "provider_voice": {
        "gemini": "Kore"
      },
      "do_not_change": ["clarity", "period tone", "dry wit"]
    },
    "mr_bennet": {
      "display_name": "Mr. Bennet",
      "role": "main",
      "stable_voice": "middle-aged gentleman, dry, amused, calm, sardonic, never hurried",
      "provider_voice": {
        "gemini": "Orus"
      },
      "do_not_change": ["dry tone", "age", "calm delivery"]
    },
    "mrs_bennet": {
      "display_name": "Mrs. Bennet",
      "role": "main",
      "stable_voice": "middle-aged, excitable, socially anxious, theatrical, fast-moving, easily vexed",
      "provider_voice": {
        "gemini": "Leda"
      },
      "do_not_change": ["excitability", "social urgency", "period tone"]
    }
  },
  "scenes": [
    {
      "scene_id": "scene_001",
      "title": "A Single Man Of Large Fortune",
      "summary": "The narrator introduces the marriage-market logic of the neighbourhood, then Mr. and Mrs. Bennet discuss the arrival of Mr. Bingley at Netherfield Park.",
      "setting": "The Bennet household, early nineteenth-century England",
      "mood": "wry, domestic, comic, socially observant",
      "scene_context": "Mrs. Bennet is excited by news that a wealthy single man has taken Netherfield Park. Mr. Bennet quietly toys with her impatience.",
      "director_notes": [
        "Mr. Bennet should sound calm, amused, and sardonic, as if he is enjoying the conversation more than he admits.",
        "Mrs. Bennet should sound quick, socially anxious, and increasingly impatient, but still grounded in period manners.",
        "Keep the pace lively during dialogue, with quick back-and-forth timing."
      ],
      "sample_context": "A polished comic exchange between spouses, driven by gossip, teasing, and social ambition.",
      "beats": [
        {
          "beat_id": "scene_001_beat_001",
          "kind": "narration",
          "speaker": "narrator",
          "text": "It is a truth universally acknowledged, that a single man in possession of a good fortune, must be in want of a wife.",
          "context": "Opening aphorism of the novel.",
          "performance": {
            "emotion": "dry amusement",
            "intensity": 0.45,
            "pacing": "measured",
            "delivery": "iconic, elegant, lightly ironic"
          }
        },
        {
          "beat_id": "scene_001_beat_002",
          "kind": "narration",
          "speaker": "narrator",
          "text": "However little known the feelings or views of such a man may be on his first entering a neighbourhood, this truth is so well fixed in the minds of the surrounding families, that he is considered the rightful property of some one or other of their daughters.",
          "context": "The narrator expands the social joke.",
          "performance": {
            "emotion": "social satire",
            "intensity": 0.5,
            "pacing": "measured",
            "delivery": "wry, observant, slightly amused"
          }
        },
        {
          "beat_id": "scene_001_beat_003",
          "kind": "dialogue",
          "speaker": "mrs_bennet",
          "text": "My dear Mr. Bennet, have you heard that Netherfield Park is let at last?",
          "context": "Mrs. Bennet opens with exciting news.",
          "performance": {
            "emotion": "eager excitement",
            "intensity": 0.65,
            "pacing": "brisk",
            "delivery": "bright, urgent, expectant"
          }
        },
        {
          "beat_id": "scene_001_beat_004",
          "kind": "narration",
          "speaker": "narrator",
          "text": "Mr. Bennet replied that he had not.",
          "context": "A small dry pause before the conversation turns.",
          "performance": {
            "emotion": "dry restraint",
            "intensity": 0.35,
            "pacing": "short pause",
            "delivery": "plain and understated"
          }
        },
        {
          "beat_id": "scene_001_beat_005",
          "kind": "dialogue",
          "speaker": "mrs_bennet",
          "text": "But it is, for Mrs. Long has just been here, and she told me all about it.",
          "context": "Mrs. Bennet presses on, eager to share gossip.",
          "performance": {
            "emotion": "excited insistence",
            "intensity": 0.7,
            "pacing": "quick",
            "delivery": "impatient, pleased with the news"
          }
        },
        {
          "beat_id": "scene_001_beat_006",
          "kind": "dialogue",
          "speaker": "mrs_bennet",
          "text": "Do you not want to know who has taken it?",
          "context": "Mrs. Bennet becomes impatient with Mr. Bennet's silence.",
          "performance": {
            "emotion": "impatience",
            "intensity": 0.7,
            "pacing": "quick",
            "delivery": "pressing, slightly vexed"
          }
        },
        {
          "beat_id": "scene_001_beat_007",
          "kind": "dialogue",
          "speaker": "mr_bennet",
          "text": "You want to tell me, and I have no objection to hearing it.",
          "context": "Mr. Bennet knowingly invites her to continue.",
          "performance": {
            "emotion": "dry amusement",
            "intensity": 0.45,
            "pacing": "unhurried",
            "delivery": "calm, teasing, deadpan"
          }
        },
        {
          "beat_id": "scene_001_beat_008",
          "kind": "dialogue",
          "speaker": "mrs_bennet",
          "text": "Why, my dear, you must know, Mrs. Long says that Netherfield is taken by a young man of large fortune from the north of England; that he came down on Monday in a chaise and four to see the place, and was so much delighted with it, that he agreed with Mr. Morris immediately; that he is to take possession before Michaelmas, and some of his servants are to be in the house by the end of next week.",
          "context": "Mrs. Bennet releases the full news in a rush.",
          "performance": {
            "emotion": "gossiping excitement",
            "intensity": 0.8,
            "pacing": "fast but articulate",
            "delivery": "breathless social news, delighted urgency"
          }
        },
        {
          "beat_id": "scene_001_beat_009",
          "kind": "dialogue",
          "speaker": "mr_bennet",
          "text": "What is his name?",
          "context": "Mr. Bennet calmly asks for the key fact.",
          "performance": {
            "emotion": "mild curiosity",
            "intensity": 0.35,
            "pacing": "brief",
            "delivery": "calm and dry"
          }
        },
        {
          "beat_id": "scene_001_beat_010",
          "kind": "dialogue",
          "speaker": "mrs_bennet",
          "text": "Bingley.",
          "context": "Mrs. Bennet gives the name.",
          "performance": {
            "emotion": "triumphant certainty",
            "intensity": 0.55,
            "pacing": "brief",
            "delivery": "pleased and emphatic"
          }
        },
        {
          "beat_id": "scene_001_beat_011",
          "kind": "dialogue",
          "speaker": "mr_bennet",
          "text": "Is he married or single?",
          "context": "Mr. Bennet asks the question Mrs. Bennet cares about most.",
          "performance": {
            "emotion": "teasing calm",
            "intensity": 0.45,
            "pacing": "unhurried",
            "delivery": "knowingly dry"
          }
        },
        {
          "beat_id": "scene_001_beat_012",
          "kind": "dialogue",
          "speaker": "mrs_bennet",
          "text": "Oh! Single, my dear, to be sure! A single man of large fortune; four or five thousand a year. What a fine thing for our girls!",
          "context": "Mrs. Bennet reveals the marriage stakes.",
          "performance": {
            "emotion": "delighted urgency",
            "intensity": 0.85,
            "pacing": "fast",
            "delivery": "excited, emphatic, socially ambitious"
          }
        },
        {
          "beat_id": "scene_001_beat_013",
          "kind": "dialogue",
          "speaker": "mr_bennet",
          "text": "How so? How can it affect them?",
          "context": "Mr. Bennet pretends not to understand.",
          "performance": {
            "emotion": "mock innocence",
            "intensity": 0.45,
            "pacing": "unhurried",
            "delivery": "dry, teasing, deliberately obtuse"
          }
        },
        {
          "beat_id": "scene_001_beat_014",
          "kind": "dialogue",
          "speaker": "mrs_bennet",
          "text": "My dear Mr. Bennet, how can you be so tiresome! You must know that I am thinking of his marrying one of them.",
          "context": "Mrs. Bennet is exasperated by his teasing.",
          "performance": {
            "emotion": "vexed impatience",
            "intensity": 0.8,
            "pacing": "quick",
            "delivery": "indignant, theatrical, but comic"
          }
        }
      ]
    }
  ]
}
```

## Gemini Render Prompt Example

This is what the APS compiler should produce for a dialogue segment. It is not the whole chapter; it is one renderable chunk.

```text
## CHAPTER CONTEXT
A comic domestic opening in the Bennet household. The chapter establishes the marriage-market stakes of the neighbourhood and introduces the rhythm of Mr. and Mrs. Bennet's marriage.

## THE SCENE
Mrs. Bennet is excited by news that a wealthy single man has taken Netherfield Park. Mr. Bennet quietly toys with her impatience.

## DIRECTOR'S NOTES
- The narration must sound elegant, ironic, and dry, not broad or cartoonish.
- Keep the period tone polished and socially observant.
- Dialogue should move with lively drawing-room timing.
- Do not modernise delivery or add slang.
- Preserve exact source text.
- Mr. Bennet should sound calm, amused, and sardonic, as if he is enjoying the conversation more than he admits.
- Mrs. Bennet should sound quick, socially anxious, and increasingly impatient, but still grounded in period manners.
- Keep the pace lively during dialogue, with quick back-and-forth timing.

## SAMPLE CONTEXT
Classic literary comedy of manners with dry narration and polished domestic banter. A polished comic exchange between spouses, driven by gossip, teasing, and social ambition.

TTS the following conversation between Mrs. Bennet and Mr. Bennet:
Mrs. Bennet: My dear Mr. Bennet, have you heard that Netherfield Park is let at last?
Mrs. Bennet: But it is, for Mrs. Long has just been here, and she told me all about it.
Mrs. Bennet: Do you not want to know who has taken it?
Mr. Bennet: You want to tell me, and I have no objection to hearing it.
Mrs. Bennet: Why, my dear, you must know, Mrs. Long says that Netherfield is taken by a young man of large fortune from the north of England; that he came down on Monday in a chaise and four to see the place, and was so much delighted with it, that he agreed with Mr. Morris immediately; that he is to take possession before Michaelmas, and some of his servants are to be in the house by the end of next week.
Mr. Bennet: What is his name?
Mrs. Bennet: Bingley.
Mr. Bennet: Is he married or single?
Mrs. Bennet: Oh! Single, my dear, to be sure! A single man of large fortune; four or five thousand a year. What a fine thing for our girls!
Mr. Bennet: How so? How can it affect them?
Mrs. Bennet: My dear Mr. Bennet, how can you be so tiresome! You must know that I am thinking of his marrying one of them.
```

## Notes

For a real render, narration and dialogue should usually be split:

- Narration beats -> single-speaker Gemini requests using the narrator voice.
- Dialogue beats -> two-speaker Gemini requests when there are only two active speakers.
- More than two active speakers -> split into smaller chunks.
