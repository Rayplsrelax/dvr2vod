"""Pure library-building logic for DVR2VOD.

No Django imports here: everything works on plain dicts so it can be
unit-tested outside Dispatcharr. plugin.py is responsible for turning
Recording rows into these plain dicts.
"""

import re
from datetime import datetime
from urllib.parse import quote

PLUGIN_KEY = "dvr2vod"

MODE_SERIES = "series_per_show"
MODE_FLAT = "flat_movies"

# SxxExy anywhere in a title: "Show - S01E02 - Pilot", "Show S01E02",
# provider-glued "NovaS01E12rivers". No leading boundary requirement (the
# show name may be glued to the marker); trailing junk after the episode
# number is ignored.
_EP_RE = re.compile(r"[Ss](\d{1,2})\s*[Ee](\d{1,3})(?!\d)")
# "Show - 2024-01-02" / "Show 2024.01.02" date-stamped episodes.
_DATE_RE = re.compile(r"\b(\d{4})[-.](\d{2})[-.](\d{2})\b")
# Separators used to split "Show - Episode" / "Show | Episode" /
# "Show: Episode". A split needs at least one space on one side of the
# separator: glued hyphens ("Star-Wars") are part of names, not separators.
_SPLIT_RE = re.compile(r"\s*[-|:]\s+|\s+[-|:]\s*")

_FALLBACK_SHOW = "Recordings"


def _clean(text):
    """Collapse whitespace and strip wrapper quotes from a raw title."""
    return re.sub(r"\s+", " ", str(text or "")).strip().strip("\"'")


def _strip_sep(text):
    """Remove separator leftovers from a show-name prefix ("Chelsea -" ->
    "Chelsea") without eating meaningful inner separators."""
    return text.rstrip(" -|:").strip()


def split_show_episode(title):
    """Best-effort split of a recording title into (show, episode_label).

    Tries, in order: an explicit SxxExy marker, a date stamp, then the first
    separator ("Show - Episode"). Falls back to (title, "").
    """
    title = _clean(title)
    if not title:
        return _FALLBACK_SHOW, ""

    match = _EP_RE.search(title)
    if match:
        ep = f"S{int(match.group(1)):02d}E{int(match.group(2)):02d}"
        show = _strip_sep(title[: match.start()]) or title
        return show, ep

    match = _DATE_RE.search(title)
    if match:
        show = _strip_sep(title[: match.start()]) or title
        return show, match.group(0).replace(".", "-")

    parts = _SPLIT_RE.split(title, maxsplit=1)
    if len(parts) == 2 and parts[0]:
        return parts[0], parts[1]
    return title, ""


def _normalize_show(name):
    """Grouping key: case/punctuation-insensitive show name."""
    return re.sub(r"[^a-z0-9]+", "", str(name or "").lower())


def build_entries(rows):
    """Turn raw recording dicts into sorted playlist entries.

    Each row needs: id, title, started_iso (ISO string or None), duration_s
    (int or None), logo (URL or ""). Unknown/blank titles still get an entry
    so nothing recorded silently disappears; the show falls back to a shared
    bucket.
    """
    entries = []
    for row in rows:
        raw_title = _clean(row.get("title"))
        if raw_title:
            title = raw_title
            show, episode = split_show_episode(title)
        else:
            # Nothing recorded silently disappears; a blank title lands in
            # the shared Recordings bucket instead of its own.
            title = "Untitled recording"
            show, episode = _FALLBACK_SHOW, ""
        entries.append(
            {
                "id": row.get("id"),
                "show": show,
                "episode": episode,
                "title": title,
                "started_iso": row.get("started_iso") or "",
                "duration_s": row.get("duration_s"),
                "logo": _clean(row.get("logo")),
            }
        )
    # Newest first; recordings without a timestamp sink to the end, stable
    # by id so output is deterministic.
    entries.sort(
        key=lambda e: (e["started_iso"] != "", e["started_iso"] or "", str(e["id"])),
        reverse=True,
    )
    return entries


def _stamp(started_iso):
    """Display stamp for an episode with no SxxExy marker."""
    if not started_iso:
        return ""
    try:
        dt = datetime.fromisoformat(str(started_iso).replace("Z", "+00:00"))
    except ValueError:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M")


def entry_url(entry, base_url, token):
    """Playback URL for one entry: Dispatcharr's recording file endpoint.

    The token rides as ?token=; both token and nothing else are URL-encoded.
    A missing base URL yields a relative diagnostic rather than a broken
    absolute URL, which preview surfaces instead of writing junk.
    """
    base = (base_url or "").rstrip("/")
    query = f"?token={quote(str(token), safe='')}" if token else ""
    return f"{base}/api/channels/recordings/{entry['id']}/file/{query}"


def _display_title(entry):
    """What the client shows as the episode/movie name."""
    stamp = _stamp(entry["started_iso"])
    date_part = stamp.split(" ")[0] if stamp else ""
    if entry["episode"]:
        head = f"{entry['show']} - {entry['episode']}"
        # A date-stamped episode label already carries the date; appending
        # the stamp again would render "Show - 2026-10-11 2026-10-11 20:20".
        if stamp and entry["episode"] != date_part:
            return f"{head} {stamp}"
        return head
    if stamp:
        return f"{entry['title']} ({stamp})"
    return entry["title"]


def _attr(value):
    """Escape an attribute value for #EXTINF."""
    return str(value or "").replace('"', "'").replace("\n", " ").strip()


def render_m3u(entries, base_url, token, mode=MODE_SERIES, group_title="DVR Recordings"):
    """Render the playlist. Group-title is the show name in series mode, the
    configured flat group in flat mode. Entries arrive newest-first and are
    kept in that order within each group."""
    lines = ["#EXTM3U"]
    for entry in entries:
        group = group_title if mode == MODE_FLAT else (entry["show"] or _FALLBACK_SHOW)
        attrs = (
            f'tvg-name="{_attr(entry["show"])}" '
            f'tvg-logo="{_attr(entry["logo"])}" '
            f'group-title="{_attr(group)}"'
        )
        lines.append(f'#EXTINF:-1 {attrs},{_attr(_display_title(entry))}')
        lines.append(entry_url(entry, base_url, token))
    return "\n".join(lines) + "\n"
