import re
from datetime import datetime
from typing import Dict, List, Optional


Signal = Dict[str, object]


COMMUNITY_RULES = [
    ("annual", 24, "tradition", "Annual local event"),
    ("mostly annual", 26, "tradition", "Recurring local tradition"),
    ("contest", 20, "community_interest", "Competitive community event"),
    ("chili", 24, "community_interest", "Food-focused community draw"),
    ("concert", 18, "community_interest", "Live performance"),
    ("orchestra", 18, "community_interest", "Live performance"),
    ("performance", 16, "community_interest", "Public performance"),
    ("stroll", 14, "community_interest", "Public outdoor event"),
    ("walk", 14, "community_interest", "Public outdoor event"),
    ("talk", 12, "community_interest", "Public educational event"),
    ("book sale", 16, "community_interest", "Community fundraiser or library event"),
    ("festival", 20, "community_interest", "Festival-style public event"),
    ("public hearing", 32, "civic_impact", "Formal public hearing"),
    ("vote", 22, "civic_impact", "Likely vote or formal action"),
    ("budget", 26, "civic_impact", "Budget-related public matter"),
    ("zoning", 24, "civic_impact", "Land-use or zoning matter"),
    ("site plan", 24, "civic_impact", "Development review"),
    ("special permit", 24, "civic_impact", "Permit review"),
    ("affordable housing", 24, "civic_impact", "Housing-related public matter"),
    ("town meeting", 28, "civic_impact", "Town Meeting matter"),
    ("policy", 18, "civic_impact", "Policy matter"),
]

STORY_RULES = [
    ("public hearing", 28, "civic_impact", "Formal public hearing"),
    ("vote", 18, "civic_impact", "Likely vote or formal action"),
    ("budget", 20, "civic_impact", "Budget-related matter"),
    ("appropriation", 20, "civic_impact", "Appropriation or spending matter"),
    ("town meeting", 22, "civic_impact", "Town Meeting matter"),
    ("permit", 16, "civic_impact", "Permit or license matter"),
    ("special permit", 18, "civic_impact", "Special permit matter"),
    ("site plan", 18, "civic_impact", "Development review"),
    ("wastewater", 22, "civic_impact", "Infrastructure planning matter"),
    ("sewer", 18, "civic_impact", "Infrastructure planning matter"),
    ("school choice", 20, "civic_impact", "School policy choice"),
    ("policy review", 18, "civic_impact", "School or town policy review"),
    ("tobacco violation", 18, "public_health", "Public health enforcement matter"),
    ("variance request", 16, "civic_impact", "Variance or permit matter"),
    ("appointment", 10, "governance", "Appointment or board membership matter"),
    ("redevelopment", 16, "civic_impact", "Redevelopment or land-use matter"),
]

ROUTINE_MEETING_PATTERNS = (
    "meeting agenda",
    "meeting preview",
    "meeting recap",
)

HIGH_SIGNAL_BODIES = {
    "select board": 5,
    "planning board": 5,
    "zoning board of appeals": 5,
    "school committee": 5,
    "conservation commission": 4,
    "board of health": 4,
    "finance committee": 3,
}

TOPIC_RULES = [
    ("wastewater", "wastewater", "Wastewater"),
    ("sewer", "sewer", "Sewer"),
    ("town meeting", "town-meeting", "Town Meeting"),
    ("budget", "budget", "Budget"),
    ("policy", "policy", "Policy"),
    ("school choice", "schools", "Schools"),
    ("school committee", "schools", "Schools"),
    ("planning board", "development", "Development"),
    ("site plan", "development", "Development"),
    ("special permit", "development", "Development"),
    ("zoning", "zoning", "Zoning"),
    ("housing", "housing", "Housing"),
    ("affordable housing", "housing", "Housing"),
    ("tobacco", "public-health", "Public Health"),
    ("title 5", "public-health", "Public Health"),
    ("conservation", "environment", "Environment"),
    ("stormwater", "environment", "Environment"),
    ("community event", "community-life", "Community Life"),
    ("concert", "arts-culture", "Arts & Culture"),
    ("orchestra", "arts-culture", "Arts & Culture"),
    ("festival", "community-life", "Community Life"),
    ("contest", "community-life", "Community Life"),
    ("library", "community-life", "Community Life"),
]


def _clean_text(value: Optional[str]) -> str:
    return " ".join(str(value or "").split())


def _score_to_mode(score: int) -> str:
    if score >= 75:
        return "full_story"
    if score >= 45:
        return "brief"
    return "calendar_only"


def _add_signal(signals: List[Signal], weight: int, key: str, reason: str) -> int:
    signals.append({"key": key, "weight": weight, "reason": reason})
    return weight


def _apply_keyword_rules(text: str, rules: List[tuple], signals: List[Signal]) -> int:
    total = 0
    for needle, weight, key, reason in rules:
        if needle in text:
            total += _add_signal(signals, weight, key, reason)
    return total


