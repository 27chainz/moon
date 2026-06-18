import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from src.aura.aps_compiler import CANONICAL_EMOTIONS, normalize_emotion


DELIVERY_ARCHETYPES = {
    "storm_setup",
    "quiet_reveal",
    "command",
    "disbelief",
    "threat",
    "urgency",
    "final_dread",
}

SFX_TYPES = {
    "ambience",
    "background_event",
    "music",
    "motion",
    "room_tone",
    "spot",
    "transition",
}
SFX_PLACEMENTS = {
    "after_text",
    "beat_end",
    "beat_span",
    "beat_start",
    "before_text",
    "during_phrase",
    "phrase_span",
    "scene_span",
}
SFX_ALIGNMENT_FAILURE_POLICIES = {
    "degrade_to_fallback",
    "skip_and_flag_qa",
}
SFX_DURATION_POLICIES = {
    "fixed",
    "loop_crossfade",
    "match_beat",
    "match_phrase",
    "one_shot",
    "trim",
}

SAFE_REMOVABLE_TAGS = {"said", "asked"}
REVIEW_SAFE_DELIVERY_TAGS = {"whispered", "shouted", "muttered"}
DETERMINISTIC_TRANSFORMATIONS = {
    "screen_label_conversion",
    "email_header_conversion",
}


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def iter_beats(aps: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for scene in aps.get("scenes", []):
        for beat in scene.get("beats", []):
            yield beat


def normalize_spoken(value: Optional[str]) -> str:
    if value is None:
        return ""
    text = value.strip()
    text = text.strip('"')
    text = re.sub(r",$", "", text)
    return text.strip()


def add_error(errors: List[str], beat: Optional[Dict[str, Any]], message: str) -> None:
    if beat:
        errors.append(f"{beat.get('beat_id', 'unknown_beat')}: {message}")
    else:
        errors.append(message)


def validate_source_trace(aps: Dict[str, Any], errors: List[str]) -> None:
    source = (aps.get("source_document") or {}).get("text", "")
    for beat in iter_beats(aps):
        trace = beat.get("source_trace") or {}
        start = trace.get("source_start")
        end = trace.get("source_end")
        if not isinstance(start, int) or not isinstance(end, int):
            add_error(errors, beat, "source_trace must include integer source_start/source_end")
            continue
        if source[start:end] != trace.get("source_text"):
            add_error(errors, beat, "source_trace source_text does not match source_document slice")

        span = beat.get("source_span") or {}
        span_start = span.get("start_char")
        span_end = span.get("end_char")
        if span and (not isinstance(span_start, int) or not isinstance(span_end, int)):
            add_error(errors, beat, "source_span must include integer start_char/end_char when present")
        elif span and source[span_start:span_end] == "":
            add_error(errors, beat, "source_span points to an empty source slice")


def validate_speakers(aps: Dict[str, Any], errors: List[str]) -> None:
    characters = set((aps.get("characters") or {}).keys())
    for beat in iter_beats(aps):
        speaker = beat.get("speaker")
        if speaker not in characters:
            add_error(errors, beat, f"speaker {speaker!r} is not present in characters")


def validate_dialogue_tags(errors: List[str], beat: Dict[str, Any]) -> None:
    if beat.get("kind") not in {"dialogue", "dialogue_direction"}:
        return
    policy = beat.get("dialogue_tag_policy") or {}
    tag = policy.get("source_tag")
    classification = policy.get("classification")
    if tag in SAFE_REMOVABLE_TAGS and classification not in {"safe", "partial"}:
        add_error(errors, beat, f"safe tag {tag!r} must be classified safe or partial")
    if tag in REVIEW_SAFE_DELIVERY_TAGS and classification != "safe":
        add_error(errors, beat, f"delivery tag {tag!r} must be classified safe")
    if beat.get("source_trace", {}).get("removed_text_spans") and not policy:
        add_error(errors, beat, "removed source text requires dialogue_tag_policy")


def validate_punctuation(errors: List[str], beat: Dict[str, Any]) -> None:
    if not beat.get("speakable"):
        if beat.get("render_text") not in {None, ""}:
            add_error(errors, beat, "non-speakable beats should not include render_text")
        return
    render_text = beat.get("render_text")
    if render_text is None:
        add_error(errors, beat, "speakable beats require render_text")
        return
    trace = beat.get("source_trace") or {}
    source_spoken = beat.get("source_spoken_text")
    spoken_span = trace.get("spoken_text_span") or {}
    if source_spoken is None:
        source_spoken = spoken_span.get("text") or beat.get("text")
    if normalize_spoken(source_spoken) != normalize_spoken(render_text):
        add_error(errors, beat, "render_text does not match source spoken text under punctuation normalization")
    for mark in ["?", "!", "...", "--", "—"]:
        if mark in source_spoken and mark not in render_text:
            add_error(errors, beat, f"render_text must preserve meaning punctuation {mark!r}")


def validate_performance(errors: List[str], beat: Dict[str, Any]) -> None:
    performance = beat.get("performance") or {}
    if not performance:
        add_error(errors, beat, "performance is required")
        return
    emotion = performance.get("emotion")
    normalized = normalize_emotion(emotion)
    if normalized != str(emotion or "").strip().lower().replace("_", " "):
        add_error(errors, beat, f"performance.emotion should be canonical, e.g. {sorted(CANONICAL_EMOTIONS)}")
    try:
        intensity = float(performance.get("intensity"))
    except (TypeError, ValueError):
        add_error(errors, beat, "performance.intensity must be a number from 0.0 to 1.0")
        return
    if not 0.0 <= intensity <= 1.0:
        add_error(errors, beat, "performance.intensity must be between 0.0 and 1.0")
    modifier = performance.get("beat_modifier", beat.get("beat_modifier"))
    if modifier is not None:
        try:
            float(modifier)
        except (TypeError, ValueError):
            add_error(errors, beat, "beat_modifier must be numeric when present")


def expected_review_required(beat: Dict[str, Any]) -> Optional[str]:
    performance = beat.get("performance") or {}
    if float(performance.get("confidence", 1.0)) < 0.8:
        return "confidence_below_auto_accept_threshold"
    if beat.get("speaker_attribution") == "inferred_context":
        return "speaker_inferred_from_context"
    if beat.get("kind") == "dialogue_direction":
        return "dialogue_direction_removed_from_spoken_text"
    if beat.get("multiple_dialogue_spans_in_source"):
        return "multiple_dialogue_spans_in_source"

    trace = beat.get("source_trace") or {}
    span = beat.get("source_span") or {}
    if span and (
        trace.get("source_start") != span.get("start_char")
        or trace.get("source_end") != span.get("end_char")
    ):
        return "source_trace_span_differs_from_segment_span"

    removed = trace.get("removed_text_spans") or []
    if beat.get("transformation_type") in DETERMINISTIC_TRANSFORMATIONS:
        return None
    for item in removed:
        text = str(item.get("text", "")).lower()
        if not any(tag in text for tag in SAFE_REMOVABLE_TAGS):
            return "removed_text_beyond_said_or_asked"
    return None


def validate_review_flags(errors: List[str], beat: Dict[str, Any]) -> None:
    review = beat.get("review") or {}
    reason = expected_review_required(beat)
    if reason and not review.get("requires_review"):
        add_error(errors, beat, f"review.requires_review must be true: {reason}")
    if review.get("requires_review") and not review.get("risk_reason"):
        add_error(errors, beat, "review.risk_reason is required when requires_review is true")
    if not review.get("requires_review") and review.get("risk_reason") is not None:
        add_error(errors, beat, "review.risk_reason must be null when requires_review is false")


def validate_sequence(scene: Dict[str, Any], errors: List[str]) -> None:
    beats = scene.get("beats", [])
    expected = list(range(1, len(beats) + 1))
    actual = [beat.get("sequence_index") for beat in beats]
    if actual != expected:
        errors.append(f"{scene.get('scene_id', 'unknown_scene')}: sequence_index must be contiguous from 1")


def validate_delivery_archetypes(scene: Dict[str, Any], errors: List[str]) -> None:
    previous = None
    run = 0
    for beat in scene.get("beats", []):
        archetype = beat.get("delivery_archetype")
        if archetype not in DELIVERY_ARCHETYPES:
            add_error(errors, beat, f"delivery_archetype must be one of {sorted(DELIVERY_ARCHETYPES)}")
            previous = None
            run = 0
            continue
        if archetype == previous:
            run += 1
        else:
            previous = archetype
            run = 1
        if run > 3 and not beat.get("allow_repeated_archetype"):
            add_error(errors, beat, "delivery_archetype repeated more than 3 beats without allow_repeated_archetype")


def validate_renderer_constraints(aps: Dict[str, Any], errors: List[str]) -> None:
    constraints = aps.get("renderer_constraints") or {}
    if constraints.get("max_speakers") != 2:
        errors.append("renderer_constraints.max_speakers must be 2 for Gemini")
    if not constraints.get("chunk_strategy"):
        errors.append("renderer_constraints.chunk_strategy is required")


def validate_sfx_ducking(errors: List[str], scene: Dict[str, Any], sfx: Dict[str, Any]) -> None:
    ducking = sfx.get("ducking")
    if ducking is None or ducking is False:
        return
    if ducking is True:
        errors.append(f"{scene.get('scene_id', 'unknown_scene')}.{sfx.get('sfx_id', 'unknown_sfx')}: ducking must be an object, not true")
        return
    if not isinstance(ducking, dict):
        errors.append(f"{scene.get('scene_id', 'unknown_scene')}.{sfx.get('sfx_id', 'unknown_sfx')}: ducking must be an object")
        return
    if not ducking.get("enabled"):
        return
    for key in ["duck_by_db", "attack_ms", "release_ms"]:
        if key not in ducking:
            errors.append(
                f"{scene.get('scene_id', 'unknown_scene')}.{sfx.get('sfx_id', 'unknown_sfx')}: ducking.{key} is required when ducking is enabled"
            )


def validate_sfx_duration(errors: List[str], scene: Dict[str, Any], sfx: Dict[str, Any]) -> None:
    duration_policy = sfx.get("duration_policy")
    if duration_policy is None:
        return
    if isinstance(duration_policy, str):
        if duration_policy not in SFX_DURATION_POLICIES:
            errors.append(
                f"{scene.get('scene_id', 'unknown_scene')}.{sfx.get('sfx_id', 'unknown_sfx')}: duration_policy must be one of {sorted(SFX_DURATION_POLICIES)}"
            )
        return
    if not isinstance(duration_policy, dict):
        errors.append(f"{scene.get('scene_id', 'unknown_scene')}.{sfx.get('sfx_id', 'unknown_sfx')}: duration_policy must be a string or object")
        return
    policy = duration_policy.get("policy")
    if policy not in SFX_DURATION_POLICIES:
        errors.append(
            f"{scene.get('scene_id', 'unknown_scene')}.{sfx.get('sfx_id', 'unknown_sfx')}: duration_policy.policy must be one of {sorted(SFX_DURATION_POLICIES)}"
        )


def validate_sfx(scene: Dict[str, Any], errors: List[str]) -> None:
    beat_ids = {beat.get("beat_id") for beat in scene.get("beats", [])}
    for sfx in scene.get("sfx", []):
        prefix = f"{scene.get('scene_id', 'unknown_scene')}.{sfx.get('sfx_id', 'unknown_sfx')}"
        if not sfx.get("sfx_id"):
            errors.append(f"{prefix}: sfx_id is required")
        if sfx.get("type") not in SFX_TYPES:
            errors.append(f"{prefix}: type must be one of {sorted(SFX_TYPES)}")
        placement = sfx.get("placement")
        if placement not in SFX_PLACEMENTS:
            errors.append(f"{prefix}: placement must be one of {sorted(SFX_PLACEMENTS)}")

        if sfx.get("type") in {"ambience", "room_tone", "music"} or placement == "scene_span":
            if not sfx.get("start_beat") or not sfx.get("end_beat"):
                errors.append(f"{prefix}: scene-span SFX requires start_beat and end_beat")

        for key in ["start_beat", "end_beat", "anchor_beat"]:
            if sfx.get(key) and beat_ids and sfx.get(key) not in beat_ids:
                errors.append(f"{prefix}: {key} {sfx.get(key)!r} does not match a beat in this scene")

        if placement in {"beat_start", "beat_end", "beat_span", "after_text", "before_text", "during_phrase"}:
            if not sfx.get("anchor_beat"):
                errors.append(f"{prefix}: {placement} placement requires anchor_beat")

        if placement == "phrase_span":
            if not sfx.get("anchor_text"):
                errors.append(f"{prefix}: phrase_span placement requires anchor_text")
            if not sfx.get("anchor_beat"):
                errors.append(f"{prefix}: phrase_span placement requires anchor_beat")
            try:
                confidence = float(sfx.get("min_alignment_confidence"))
            except (TypeError, ValueError):
                errors.append(f"{prefix}: phrase_span requires numeric min_alignment_confidence")
            else:
                if not 0.0 <= confidence <= 1.0:
                    errors.append(f"{prefix}: min_alignment_confidence must be between 0.0 and 1.0")
            if sfx.get("fallback_placement") not in SFX_PLACEMENTS - {"phrase_span"}:
                errors.append(f"{prefix}: phrase_span requires fallback_placement that is not phrase_span")
            if sfx.get("on_alignment_failure") not in SFX_ALIGNMENT_FAILURE_POLICIES:
                errors.append(
                    f"{prefix}: on_alignment_failure must be one of {sorted(SFX_ALIGNMENT_FAILURE_POLICIES)}"
                )

        validate_sfx_duration(errors, scene, sfx)
        validate_sfx_ducking(errors, scene, sfx)


def validate_aps(aps: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if aps.get("schema_version") != "0.2":
        errors.append("schema_version must be 0.2")
    validate_source_trace(aps, errors)
    validate_speakers(aps, errors)
    validate_renderer_constraints(aps, errors)
    for scene in aps.get("scenes", []):
        validate_sequence(scene, errors)
        validate_delivery_archetypes(scene, errors)
        validate_sfx(scene, errors)
        for beat in scene.get("beats", []):
            validate_dialogue_tags(errors, beat)
            validate_punctuation(errors, beat)
            validate_performance(errors, beat)
            validate_review_flags(errors, beat)
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Strictly validate an APS file before renderer job generation.")
    parser.add_argument("aps", type=Path)
    args = parser.parse_args()

    errors = validate_aps(load_json(args.aps))
    if errors:
        print(f"APS validation failed with {len(errors)} error(s):")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print(f"APS validation passed: {args.aps}")


if __name__ == "__main__":
    main()
