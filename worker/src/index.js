//
//  index.js
//  wird-add-channel
//
//  Created by Ali Zaghloul on 25/09/2026.
//

const GITHUB_API = "https://api.github.com";

// Statuses that mean a run is still occupying the workflow.
const ACTIVE_STATUSES = ["queued", "in_progress", "waiting", "requested", "pending"];

// Used only when DAILY_RUN_LIMIT is missing or unparseable. Keep in sync with
// the value in wrangler.toml.
const DEFAULT_DAILY_RUN_LIMIT = 15;

const PAGE = `<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>إضافة قناة — ورد</title>
<style>
  :root {
    color-scheme: light;
    --bg: #f4f5f3;
    --surface: #ffffff;
    --text: #14171a;
    --muted: #6b7280;
    --line: #e2e4e0;
    --accent: #0f7a5a;
    --accent-fg: #ffffff;
    --accent-soft: rgba(15, 122, 90, 0.14);
    --ok: #0f7a5a;
    --err: #b3261e;
    --warn: #8a5300;
    --shadow: 0 1px 2px rgba(20, 23, 26, 0.05), 0 8px 24px rgba(20, 23, 26, 0.06);
  }

  @media (prefers-color-scheme: dark) {
    :root {
      color-scheme: dark;
      --bg: #0e1113;
      --surface: #171b1e;
      --text: #eceff1;
      --muted: #99a2aa;
      --line: #272d31;
      --accent: #3fbf93;
      --accent-fg: #06120d;
      --accent-soft: rgba(63, 191, 147, 0.18);
      --ok: #3fbf93;
      --err: #ff8a80;
      --warn: #f2b25c;
      --shadow: 0 1px 2px rgba(0, 0, 0, 0.4), 0 8px 24px rgba(0, 0, 0, 0.35);
    }
  }

  * { box-sizing: border-box; }

  html {
    -webkit-text-size-adjust: 100%;
  }

  body {
    margin: 0;
    padding: 24px 16px;
    min-height: 100vh;
    min-height: 100dvh;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", system-ui, "Helvetica Neue", Arial, sans-serif;
    font-size: 16px;
    line-height: 1.5;
  }

  .card {
    width: 100%;
    max-width: 460px;
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 20px;
    padding: 32px 28px;
    box-shadow: var(--shadow);
  }

  h1 {
    margin: 0;
    font-size: 24px;
    font-weight: 700;
    letter-spacing: -0.01em;
  }

  .sub {
    margin: 6px 0 28px;
    color: var(--muted);
    font-size: 15px;
  }

  label {
    display: block;
    margin-bottom: 8px;
    font-size: 13px;
    font-weight: 600;
    color: var(--muted);
  }

  .field + .field { margin-top: 18px; }

  input {
    width: 100%;
    min-height: 48px;
    padding: 12px 14px;
    font-family: inherit;
    font-size: 16px;
    color: var(--text);
    background: var(--bg);
    border: 1px solid var(--line);
    border-radius: 12px;
    outline: none;
    transition: border-color 0.15s ease, box-shadow 0.15s ease;
  }

  input::placeholder {
    color: var(--muted);
    opacity: 0.7;
  }

  input:focus-visible,
  input:focus {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px var(--accent-soft);
  }

  button {
    width: 100%;
    min-height: 48px;
    margin-top: 26px;
    padding: 12px 16px;
    font-family: inherit;
    font-size: 16px;
    font-weight: 600;
    color: var(--accent-fg);
    background: var(--accent);
    border: 0;
    border-radius: 12px;
    cursor: pointer;
    transition: opacity 0.15s ease, transform 0.1s ease;
  }

  button:active { transform: scale(0.99); }

  button:focus-visible {
    outline: none;
    box-shadow: 0 0 0 3px var(--accent-soft);
  }

  input:disabled,
  button:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }

  .status {
    display: flex;
    align-items: center;
    min-height: 44px;
    margin: 18px 0 0;
    font-size: 15px;
    color: var(--muted);
  }

  .status.ok { color: var(--ok); font-weight: 600; }
  .status.err { color: var(--err); font-weight: 600; }
  .status.warn { color: var(--warn); font-weight: 600; }

  @media (max-width: 380px) {
    body { padding: 16px 12px; }
    .card { padding: 24px 20px; border-radius: 16px; }
    h1 { font-size: 21px; }
  }

  @media (prefers-reduced-motion: reduce) {
    input, button { transition: none; }
    button:active { transform: none; }
  }
</style>
</head>
<body>
  <main class="card">
    <h1>إضافة قناة</h1>
    <p class="sub">أضف قناة يوتيوب إلى تطبيق ورد</p>

    <form id="form" novalidate>
      <div class="field">
        <label for="channel">رابط القناة</label>
        <input id="channel" type="text" autofocus placeholder="https://youtube.com/@handle" autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false" dir="ltr">
      </div>

      <div class="field">
        <label for="name">الاسم في التطبيق (اختياري)</label>
        <input id="name" type="text" autocomplete="off">
      </div>

      <div class="field">
        <label for="passcode">كلمة المرور</label>
        <input id="passcode" type="password" autocomplete="current-password">
      </div>

      <button id="submit" type="submit">إضافة</button>
    </form>

    <p class="status" id="status" role="status" aria-live="polite"></p>
  </main>

<script>
(function () {
  "use strict";

  var POLL_MS = 3000;
  var TIMEOUT_MS = 300000;
  var GRACE_MS = 10000;

  var MESSAGES = {
    waiting: "في الانتظار…",
    running: "جارٍ التنفيذ…",
    sending: "جارٍ الإرسال…",
    success: "✅ تمت الإضافة. ستظهر في التطبيق بعد التحديث",
    failure: "❌ فشلت الإضافة — تأكد من رابط القناة",
    timeout: "انتهت المهلة، راجع السجل",
    generic: "حدث خطأ، حاول مرة أخرى"
  };

  var ERRORS = {
    not_configured: "الخدمة غير مكتملة الإعداد",
    bad_passcode: "كلمة المرور غير صحيحة",
    empty_channel: "اكتب رابط القناة",
    already_added: "القناة مضافة بالفعل",
    busy: "هناك إضافة قيد التنفيذ الآن، جرّب بعد دقيقة",
    daily_limit: "وصلت للحد اليومي، جرّب غدًا"
  };

  var form = document.getElementById("form");
  var statusEl = document.getElementById("status");
  var channelEl = document.getElementById("channel");
  var nameEl = document.getElementById("name");
  var passcodeEl = document.getElementById("passcode");
  var submitEl = document.getElementById("submit");
  var controls = [channelEl, nameEl, passcodeEl, submitEl];

  var timer = null;
  var submittedAt = 0;
  var deadline = 0;

  function lock(locked) {
    for (var i = 0; i < controls.length; i++) {
      controls[i].disabled = locked;
    }
  }

  function say(text, kind) {
    statusEl.textContent = text;
    statusEl.className = kind ? "status " + kind : "status";
  }

  function finish(text, kind) {
    if (timer !== null) {
      clearInterval(timer);
      timer = null;
    }
    say(text, kind);
    lock(false);
    channelEl.value = "";
    channelEl.focus();
  }

  function readStatus() {
    if (Date.now() > deadline) {
      finish(MESSAGES.timeout, "err");
      return;
    }

    fetch("/status", { cache: "no-store" })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        if (!data || !data.ok) { return; }

        var run = data.run;
        if (!run || !run.createdAt) {
          say(MESSAGES.waiting);
          return;
        }

        var createdAt = Date.parse(run.createdAt);
        if (isNaN(createdAt) || createdAt < submittedAt - GRACE_MS) {
          say(MESSAGES.waiting);
          return;
        }

        if (run.status === "completed") {
          if (run.conclusion === "success") {
            finish(MESSAGES.success, "ok");
          } else {
            finish(MESSAGES.failure, "err");
          }
          return;
        }

        if (run.status === "in_progress") {
          say(MESSAGES.running);
          return;
        }

        say(MESSAGES.waiting);
      })
      .catch(function () { /* transient network blip: keep polling */ });
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    if (timer !== null || submitEl.disabled) { return; }

    lock(true);
    say(MESSAGES.sending);

    fetch("/add", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      body: JSON.stringify({
        channel: channelEl.value,
        name: nameEl.value,
        passcode: passcodeEl.value
      })
    })
      .then(function (response) {
        return response.json().catch(function () { return null; });
      })
      .then(function (data) {
        if (!data || !data.ok) {
          var code = data && data.error;
          var text = ERRORS[code] || MESSAGES.generic;
          var kind = "err";
          if (code === "already_added") {
            if (data.name) { text = text + ": " + data.name; }
            kind = "warn";
          }
          say(text, kind);
          lock(false);
          return;
        }

        submittedAt = Date.parse(data.submittedAt);
        if (isNaN(submittedAt)) { submittedAt = Date.now(); }
        deadline = Date.now() + TIMEOUT_MS;

        say(MESSAGES.waiting);
        timer = setInterval(readStatus, POLL_MS);
        readStatus();
      })
      .catch(function () {
        say(MESSAGES.generic, "err");
        lock(false);
      });
  });
})();
</script>
</body>
</html>`;

