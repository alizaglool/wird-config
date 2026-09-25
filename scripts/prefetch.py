#!/usr/bin/env python3
"""
prefetch.py - server-side YouTube prefetch for the Wird iOS app.

Spends the YouTube Data API v3 quota ONCE per run on a server and writes
static JSON into this repo. The app reads that JSON at zero YouTube quota.

Reads : YOUTUBE_API_KEY (env), sheikhs.json (repo root)
Writes: channels/<channelId>.json for every channel, plus channels/index.json

Quota: 1 unit for the batched channels.list, then 11 units per channel
       (5 playlistItems pages + 5 videos batches + 1 playlists page).

Python 3 standard library only.
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

API_BASE = "https://www.googleapis.com/youtube/v3/"

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHEIKHS_PATH = os.path.join(REPO_ROOT, "sheikhs.json")
CHANNELS_DIR = os.path.join(REPO_ROOT, "channels")

MAX_UPLOAD_PAGES = 5
PAGE_SIZE = 50
HTTP_ATTEMPTS = 3          # initial try + 2 retries
BACKOFF_SECONDS = (1, 3)   # waited before retry 1 and retry 2

SCHEMA_VERSION = 1

# ISO-8601 duration, e.g. PT0S, PT1H2M3S, P1DT4H, P2W
_DURATION_RE = re.compile(
    r"^P(?:(?P<weeks>\d+)W)?(?:(?P<days>\d+)D)?"
    r"(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+(?:\.\d+)?)S)?)?$"
)

quota_units = 0


class QuotaExceeded(Exception):
    """Raised when the API reports quotaExceeded - aborts the whole run."""


def log(msg):
    print(msg, flush=True)


def iso_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_duration(value):
    """ISO-8601 duration -> integer seconds, or None if unparseable."""
    if not value:
        return None
    m = _DURATION_RE.match(value.strip())
    if not m:
        return None
    weeks = int(m.group("weeks") or 0)
    days = int(m.group("days") or 0)
    hours = int(m.group("hours") or 0)
    minutes = int(m.group("minutes") or 0)
    seconds = float(m.group("seconds") or 0)
    total = weeks * 604800 + days * 86400 + hours * 3600 + minutes * 60 + seconds
    return int(total)


def as_int(value, default=None):
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_str(value):
    """Never emit JSON null for a string field."""
    return value if isinstance(value, str) else ""


def pick_thumbnail(thumbnails):
    """snippet.thumbnails -> best available url, preferring high > medium > default."""
    if not isinstance(thumbnails, dict):
        return ""
    for key in ("high", "medium", "default"):
        entry = thumbnails.get(key)
        if isinstance(entry, dict):
            url = entry.get("url")
            if url:
                return url
    return ""


def api_get(endpoint, params, api_key):
    """One quota-billed API call, with retries on 5xx and transient URLError."""
    global quota_units

    query = dict(params)
    query["key"] = api_key
    url = API_BASE + endpoint + "?" + urllib.parse.urlencode(query, doseq=True)
    safe_url = API_BASE + endpoint + "?" + urllib.parse.urlencode(
        {k: v for k, v in params.items()}, doseq=True
    )

    last_error = None
    for attempt in range(HTTP_ATTEMPTS):
        if attempt:
            time.sleep(BACKOFF_SECONDS[min(attempt - 1, len(BACKOFF_SECONDS) - 1)])
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                quota_units += 1
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            quota_units += 1
            body = ""
            try:
                body = exc.read().decode("utf-8", "replace")
            except Exception:
                pass
            reason = ""
            try:
                payload = json.loads(body)
                errors = payload.get("error", {}).get("errors") or []
                if errors:
                    reason = errors[0].get("reason", "") or ""
            except Exception:
                pass

            if exc.code == 403 and reason in ("quotaExceeded", "dailyLimitExceeded"):
                raise QuotaExceeded(
                    "YouTube API quota exhausted on %s (reason=%s)" % (endpoint, reason)
                )

            if 500 <= exc.code < 600 and attempt < HTTP_ATTEMPTS - 1:
                last_error = "HTTP %s on %s" % (exc.code, safe_url)
                log("      retrying after %s" % last_error)
                continue

            raise RuntimeError(
                "HTTP %s on %s (reason=%s)" % (exc.code, safe_url, reason or "unknown")
            )
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if attempt < HTTP_ATTEMPTS - 1:
                last_error = "%s on %s" % (type(exc).__name__, safe_url)
                log("      retrying after %s" % last_error)
                continue
            raise RuntimeError("network failure on %s: %s" % (safe_url, exc))

    raise RuntimeError("exhausted retries on %s (%s)" % (safe_url, last_error))


def fetch_channel_batch(channel_ids, api_key):
    """channels.list for up to 50 ids in ONE call -> {channelId: resource}."""
    out = {}
    for start in range(0, len(channel_ids), PAGE_SIZE):
        chunk = channel_ids[start:start + PAGE_SIZE]
        data = api_get(
            "channels",
            {
                "part": "snippet,statistics,brandingSettings,contentDetails",
                "id": ",".join(chunk),
                "maxResults": PAGE_SIZE,
            },
            api_key,
        )
        for item in data.get("items", []):
            if item.get("id"):
                out[item["id"]] = item
    return out


def build_channel_object(channel_id, curated_name, resource):
    snippet = resource.get("snippet") or {}
    stats = resource.get("statistics") or {}
    branding = (resource.get("brandingSettings") or {}).get("image") or {}
    return {
        "id": channel_id,
        # Curated name from sheikhs.json on purpose - YouTube's snippet.title
        # used to leak into the UI. Never read snippet.title here.
        "name": curated_name,
        "thumbnailUrl": pick_thumbnail(snippet.get("thumbnails")),
        "bannerImageUrl": as_str(branding.get("bannerExternalUrl")),
        "subscriberCount": as_int(stats.get("subscriberCount"), 0) or 0,
        "videoCount": as_int(stats.get("videoCount"), 0) or 0,
        "channelHandle": as_str(snippet.get("customUrl")),
        "channelDescription": as_str(snippet.get("description")),
    }


def fetch_uploads(uploads_playlist_id, api_key):
    """Walk at most MAX_UPLOAD_PAGES pages of the uploads playlist.

    Returns (items, next_page_token) where items is a list of
    {id, title, thumbnailUrl, publishedAt} in playlist order.
    """
    items = []
    seen = set()
    page_token = None
    for _ in range(MAX_UPLOAD_PAGES):
        params = {
            "part": "snippet",
            "maxResults": PAGE_SIZE,
            "playlistId": uploads_playlist_id,
        }
        if page_token:
            params["pageToken"] = page_token
        data = api_get("playlistItems", params, api_key)
        for entry in data.get("items", []):
            snippet = entry.get("snippet") or {}
            video_id = (snippet.get("resourceId") or {}).get("videoId")
            if not video_id or video_id in seen:
                continue
            seen.add(video_id)
            items.append({
                "id": video_id,
                "title": as_str(snippet.get("title")),
                "thumbnailUrl": pick_thumbnail(snippet.get("thumbnails")),
                "publishedAt": as_str(snippet.get("publishedAt")),
            })
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return items, page_token


def fetch_video_details(video_ids, api_key):
    """videos.list in batches of 50 -> {videoId: {durationSeconds, viewCount, isPastBroadcast}}."""
    details = {}
    for start in range(0, len(video_ids), PAGE_SIZE):
        chunk = video_ids[start:start + PAGE_SIZE]
        data = api_get(
            "videos",
            {
                "part": "contentDetails,statistics,liveStreamingDetails",
                "id": ",".join(chunk),
                "maxResults": PAGE_SIZE,
            },
            api_key,
        )
        for item in data.get("items", []):
            vid = item.get("id")
            if not vid:
                continue
            content = item.get("contentDetails") or {}
            stats = item.get("statistics") or {}
            live = item.get("liveStreamingDetails") or {}
            details[vid] = {
                "durationSeconds": parse_duration(content.get("duration")),
                "viewCount": as_int(stats.get("viewCount"), None),
                "isPastBroadcast": bool(live.get("actualEndTime")),
            }
    return details


def fetch_playlists(channel_id, api_key):
    """playlists.list, ONE page only. Private playlists are simply absent."""
    data = api_get(
        "playlists",
        {
            "part": "snippet,contentDetails",
            "channelId": channel_id,
            "maxResults": PAGE_SIZE,
        },
        api_key,
    )
    out = []
    for item in data.get("items", []):
        snippet = item.get("snippet") or {}
        content = item.get("contentDetails") or {}
        out.append({
            "id": as_str(item.get("id")),
            "title": as_str(snippet.get("title")),
            "thumbnailUrl": pick_thumbnail(snippet.get("thumbnails")),
            "itemCount": as_int(content.get("itemCount"), 0) or 0,
            "description": as_str(snippet.get("description")),
        })
    return out


def write_json(path, payload):
    """Atomic write so a crash mid-run never truncates a previous good file."""
    tmp_path = path + ".tmp"
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.replace(tmp_path, path)
    return len(text.encode("utf-8"))


def load_previous(channel_id):
    path = os.path.join(CHANNELS_DIR, channel_id + ".json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return None


def process_channel(channel_id, curated_name, resource, generated_at, api_key):
    channel_obj = build_channel_object(channel_id, curated_name, resource)

    related = ((resource.get("contentDetails") or {}).get("relatedPlaylists") or {})
    uploads_playlist_id = related.get("uploads") or ("UU" + channel_id[2:])

    uploads, next_token = fetch_uploads(uploads_playlist_id, api_key)

    detail_map = fetch_video_details([u["id"] for u in uploads], api_key)

    enriched = []
    unavailable = 0
    for upload in uploads:
        detail = detail_map.get(upload["id"])
        if detail is None:
            # Deleted or private video still listed in the uploads playlist.
            unavailable += 1
            continue
        enriched.append({
            "id": upload["id"],
            "title": upload["title"],
            "thumbnailUrl": upload["thumbnailUrl"],
            "publishedAt": upload["publishedAt"],
            "durationSeconds": detail["durationSeconds"],
            "viewCount": detail["viewCount"],
            "isPastBroadcast": detail["isPastBroadcast"],
        })

    # Stable sort keeps playlist order (already newest-first) as the tiebreak.
    enriched.sort(key=lambda v: v["publishedAt"], reverse=True)

    playlists = fetch_playlists(channel_id, api_key)

    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": generated_at,
        "channel": channel_obj,
        "uploadsPlaylistId": uploads_playlist_id,
        "uploadsNextPageToken": next_token,
        "uploads": enriched,
        "playlists": playlists,
    }

    path = os.path.join(CHANNELS_DIR, channel_id + ".json")
    size = write_json(path, payload)
    log("      %d uploads (%d unavailable skipped), %d playlists, %d bytes"
        % (len(enriched), unavailable, len(playlists), size))

    index_entry = dict(channel_obj)
    index_entry["uploadsPlaylistId"] = uploads_playlist_id
    return index_entry


def main():
    api_key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        log("ERROR: YOUTUBE_API_KEY is not set")
        return 1

    with open(SHEIKHS_PATH, "r", encoding="utf-8") as handle:
        sheikhs = json.load(handle)

    channels = [
        c for c in sheikhs.get("channels", [])
        if c.get("id") and c.get("name")
    ]
    if not channels:
        log("ERROR: sheikhs.json lists no usable channels")
        return 1

    os.makedirs(CHANNELS_DIR, exist_ok=True)
    generated_at = iso_now()
    log("Prefetch run %s - %d channels" % (generated_at, len(channels)))

    channel_ids = [c["id"] for c in channels]

    try:
        resources = fetch_channel_batch(channel_ids, api_key)
    except QuotaExceeded as exc:
        log("ABORT: %s" % exc)
        log("Quota units consumed: %d" % quota_units)
        return 1

    log("channels.list returned %d/%d resources" % (len(resources), len(channel_ids)))

    index_entries = []
    succeeded = 0
    failed = []

    for position, channel in enumerate(channels, start=1):
        channel_id = channel["id"]
        curated_name = channel["name"]
        log("[%2d/%d] %s (%s)" % (position, len(channels), curated_name, channel_id))

        resource = resources.get(channel_id)
        try:
            if resource is None:
                raise RuntimeError("channels.list returned no resource for this id")
            index_entries.append(
                process_channel(channel_id, curated_name, resource, generated_at, api_key)
            )
            succeeded += 1
        except QuotaExceeded as exc:
            log("ABORT: %s" % exc)
            log("Channels completed before abort: %d" % succeeded)
            log("Quota units consumed: %d" % quota_units)
            return 1
        except Exception as exc:  # noqa: BLE001 - one bad channel must not kill the run
            failed.append((channel_id, curated_name, str(exc)))
            log("      FAILED: %s" % exc)
            previous = load_previous(channel_id)
            if previous:
                log("      keeping previous channels/%s.json on disk" % channel_id)
                prev_channel = previous.get("channel") or {}
                if prev_channel.get("id"):
                    entry = dict(prev_channel)
                    entry["name"] = curated_name
                    entry["uploadsPlaylistId"] = as_str(previous.get("uploadsPlaylistId"))
                    index_entries.append(entry)

    if succeeded == 0:
        log("ERROR: every channel failed")
        log("Quota units consumed: %d" % quota_units)
        return 1

    index_payload = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": generated_at,
        "channels": index_entries,
    }
    index_size = write_json(os.path.join(CHANNELS_DIR, "index.json"), index_payload)

    log("")
    log("index.json: %d channels, %d bytes" % (len(index_entries), index_size))
    log("Succeeded: %d   Failed: %d" % (succeeded, len(failed)))
    for channel_id, name, err in failed:
        log("  FAILED %s (%s): %s" % (channel_id, name, err))
    log("Quota units consumed: %d" % quota_units)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except QuotaExceeded as exc:
        log("ABORT: %s" % exc)
        log("Quota units consumed: %d" % quota_units)
        sys.exit(1)