def _timeliness_bonus(starts_at: Optional[str]) -> int:
    if not starts_at:
        return 0
    try:
        event_time = datetime.strptime(starts_at, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return 0
    delta = event_time - datetime.utcnow()
    if delta.days < 0:
        return 0
    if delta.days <= 2:
        return 10
    if delta.days <= 7:
        return 6
    if delta.days <= 14:
        return 3
    return 0


def _public_interest_bonus(text: str) -> int:
    total = 0
    if any(token in text for token in ("free library", "library", "bay association")):
        total += 6
    if any(token in text for token in ("family", "music", "raffles", "registrants")):
        total += 5
    return total


def score_community_event(event: Dict[str, object]) -> Dict[str, object]:
    title = _clean_text(event.get("title"))
    description = _clean_text(event.get("description"))
    source_type = _clean_text(event.get("source_type")).lower() or "community_event"
    source_category = _clean_text(event.get("source_category"))
    text = " ".join(filter(None, [title.lower(), description.lower(), source_category.lower()]))
    signals = []  # type: List[Signal]

    score = 18
    score += _apply_keyword_rules(text, COMMUNITY_RULES, signals)

    if source_type == "community_event":
        score += _add_signal(signals, 10, "community_event", "Community event")
    elif source_type == "official_meeting":
        score += _add_signal(signals, -10, "routine_meeting_penalty", "Routine official meeting")
    elif source_type == "regional_public_meeting":
        score += _add_signal(signals, 6, "regional_public_meeting", "Regional public meeting")
    elif source_type == "holiday":
        score += _add_signal(signals, 4, "holiday", "Holiday listing")

    if any(pattern in text for pattern in ROUTINE_MEETING_PATTERNS):
        score += _add_signal(signals, -18, "routine_meeting_penalty", "Routine meeting listing")

    if any(token in text for token in ("committee meeting", "board of", "commission meeting")) and "public hearing" not in text:
        score += _add_signal(signals, -8, "recurrence_penalty", "Recurring board or committee meeting")

    public_interest = _public_interest_bonus(text)
    if public_interest:
        score += _add_signal(signals, public_interest, "community_interest", "Strong public or cultural appeal")

    timeliness = _timeliness_bonus(_clean_text(event.get("starts_at")))
    if timeliness:
        score += _add_signal(signals, timeliness, "timeliness", "Upcoming soon")

    if any(token in text for token in ("saturday", "sunday", "pm")):
        score += _add_signal(signals, 4, "attendance_potential", "Likely public attendance window")

    score = max(0, min(100, score))
    topics = infer_topics(
        " ".join(
            filter(
                None,
                [
                    title,
                    description,
                    source_category,
                    source_type,
                ],
            )
        )
    )
    return {
        "score": score,
        "signals": signals,
        "coverage_mode": _score_to_mode(score),
        "topics": topics,
    }


def score_story(row: Dict[str, object]) -> Dict[str, object]:
    headline = _clean_text(row.get("headline"))
    summary = _clean_text(row.get("summary"))
    body_text = _clean_text(row.get("body_text"))
    story_type = _clean_text(row.get("story_type")).lower()
    body_name = _clean_text(row.get("body_name")).lower()
    text = " ".join(filter(None, [headline.lower(), summary.lower(), body_text.lower()[:1500]]))
    signals = []  # type: List[Signal]

    score = 20
    matched = []
    for needle, weight, key, reason in STORY_RULES:
        if needle in text:
            matched.append({"key": key, "weight": weight, "reason": reason})

    for signal in sorted(matched, key=lambda item: int(item["weight"]), reverse=True)[:2]:
        score += _add_signal(signals, int(signal["weight"]), str(signal["key"]), str(signal["reason"]))

    if story_type == "meeting_preview":
        score += _add_signal(signals, 6, "timeliness", "Upcoming meeting coverage")
    elif story_type == "minutes_recap":
        score += _add_signal(signals, 8, "accountability", "Post-meeting recap")

    body_bonus = HIGH_SIGNAL_BODIES.get(body_name)
    if body_bonus:
        score += _add_signal(signals, body_bonus, "body_priority", "High-interest civic body")

    if "why it matters" in body_text.lower():
        score += _add_signal(signals, 4, "context", "Story includes contextual framing")

    if "appointment" in text and not any(key in text for key in ("budget", "permit", "hearing", "wastewater", "policy")):
        score += _add_signal(signals, -8, "appointment_penalty", "Primarily appointment-driven agenda")

    score = max(0, min(100, score))
    topics = infer_topics(
        " ".join(
            filter(
                None,
                [
                    headline,
                    summary,
                    body_text[:1500],
                    body_name,
                ],
            )
        )
    )
    return {
        "score": score,
        "signals": signals,
        "coverage_mode": _score_to_mode(score),
        "topics": topics,
    }


def signal_summary(signals: List[Signal]) -> str:
    parts = []
    for signal in signals[:4]:
        weight = int(signal.get("weight") or 0)
        reason = _clean_text(signal.get("reason"))
        if not reason:
            continue
        parts.append("{} ({:+d})".format(reason, weight))
    return "; ".join(parts)


def infer_topics(text: str) -> List[Dict[str, str]]:
    lowered = _clean_text(text).lower()
    topics = []
    seen = set()
    for needle, slug, label in TOPIC_RULES:
        if needle in lowered and slug not in seen:
            seen.add(slug)
            topics.append({"slug": slug, "label": label})
    return topics[:5]