function jsonResponse(body, status) {
  return new Response(JSON.stringify(body), {
    status: status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store"
    }
  });
}

function failure(code, status) {
  return jsonResponse({ ok: false, error: code }, status);
}

// Byte-wise comparison with no early exit: the length mismatch and every byte
// difference land in the same accumulator.
function constantTimeEquals(a, b) {
  const encoder = new TextEncoder();
  const left = encoder.encode(typeof a === "string" ? a : "");
  const right = encoder.encode(typeof b === "string" ? b : "");

  let diff = left.length ^ right.length;
  const span = Math.max(left.length, right.length);
  for (let i = 0; i < span; i++) {
    diff |= (left[i] | 0) ^ (right[i] | 0);
  }

  return diff === 0;
}

// The Worker must exist before `wrangler secret put` can attach a secret to it,
// so it is briefly live with its secrets undefined. Every path that needs one
// checks first rather than falling through.
function hasSecret(value) {
  return typeof value === "string" && value.length > 0;
}

// All four headers are required; GitHub hard-403s a request without User-Agent.
function githubHeaders(env) {
  return {
    "Authorization": "Bearer " + env.GITHUB_TOKEN,
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "wird-add-channel"
  };
}

// Returns the run list (newest first) or null on any upstream failure.
async function listRuns(env) {
  const url = GITHUB_API + "/repos/" + env.GITHUB_OWNER + "/" + env.GITHUB_REPO +
    "/actions/workflows/" + env.WORKFLOW_FILE + "/runs?per_page=100";

  let response;
  try {
    response = await fetch(url, { headers: githubHeaders(env) });
  } catch (error) {
    return null;
  }

  if (!response.ok) {
    console.log("github runs request failed with status", response.status);
    return null;
  }

  try {
    const payload = await response.json();
    return Array.isArray(payload.workflow_runs) ? payload.workflow_runs : [];
  } catch (error) {
    return null;
  }
}

