from __future__ import annotations

from typing import Any

from idml_foundation.ai.security import payload_digest

EVIDENCE_SEGMENT_MAX_CHARACTERS = 500
EVIDENCE_MAX_SEGMENTS = 16
EVIDENCE_TOTAL_MAX_CHARACTERS = 8_000


def _aggregate_payload(evidence: dict[str, Any], segments: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "evidence_id": evidence["evidence_id"],
        "source_kind": evidence["source_kind"],
        "locator": evidence["locator"],
        "segment_count": len(segments),
        "total_characters": sum(len(str(segment["text"])) for segment in segments),
        "segments": [
            {
                "segment_id": segment["segment_id"],
                "position": segment["position"],
                "text_sha256": segment["text_sha256"],
            }
            for segment in segments
        ],
    }


def segment_evidence(
    *,
    evidence_id: str,
    source_kind: str,
    locator: str,
    text: str,
    segment_max_characters: int = EVIDENCE_SEGMENT_MAX_CHARACTERS,
) -> dict[str, Any]:
    """Build a bounded, lossless, individually and collectively authenticated evidence value."""
    if not evidence_id or not source_kind or not locator:
        raise ValueError("segmented evidence metadata is incomplete")
    if not text:
        raise ValueError("segmented evidence text is empty")
    if not 1 <= segment_max_characters <= EVIDENCE_SEGMENT_MAX_CHARACTERS:
        raise ValueError("segmented evidence chunk size is outside the allowed bound")
    if len(text) > EVIDENCE_TOTAL_MAX_CHARACTERS:
        raise ValueError("segmented evidence exceeds the total character bound")
    chunks = [
        text[offset : offset + segment_max_characters]
        for offset in range(0, len(text), segment_max_characters)
    ]
    if len(chunks) > EVIDENCE_MAX_SEGMENTS:
        raise ValueError("segmented evidence exceeds the segment count bound")
    segments = [
        {
            "segment_id": f"{evidence_id}:segment:{position + 1:03d}",
            "position": position,
            "text": chunk,
            "text_sha256": payload_digest(chunk),
        }
        for position, chunk in enumerate(chunks)
    ]
    evidence: dict[str, Any] = {
        "evidence_id": evidence_id,
        "source_kind": source_kind,
        "locator": locator,
        "segment_count": len(segments),
        "total_characters": len(text),
        "segments": segments,
    }
    evidence["aggregate_sha256"] = payload_digest(_aggregate_payload(evidence, segments))
    return evidence


def reassemble_evidence(evidence: dict[str, Any]) -> str:
    """Validate either legacy or segmented evidence and return its exact complete text."""
    if not isinstance(evidence, dict):
        raise ValueError("evidence must be an object")
    for name in ("evidence_id", "source_kind", "locator"):
        if not isinstance(evidence.get(name), str) or not evidence[name]:
            raise ValueError("evidence metadata is incomplete")

    if "segments" not in evidence:
        excerpt = evidence.get("excerpt")
        if not isinstance(excerpt, str) or not excerpt:
            raise ValueError("legacy evidence excerpt is missing")
        if payload_digest(excerpt) != evidence.get("excerpt_sha256"):
            raise ValueError("legacy evidence hash is invalid")
        return excerpt

    segments = evidence.get("segments")
    if not isinstance(segments, list) or not 1 <= len(segments) <= EVIDENCE_MAX_SEGMENTS:
        raise ValueError("segmented evidence count is invalid")
    if evidence.get("segment_count") != len(segments):
        raise ValueError("segmented evidence declared count is invalid")
    expected_ids: set[str] = set()
    for position, segment in enumerate(segments):
        if not isinstance(segment, dict):
            raise ValueError("evidence segment must be an object")
        expected_id = f"{evidence['evidence_id']}:segment:{position + 1:03d}"
        text = segment.get("text")
        if (
            segment.get("position") != position
            or segment.get("segment_id") != expected_id
            or expected_id in expected_ids
            or not isinstance(text, str)
            or not text
            or len(text) > EVIDENCE_SEGMENT_MAX_CHARACTERS
            or payload_digest(text) != segment.get("text_sha256")
        ):
            raise ValueError("evidence segment content, order, or hash is invalid")
        expected_ids.add(expected_id)
    text = "".join(str(segment["text"]) for segment in segments)
    if not text or len(text) > EVIDENCE_TOTAL_MAX_CHARACTERS:
        raise ValueError("segmented evidence total size is invalid")
    if evidence.get("total_characters") != len(text):
        raise ValueError("segmented evidence declared size is invalid")
    expected_aggregate = payload_digest(_aggregate_payload(evidence, segments))
    if evidence.get("aggregate_sha256") != expected_aggregate:
        raise ValueError("segmented evidence aggregate hash is invalid")
    if "excerpt" in evidence or "excerpt_sha256" in evidence:
        raise ValueError("segmented evidence cannot mix the legacy representation")
    return text


def evidence_reference(evidence: dict[str, Any]) -> dict[str, Any]:
    """Return the exact content-free reference an agent must cite in its proposal."""
    reassemble_evidence(evidence)
    base = {
        "evidence_id": evidence["evidence_id"],
        "source_kind": evidence["source_kind"],
        "locator": evidence["locator"],
    }
    if "segments" not in evidence:
        return {**base, "excerpt_sha256": evidence["excerpt_sha256"]}
    return {
        **base,
        "segments": [
            {
                "segment_id": segment["segment_id"],
                "position": segment["position"],
                "text_sha256": segment["text_sha256"],
            }
            for segment in evidence["segments"]
        ],
        "aggregate_sha256": evidence["aggregate_sha256"],
    }
