# APS To Resemble DramaBox Rules

DramaBox uses a prompt format where quoted text is spoken literally and unquoted text is treated as direction.

```text
<speaker description>, "<dialogue>" <action direction> "<more dialogue>"
```

## Absolute Rule

Inside double quotes: spoken literally.

Outside double quotes: performance cue, never spoken.

## APS Conversion

```text
speaker + stable voice + scene context + performance cue -> outside quotes
exact beat text -> inside quotes
```

Example:

```text
Andreas Egger is a physically strained mountain laborer, afraid but trying to sound practical. He speaks through exertion, "Just don't die on me now"
```

## Stage Directions

Keep these outside quotes:

```text
She sighs deeply.
He clears his throat.
A long pause.
Her voice cracks.
He gulps nervously.
```

Correct:

```text
Horned Hannes is old and dying, but dryly defiant. His voice suddenly sharpens, "No, you limping devil!"
```

Incorrect:

```text
Horned Hannes says, "Cough. No, you limping devil!"
```

## Vocalisations

Phonetic vocalisations can be spoken if they are inside quotes:

```text
"Hahaha"
"Hehehe"
"Mmmmm"
"Ugh"
"Argh"
"Hmm"
```

Avoid inside quotes:

```text
"Sigh"
"Gasp"
"Cough"
"Ahem"
"Pfft"
```