// Trailing characters that a paste can carry in but that are never part of a
// channel identifier: sentence punctuation, quotes, brackets, Arabic stops, and
// whitespace. A single trailing "." cost a failed run on 26/09/2026 — it reached
// forHandle verbatim and YouTube answered not-found. "-", "_", "@" and "/" are
// deliberately absent: each is legal inside a handle or a UC id. This set is
// duplicated in scripts/add_channel.py and the two must stay identical.
const TRAILING_JUNK = ".,;:!?)]}>([{<\"'`\u2019\u2018\u201D\u201C\u00AB\u00BB\u060C\u061B\u061F\u06D4\u2026 \t\r\n";

// The input with every trailing junk character removed. Only the tail is
// touched, so an internal period in a handle such as "dr.mahmoud_shaban"
// survives untouched.
function stripTrailingJunk(text) {
  let end = text.length;
  while (end > 0 && TRAILING_JUNK.indexOf(text.charAt(end - 1)) !== -1) {
    end -= 1;
  }
  return text.slice(0, end);
}

// The canonical channel id shape, mirroring _CHANNEL_ID_RE in scripts/add_channel.py.
const CHANNEL_ID_RE = /^UC[A-Za-z0-9_-]{22}$/;

// The UC id the input names, or "" when the input is a @handle, a /c/ or /user/
// vanity path, or a bare name. Those forms need a YouTube channels.list call to
// resolve and this Worker holds no API key, so they skip the pre-check and are
// left to scripts/add_channel.py exactly as before.
function channelIdFromInput(raw) {
  const text = String(raw).trim().replace(/[?#].*$/, "");
  const segments = text.split("/").filter(function (s) { return s.length > 0; });

  for (let i = 0; i < segments.length; i++) {
    if (segments[i].toLowerCase() === "channel") {
      const next = segments[i + 1];
      return next !== undefined && CHANNEL_ID_RE.test(next) ? next : "";
    }
  }

  return segments.length === 1 && CHANNEL_ID_RE.test(segments[0]) ? segments[0] : "";
}

// The @handle the input names, lowercased and WITHOUT the leading "@", or "" when
// the input names no handle. Covers "@name", "youtube.com/@name", any host, and a
// trailing path such as "/videos". A /c/ or /user/ vanity path is NOT a handle and
// still needs a YouTube channels.list call this Worker cannot make, so it returns ""
// and falls through to scripts/add_channel.py exactly as before.
function handleFromInput(raw) {
  let text = String(raw).trim().replace(/[?#].*$/, "");
  try {
    text = decodeURIComponent(text);
  } catch (error) {
    // A malformed percent-escape is not a reason to reject the input; the
    // undecoded text simply will not match a stored handle.
  }

  const segments = text.split("/").filter(function (s) { return s.length > 0; });
  for (const segment of segments) {
    if (segment.charAt(0) === "@" && segment.length >= 2) {
      return segment.slice(1).toLowerCase();
    }
  }

  return "";
}

// The parsed body of a repo file, or null when it could not be read. Every failure
// mode — network throw, non-2xx, unparseable body — collapses to null so that every
// caller falls through and dispatches, exactly as it did before these checks
// existed. The pre-checks are a convenience, never a gate.
async function fetchRepoJson(env, path) {
  const url = GITHUB_API + "/repos/" + env.GITHUB_OWNER + "/" + env.GITHUB_REPO +
    "/contents/" + path + "?ref=" + encodeURIComponent(env.GITHUB_REF);

  const headers = githubHeaders(env);
  // The raw media type returns the file body itself. The Contents API is read
  // instead of raw.githubusercontent.com because that host serves a CDN copy
  // that can lag several minutes — exactly the window a re-submission lands in.
  headers["Accept"] = "application/vnd.github.raw";

  let response;
  try {
    response = await fetch(url, { headers: headers });
  } catch (error) {
    return null;
  }

  if (!response.ok) {
    console.log(path + " request failed with status", response.status);
    return null;
  }

  try {
    return await response.json();
  } catch (error) {
    return null;
  }
}

// { name } when the channel is already in sheikhs.json, false when it is not,
// and null when the list could not be read.
async function lookupExistingChannel(env, channelId) {
  const payload = await fetchRepoJson(env, "sheikhs.json");
  const channels = payload && payload.channels;
  if (!Array.isArray(channels)) {
    return null;
  }

  for (const entry of channels) {
    if (entry && entry.id === channelId) {
      return { name: typeof entry.name === "string" ? entry.name : "" };
    }
  }

  return false;
}

// { name } when some listed channel carries this handle, false when none does, and
// null when the index could not be read. channels/index.json is generated from
// sheikhs.json by scripts/prefetch.py, so a match here is always a real duplicate.
// The stored handle is compared with its leading "@" stripped, so an entry written
// without one still matches.
async function lookupExistingByHandle(env, handle) {
  const payload = await fetchRepoJson(env, "channels/index.json");
  const channels = payload && payload.channels;
  if (!Array.isArray(channels)) {
    return null;
  }

  for (const entry of channels) {
    const stored = entry && typeof entry.channelHandle === "string" ? entry.channelHandle : "";
    // Normalize before the emptiness check: a stored "@" strips to "" and would
    // otherwise match an empty query, the one false positive this check must never
    // produce.
    const normalized = (stored.charAt(0) === "@" ? stored.slice(1) : stored).toLowerCase();
    if (normalized === "") {
      continue;
    }
    if (normalized === handle) {
      return { name: typeof entry.name === "string" ? entry.name : "" };
    }
  }

  return false;
}

async function dispatchWorkflow(env, channel, name) {
  const url = GITHUB_API + "/repos/" + env.GITHUB_OWNER + "/" + env.GITHUB_REPO +
    "/actions/workflows/" + env.WORKFLOW_FILE + "/dispatches";

  const headers = githubHeaders(env);
  headers["Content-Type"] = "application/json";

  let response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: headers,
      body: JSON.stringify({
        ref: env.GITHUB_REF,
        inputs: { channel: channel, name: name }
      })
    });
  } catch (error) {
    return false;
  }

  // Success is 204 with an empty body; anything else is a failure.
  if (response.status !== 204) {
    console.log("github dispatch failed with status", response.status);
    return false;
  }

  return true;
}

async function handleAdd(request, env) {
  // Before the JSON parse and before every other check: an undefined passcode
  // would throw in TextEncoder.encode, and an empty one would admit anybody.
  if (!hasSecret(env.ADD_PASSCODE) || !hasSecret(env.GITHUB_TOKEN)) {
    return failure("not_configured", 503);
  }

  let body;
  try {
    body = await request.json();
  } catch (error) {
    return failure("bad_request", 400);
  }

  if (body === null || typeof body !== "object") {
    return failure("bad_request", 400);
  }

  if (!constantTimeEquals(body.passcode, env.ADD_PASSCODE)) {
    return failure("bad_passcode", 401);
  }

  // scripts/add_channel.py owns channel parsing; only emptiness is checked here.
  // The clean runs BEFORE the emptiness check on purpose: an input that is
  // nothing but punctuation then answers empty_channel instead of dispatching a
  // run that cannot resolve anything. One value serves the pre-check below and
  // the dispatch further down, so the two can never disagree.
  const channel = stripTrailingJunk(
    typeof body.channel === "string" ? body.channel.trim() : "");
  if (channel.length === 0) {
    return failure("empty_channel", 400);
  }
  const name = typeof body.name === "string" ? body.name.trim() : "";

  // Duplicate pre-check, deliberately ahead of the busy and daily-limit guards:
  // a channel that is already listed gets a clear answer instead of queueing a
  // run that resolves it, changes nothing, and still reports success.
  const channelId = channelIdFromInput(channel);
  if (channelId !== "") {
    const existing = await lookupExistingChannel(env, channelId);
    if (existing !== null && existing !== false) {
      return jsonResponse({ ok: false, error: "already_added", name: existing.name }, 409);
    }
  } else {
    // A @handle cannot be resolved to a UC id without a YouTube API key, but
    // channels/index.json records every listed channel's handle, so the handle is
    // itself a key. /c/ and /user/ vanity paths remain uncheckable here.
    const handle = handleFromInput(channel);
    if (handle !== "") {
      const existingByHandle = await lookupExistingByHandle(env, handle);
      if (existingByHandle !== null && existingByHandle !== false) {
        return jsonResponse(
          { ok: false, error: "already_added", name: existingByHandle.name }, 409);
      }
    }
  }

  // One listing serves both guards.
  const runs = await listRuns(env);
  if (runs === null) {
    return failure("github_error", 502);
  }

  for (const run of runs) {
    if (ACTIVE_STATUSES.indexOf(run.status) !== -1) {
      return failure("busy", 429);
    }
  }

  const today = new Date().toISOString().slice(0, 10);
  let todayCount = 0;
  for (const run of runs) {
    if (typeof run.created_at === "string" && run.created_at.slice(0, 10) === today) {
      todayCount += 1;
    }
  }
  // Number("") is 0 and Number(undefined) is NaN; either would disable the cap,
  // so an unusable value falls back to the documented default instead.
  const configuredLimit = Number(env.DAILY_RUN_LIMIT);
  const dailyLimit = Number.isFinite(configuredLimit) && configuredLimit > 0
    ? Math.floor(configuredLimit)
    : DEFAULT_DAILY_RUN_LIMIT;
  if (todayCount >= dailyLimit) {
    return failure("daily_limit", 429);
  }

  const submittedAt = new Date().toISOString();
  const dispatched = await dispatchWorkflow(env, channel, name);
  if (!dispatched) {
    return failure("github_error", 502);
  }

  return jsonResponse({ ok: true, submittedAt: submittedAt }, 200);
}

async function handleStatus(env) {
  if (!hasSecret(env.GITHUB_TOKEN)) {
    return failure("not_configured", 503);
  }

  const runs = await listRuns(env);
  if (runs === null) {
    return failure("github_error", 502);
  }

  if (runs.length === 0) {
    return jsonResponse({ ok: true, run: null }, 200);
  }

  // GitHub documents newest-first but does not guarantee it; a malformed or
  // missing created_at must never win, so runs[0] stays the fallback.
  let newest = runs[0];
  let newestAt = Date.parse(newest.created_at);
  if (isNaN(newestAt)) { newestAt = -Infinity; }
  for (const run of runs) {
    const at = Date.parse(run.created_at);
    if (!isNaN(at) && at > newestAt) {
      newest = run;
      newestAt = at;
    }
  }
  return jsonResponse({
    ok: true,
    run: {
      status: newest.status === undefined ? null : newest.status,
      conclusion: newest.conclusion === undefined ? null : newest.conclusion,
      createdAt: newest.created_at === undefined ? null : newest.created_at,
      url: newest.html_url === undefined ? null : newest.html_url
    }
  }, 200);
}

export default {
  async fetch(request, env, ctx) {
    const path = new URL(request.url).pathname;

    if (request.method === "GET" && path === "/") {
      return new Response(PAGE, {
        headers: {
          "Content-Type": "text/html; charset=utf-8",
          "Cache-Control": "no-store"
        }
      });
    }

    if (request.method === "POST" && path === "/add") {
      try {
        return await handleAdd(request, env);
      } catch (error) {
        return failure("github_error", 502);
      }
    }

    if (request.method === "GET" && path === "/status") {
      try {
        return await handleStatus(env);
      } catch (error) {
        return failure("github_error", 502);
      }
    }

    return failure("not_found", 404);
  }
};
