#!/usr/bin/env python3
"""
add_channel.py - resolve a YouTube channel and append it to sheikhs.json.

Created by Ali Zaghloul on 25/09/2026.

Takes the channel URL, @handle or UC id typed into the GitHub Actions form,
resolves it to a canonical channel id with a single channels.list call and
appends it to sheikhs.json. A channel that is already listed is left alone and
the run still succeeds, so the workflow is safe to re-run.

Reads : YOUTUBE_API_KEY, INPUT_CHANNEL, INPUT_NAME (env), sheikhs.json (repo root)
Writes: sheikhs.json (repo root)

Quota: 1 unit for the single channels.list lookup.

Python 3 standard library only.
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

API_BASE = "https://www.googleapis.com/youtube/v3/"

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHEIKHS_PATH = os.path.join(REPO_ROOT, "sheikhs.json")

HTTP_ATTEMPTS = 3          # initial try + 2 retries
BACKOFF_SECONDS = (1, 3)   # waited before retry 1 and retry 2

# A canonical channel id: UC followed by exactly 22 more chars.
_CHANNEL_ID_RE = re.compile(r"^UC[A-Za-z0-9_-]{22}$")

# A handle: word chars, dot, dash. \w is Unicode-aware on purpose - Arabic
# handles exist and must not be rejected.
_HANDLE_RE = re.compile(r"^[\w.\-]+$")

# Legacy vanity prefixes. They resolve through forHandle far less reliably
# than /@handle does, so they get a warning rather than a silent accept.
_LEGACY_PREFIXES = frozenset(("c", "user"))

# Trailing characters a paste can carry in that are never part of a channel
# identifier. Kept character-for-character identical to TRAILING_JUNK in
# worker/src/index.js. "-", "_", "@" and "/" are deliberately absent: each is
# legal inside a handle or a UC id.
_TRAILING_JUNK = ".,;:!?)]}>([{<\"'`\u2019\u2018\u201D\u201C\u00AB\u00BB\u060C\u061B\u061F\u06D4\u2026 \t\r\n"

quota_units = 0


class QuotaExceeded(Exception):
    """Raised when the API reports quotaExceeded - aborts the whole run."""


def log(msg):
    print(msg, flush=True)


def set_step_output(name, value):
    """Write a GitHub Actions step output, no-op outside Actions."""
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("%s=%s\n" % (name, value))


def today_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def as_str(value):
    """Never treat a JSON null as a usable string."""
    return value if isinstance(value, str) else ""


def parse_channel_input(value):
    """Free-form channel input -> ("id", <id>) or ("handle", <handle>), else None.

    Tolerates a missing scheme, a www./m. host prefix, a trailing slash, a
    ?si=... share suffix, a #fragment and trailing tab segments like /videos.
    """
    text = (value or "").strip()
    if not text:
        return None

    # A #fragment or a ?si=... share suffix is never part of the identifier.
    text = text.split("#", 1)[0].split("?", 1)[0].strip()
    # Trailing sentence punctuation is a paste artifact. Left in place it passes
    # _HANDLE_RE, which permits a dot anywhere, and reaches forHandle verbatim:
    # run 36237559826 failed exactly that way on a single trailing period.
    text = text.rstrip(_TRAILING_JUNK)
    if not text:
        return None

    had_scheme = False
    for scheme in ("https://", "http://", "//"):
        if text.lower().startswith(scheme):
            text = text[len(scheme):]
            had_scheme = True
            break

    lowered = text.lower()
    is_url = had_scheme or "/" in text or "youtube.com" in lowered or "youtu.be" in lowered

    # Only a URL can carry a host prefix. A bare handle may legitimately start
    # with "m." and must not be truncated.
    if is_url:
        while True:
            lowered = text.lower()
            for prefix in ("www.", "m."):
                if lowered.startswith(prefix):
                    text = text[len(prefix):]
                    break
            else:
                break

    segments = [s for s in text.split("/") if s]
    if not segments:
        return None

    if is_url:
        host = segments[0].lower()
        if host in ("youtube.com", "youtu.be") or host.endswith(".youtube.com"):
            segments = segments[1:]
        elif "." in host:
            return None        # a URL pointing at some other site entirely
        if not segments:
            return None

    head = segments[0]
    lowered_head = head.lower()

    if lowered_head == "channel":
        if len(segments) > 1 and _CHANNEL_ID_RE.match(segments[1]):
            return ("id", segments[1])
        return None

    if lowered_head in _LEGACY_PREFIXES:
        if len(segments) > 1 and _HANDLE_RE.match(segments[1]):
            log("WARNING: /%s/ legacy URLs are unreliable - trying %r as a handle"
                % (lowered_head, segments[1]))
            return ("handle", segments[1])
        return None

    if head.startswith("@"):
        handle = head[1:]
        return ("handle", handle) if _HANDLE_RE.match(handle) else None

    # A bare token, or a legacy vanity path such as youtube.com/SomeName.
    if _CHANNEL_ID_RE.match(head):
        return ("id", head)
    if _HANDLE_RE.match(head):
        return ("handle", head)
    return None


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


def resolve_channel(kind, identifier, api_key):
    """ONE channels.list call -> the channel resource, or None if not found."""
    params = {"part": "snippet"}
    if kind == "id":
        params["id"] = identifier
    else:
        params["forHandle"] = "@" + identifier   # the @ prefix is required
    data = api_get("channels", params, api_key)
    items = data.get("items") or []
    return items[0] if items else None


def write_sheikhs(path, payload):
    """Atomic write in the exact formatting the committed sheikhs.json uses."""
    tmp_path = path + ".tmp"
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.replace(tmp_path, path)
    return len(text.encode("utf-8"))


def git_diff_stat(path):
    """Read-only proof of what actually changed. Never fails the run."""
    try:
        result = subprocess.run(
            ["git", "diff", "--stat", "--", path],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception as exc:  # noqa: BLE001 - diagnostics must not break the run
        log("  git diff     : unavailable (%s)" % exc)
        return
    output = (result.stdout or "").strip()
    log("  git diff     : %s" % (output or "(nothing reported)"))


def main():
    api_key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        log("ERROR: YOUTUBE_API_KEY is not set")
        return 1

    raw_input_channel = os.environ.get("INPUT_CHANNEL", "").strip()
    if not raw_input_channel:
        log("ERROR: INPUT_CHANNEL is not set - paste a channel URL, @handle or UC id")
        return 1

    input_name = os.environ.get("INPUT_NAME", "").strip()

    parsed = parse_channel_input(raw_input_channel)
    if parsed is None:
        log("ERROR: could not read %r as a YouTube channel" % raw_input_channel)
        log("Accepted forms:")
        log("  https://www.youtube.com/channel/UCxxxxxxxxxxxxxxxxxxxxxx")
        log("  https://www.youtube.com/@handle")
        log("  @handle")
        log("  handle")
        log("  UCxxxxxxxxxxxxxxxxxxxxxx")
        return 1

    kind, identifier = parsed
    log("Input %r read as %s %r" % (raw_input_channel, kind, identifier))

    try:
        resource = resolve_channel(kind, identifier, api_key)
    except QuotaExceeded as exc:
        log("ABORT: %s" % exc)
        log("Quota units consumed: %d" % quota_units)
        return 1

    if resource is None:
        log("Channel not found: %s" % raw_input_channel)
        log("Quota units consumed: %d" % quota_units)
        return 1

    channel_id = as_str(resource.get("id")).strip()
    if not _CHANNEL_ID_RE.match(channel_id):
        log("ERROR: resolved id %r is not a valid channel id" % channel_id)
        log("Quota units consumed: %d" % quota_units)
        return 1

    with open(SHEIKHS_PATH, "r", encoding="utf-8") as handle:
        sheikhs = json.load(handle)

    channels = sheikhs.get("channels")
    if not isinstance(channels, list):
        log("ERROR: sheikhs.json carries no 'channels' array")
        return 1

    for existing in channels:
        if isinstance(existing, dict) and existing.get("id") == channel_id:
            log("Already in the list: %s (%s)" % (channel_id, as_str(existing.get("name"))))
            log("Quota units consumed: %d" % quota_units)
            set_step_output("added", "false")
            return 0

    youtube_title = as_str((resource.get("snippet") or {}).get("title")).strip()
    if input_name:
        name, name_source = input_name, "input"
    else:
        name, name_source = youtube_title, "YouTube"
    if not name:
        log("ERROR: no display name - INPUT_NAME is blank and YouTube returned no title")
        log("Quota units consumed: %d" % quota_units)
        return 1

    channels.append({"id": channel_id, "name": name})
    # version and every other top-level key are left exactly as they were.
    sheikhs["updatedAt"] = today_utc()

    size = write_sheikhs(SHEIKHS_PATH, sheikhs)

    log("")
    log("Added %s" % channel_id)
    log("  name         : %s (from %s)" % (name, name_source))
    log("  channels now : %d" % len(channels))
    log("  sheikhs.json : %d bytes" % size)
    git_diff_stat(SHEIKHS_PATH)
    log("Quota units consumed: %d" % quota_units)
    set_step_output("added", "true")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except QuotaExceeded as exc:
        log("ABORT: %s" % exc)
        log("Quota units consumed: %d" % quota_units)
        sys.exit(1)
