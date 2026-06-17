# APS Practice

Use this folder to test whether Aster can turn book passages into usable production scripts.

Workflow:

```text
inputs/sample_scene.txt
-> expected/sample_scene.aps.json
-> expected/sample_scene.gemini_request.json
-> expected/sample_scene.resemble_prompts.txt
```

Evaluation questions:

- Is the spoken text exact?
- Are stage directions separate from spoken text?
- Are speakers identified correctly?
- Would Gemini receive enough continuity to keep voices stable?
- Would DramaBox receive valid quoted/unquoted prompt text?
- Is the chunk small enough to render and QA?

