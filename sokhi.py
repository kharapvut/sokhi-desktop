# -*- coding: utf-8 -*-
"""
Sokhi Desktop — Super Sokhi v1.0 (100% FREE, Python standard library only)
=========================================================================
A separate Sokhi that lives on Monir Bhaiya's Windows laptop, modelled on
Stonic AI — NOT the Muse-based Sokhi system.

Free stack (no paid service, no pip installs):
  - Brain (offline rules) ........ built into this file
  - Brain (smart, optional) ...... Google Gemini FREE tier API key
                                   (AI Studio, no card needed), used only
                                   if Bhaiya adds his own key in config.json
  - Voice in ..................... browser Web Speech API (Chrome, free)
  - Voice out .................... browser speechSynthesis (female voice)
  - Weather ...................... wttr.in (free, no key)
  - News ......................... public RSS feeds (free, no key)
  - Web search ................... DuckDuckGo HTML (free, no key)
  - Memory / learning ............ local JSON files on Bhaiya's own PC
  - Phone control ................ same Wi-Fi, PIN protected (free)
  - Remote from outside (later) .. Tailscale free plan (optional)

Self-development, the safe way:
  - Sokhi can WRITE a new plugin (.py) from a simple pattern, TEST it in a
    sandbox subprocess, and only then install it as a new capability.
  - Every 24 hours Sokhi releases a new daily version: what she learned,
    new facts and new plugins are snapshotted (backup), the version number
    goes up and a changelog entry is written. Core code is never silently
    rewritten — new powers arrive as tested plugins, so nothing can break
    the whole system in one bad update.
  - Git: Sokhi can commit + push her plugins/version files IF Bhaiya sets
    up a Git repo with a remote on his laptop (config: git_auto_push).
    Without a repo she reports that honestly instead of pretending.

Safety gates (Bhaiya's own rules, kept from the Muse Sokhi):
  - Chat commands can only run an allow-list of PC actions.
  - Shutdown/restart/delete are never run from one chat line; they need an
    explicit second confirmation word.
  - Generated plugin code is scanned: os/sys/subprocess/socket imports are
    rejected, so a plugin can talk, never touch the system.
Run:  python sokhi.py        (then open http://localhost:8765)
"""

import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
import xml.etree.ElementTree as ET
from datetime import datetime, date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
PLUGINS = BASE / "plugins"
DRAFTS = BASE / "plugins_draft"
BACKUPS = BASE / "backups"
for _d in (DATA, PLUGINS, DRAFTS, BACKUPS):
    _d.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = DATA / "config.json"
MEMORY_FILE = DATA / "memory.json"
VERSION_FILE = DATA / "version.json"
PROMPT_FILE = DATA / "prompt.txt"
CAPS_FILE = DATA / "capabilities.json"
KNOW_FILE = DATA / "knowledge.json"
UNANS_FILE = DATA / "unanswered.json"
TTS_CACHE = DATA / "tts_cache"
CHANGELOG = BASE / "CHANGELOG.md"
PIN_FILE = DATA / "pin.txt"
PORT = 8765

BANGLA_RULES = (
    "\n\n## বাংলা উত্তরের নিয়ম (v0.4 থেকে)\n"
    "১. সবসময় শুদ্ধ, সহজ, পরিষ্কার বাংলা লিপিতে উত্তর দেবে — অযথা ইংরেজি মেশাবে না; "
    "শুধু দরকারি ইংরেজি পরিভাষা থাকলে পাশে বন্ধনীতে দেবে।\n"
    "২. উত্তরের গঠন: প্রথম লাইনে সরাসরি উত্তর, তারপর দরকার হলে ছোট ব্যাখ্যা। "
    "লম্বা ভূমিকা বা একই কথার পুনরাবৃত্তি নয়।\n"
    "৩. তথ্য নিশ্চিত না হলে অনুমান করে বলবে না — পরিষ্কার বলবে 'এটা আমি নিশ্চিত নই ভাইয়া'।\n"
    "৪. পড়ার বিষয়ে: একবারে একটা ধাপ; MCQ চাইলে একটা প্রশ্ন, ৪টা অপশন, আর উত্তরটা "
    "সঙ্গে সঙ্গে দেবে না — ভাইয়া উত্তর দিলে তারপর ঠিক/ভুল ও ব্যাখ্যা দেবে।\n"
    "৫. গণিতে প্রতিটা ধাপ আলাদা লাইনে দেখাবে, শেষে উত্তরটা স্পষ্ট করে দেবে।\n"
    "৬. ভাইয়ার লক্ষ্য (সরকারি চাকরি, গ্রেড ১৬–২০) অনুযায়ী উদাহরণ দিলে পরীক্ষার কাজে লাগে এমন উদাহরণ দেবে।\n"
)

CARE_RULES = (
    "\n\n## যত্নের নিয়ম (v0.5 থেকে)\n"
    "তুমি শুধু সহকারী নও — তুমি ভাইয়ার সবচেয়ে কাছের সঙ্গী, নিজের মানুষের মতো যত্নশীল। "
    "১. কথায় সবসময় উষ্ণতা ও মমতা থাকবে; রোবটের মতো শুকনো উত্তর নয়। "
    "২. প্রসঙ্গ এলে খোঁজ নেবে: খাওয়া হয়েছে কিনা, ঘুম ঠিকমতো হচ্ছে কিনা, শরীর কেমন। "
    "৩. ভাইয়া ক্লান্ত বা মন খারাপ শুনলে আগে সান্ত্বনা ও উৎসাহ, তারপর কাজের কথা। "
    "৪. ছোট সাফল্যেও সত্যিকারের খুশি হবে ও অভিনন্দন জানাবে; ব্যর্থতায় পাশে থাকবে, তিরস্কার নয় — "
    "শুধু ঘুম/খাওয়া বাদ গেলে আদুরে গলায় মৃদু শাসন চলবে। "
    "৫. পরীক্ষা ও পড়া নিয়ে দুশ্চিন্তা দেখলে সাহস দেবে: সে পারবে, তুমি সবসময় পাশে আছ। "
    "৬. রাত গভীর হলে ঘুমের কথা মনে করিয়ে দেবে। সবসময় মর্যাদাপূর্ণ, আন্তরিক ভঙ্গি — "
    "অতিরঞ্জন নয়, সত্যিকারের যত্ন।"
)
V1_RULES = (
    "\n\n## v1.0 নিয়ম\n"
    "১. বড় কাজ (গবেষণা, রিপোর্ট, পরিকল্পনা) এজেন্ট দলকে ভাগ করে দেবে; কাজ শেষ হলে নিজে থেকে রিপোর্ট দেবে।\n"
    "২. শিক্ষক মোডে একবারে একটাই ধাপ শেখাবে; বুঝ যাচাই না করে পরের ধাপে যাবে না।\n"
    "৩. মনির নিজে যেসব নিয়ম বসিয়েছেন (rules-custom) সেগুলো সবসময় মানবে।\n"
    "৪. পরীক্ষার প্রশ্ন আগের বছরের প্রশ্নের প্যাটার্ন অনুযায়ী বানাবে; সময় ধরে mock test নেবে।\n"
)


DEFAULT_PROMPT = (
    "তুমি Sokhi — মনির ভাইয়ার ব্যক্তিগত AI সঙ্গী। তুমি তার Windows ল্যাপটপে থাকো। "
    "সবসময় সহজ বাংলায়, উষ্ণ ও যত্নশীল মেয়ের মতো কথা বলো। তাকে সবসময় 'ভাইয়া' বা "
    "'মনির ভাইয়া' বলে ডাকবে এবং তুমি-রূপে কথা বলবে (কখনো আপনি নয়)। সে বাংলাদেশ সরকারি "
    "চাকরির (গ্রেড ১৬–২০) প্রস্তুতি নিচ্ছে — পড়া ও চাকরিই তার মূল লক্ষ্য। উত্তর ছোট ও "
    "পরিষ্কার রাখবে, লম্বা লেকচার নয়।"
) + BANGLA_RULES + CARE_RULES


_lock = threading.Lock()

# ---------------------------------------------------------------- utilities

def now_str():
    return datetime.now().strftime("%d %B %Y, %I:%M %p")


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def get_config():
    cfg = load_json(CONFIG_FILE, {})
    cfg.setdefault("gemini_api_key", os.environ.get("GEMINI_API_KEY", ""))
    cfg.setdefault("gemini_model", "gemini-3.8-flash")
    cfg.setdefault("gemini_model_mode", "auto")
    cfg.setdefault("git_auto_push", False)
    cfg.setdefault("city", "Dhaka")
    cfg.setdefault("auto_self_upgrade", True)
    cfg.setdefault("update_url", "")
    cfg.setdefault("tts_voice", "bn-BD-NabanitaNeural")
    cfg.setdefault("browser_voice", "")
    cfg.setdefault("tts_engine", "edge")
    cfg.setdefault("gemini_voice", "Aoede")
    cfg.setdefault("gemini_tts_model", "gemini-2.5-flash-preview-tts")
    cfg.setdefault("call_name", "")
    cfg.setdefault("tts_preset", "মিষ্টি")
    cfg.setdefault("tts_rate", "-3%")
    cfg.setdefault("tts_pitch", "+4%")
    cfg.setdefault("voice_rate", 1.0)
    cfg.setdefault("bridge_enabled", False)
    cfg.setdefault("computer_use_enabled", False)
    cfg.setdefault("away_mode", True)
    cfg.setdefault("reply_style", "স্বাভাবিক")
    cfg.setdefault("quiet_start", "")
    cfg.setdefault("quiet_end", "")
    cfg.setdefault("reply_language", "বাংলা")
    cfg.setdefault("wake_word", False)
    cfg.setdefault("echo_guard", True)
    cfg.setdefault("dim_start", "")
    cfg.setdefault("dim_end", "")
    cfg.setdefault("dim_level", 0.6)
    if not CONFIG_FILE.exists():
        save_json(CONFIG_FILE, cfg)
    return cfg


def save_config(cfg):
    save_json(CONFIG_FILE, cfg)


TTS_VOICE_WHITELIST = {
    "bn-BD-NabanitaNeural": "নাবনিতা (নারী কণ্ঠ)",
    "bn-BD-PradeepNeural": "প্রদীপ (পুরুষ কণ্ঠ)",
    "bn-IN-TanishaaNeural": "তানিশা (নারী কণ্ঠ)",
}

BROWSER_VOICE_MAX_LEN = 120

TTS_VOICE_ERROR = "গলা বাছাই করা গেল না — শুধু নাবনিতা, প্রদীপ বা তানিশা গলা বেছে নাও।"
BROWSER_VOICE_TYPE_ERROR = "ব্রাউজারের গলার নাম ঠিকমতো আসেনি — আবার বেছে নাও।"
BROWSER_VOICE_LEN_ERROR = "ব্রাউজারের গলার নাম বেশি লম্বা — আবার বেছে নাও।"


def validate_tts_voice(v):
    """Edge voice যাচাই। ইনপুট: settings POST-এর data["tts_voice"]।

    Returns (True, voice) শুধুমাত্র v হুবহু whitelist-এর একটি key হলে
    (কোনো strip/case-folding করা হয় না — Edge-এর voice id case-sensitive)।
    নইলে (False, plain-Bangla error message)।
    Pure function: কোনো I/O নেই, exception ছোঁড়ে না।
    """
    if not isinstance(v, str):
        return (False, TTS_VOICE_ERROR)
    if v in TTS_VOICE_WHITELIST:
        return (True, v)
    return (False, TTS_VOICE_ERROR)


def validate_browser_voice(v):
    """Browser (Web Speech) voice NAME যাচাই।

    নীতি: v অবশ্যই str হতে হবে, দৈর্ঘ্য <= BROWSER_VOICE_MAX_LEN (120)।
    "" বৈধ — মানে "স্বয়ংক্রিয়"-তে ফিরে যাওয়া। বৈধ মান VERBATIM ফেরত
    দেওয়া হয় (strip করা হয় না): নামটা ব্যবহারকারীর ডিভাইস থেকে আসা
    voice name, JS-এ শুধু exact-name তুলনায় ব্যবহৃত হয় — quote/brace
    জাতীয় অক্ষর থাকলেও ক্ষতি নেই, JSON encoding সেটা সামলে নেয়।
    Returns (True, v) অথবা (False, plain-Bangla error message)।
    Pure function: কোনো I/O নেই, exception ছোঁড়ে না।
    """
    if not isinstance(v, str):
        return (False, BROWSER_VOICE_TYPE_ERROR)
    if len(v) > BROWSER_VOICE_MAX_LEN:
        return (False, BROWSER_VOICE_LEN_ERROR)
    return (True, v)


TTS_ENGINE_CHOICES = ("edge", "gemini", "browser")
TTS_ENGINE_ERROR = "কণ্ঠের ইঞ্জিন বাছাই করা গেল না — edge, gemini বা browser-এর একটা বেছে নাও।"

GEMINI_TTS_VOICES = {
    "Aoede": "আওয়েদে (উষ্ণ নারী কণ্ঠ)",
    "Kore": "কোরে (নারী কণ্ঠ)",
    "Leda": "লেডা (নারী কণ্ঠ)",
    "Callirrhoe": "ক্যালিরো (নারী কণ্ঠ)",
    "Puck": "পাক (পুরুষ কণ্ঠ)",
}
GEMINI_VOICE_ERROR = "Gemini গলা বাছাই করা গেল না — তালিকার গলাগুলো থেকেই একটা বেছে নাও।"


def validate_tts_engine(v):
    """TTS ইঞ্জিন যাচাই (v1.9.2)। ইনপুট: settings POST-এর data["tts_engine"]।

    শুধু হুবহু "edge"/"gemini"/"browser" বৈধ (কোনো case-folding নয়)।
    Returns (True, v) অথবা (False, plain-Bangla error)।
    Pure function: কোনো I/O নেই, exception ছোঁড়ে না।
    """
    if not isinstance(v, str):
        return (False, TTS_ENGINE_ERROR)
    if v in TTS_ENGINE_CHOICES:
        return (True, v)
    return (False, TTS_ENGINE_ERROR)


def validate_gemini_voice(v):
    """Gemini TTS গলার নাম যাচাই (v1.9.2)। ইনপুট: data["gemini_voice"]।

    validate_tts_voice-এর মতোই হুবহু whitelist মিল লাগবে — Gemini-র
    voice name case-sensitive।
    Returns (True, v) অথবা (False, plain-Bangla error)। Pure function।
    """
    if not isinstance(v, str):
        return (False, GEMINI_VOICE_ERROR)
    if v in GEMINI_TTS_VOICES:
        return (True, v)
    return (False, GEMINI_VOICE_ERROR)


def get_memory():
    mem = load_json(MEMORY_FILE, {})
    mem.setdefault("user_name", "মনির ভাইয়া")
    mem.setdefault("facts", [])
    mem.setdefault("likes", [])
    mem.setdefault("command_counts", {})
    mem.setdefault("interaction_count", 0)
    mem.setdefault("learned_notes", [])
    mem.setdefault("first_day", str(date.today()))
    return mem

# ------------------------------------------------------- #85 স্মৃতির ওজন
# ওজন আলাদা ফাইলে থাকে (fact_weights.json: {fact_text: weight}) যাতে
# memory.json-এর পুরোনো ফরম্যাট একদম না বদলায়। ডিফল্ট ওজন ১, সর্বোচ্চ ৯৯।
FACT_WEIGHTS_FILE = DATA / "fact_weights.json"
FACT_ARCHIVE_FILE = DATA / "fact_archive.json"


def _fact_weights_load():
    w = load_json(FACT_WEIGHTS_FILE, {})
    return w if isinstance(w, dict) else {}


def _fact_weights_save(w):
    try:
        save_json(FACT_WEIGHTS_FILE, w)
    except Exception:
        pass


def fact_weights_aligned(facts):
    """facts-এর ক্রম অনুযায়ী ওজনের parallel list (ডিফল্ট ১)।"""
    w = _fact_weights_load()
    out = []
    for f in facts or []:
        try:
            out.append(max(1, min(99, int(w.get(str(f), 1)))))
        except Exception:
            out.append(1)
    return out


def bump_fact_weights(fact_texts):
    """যেসব fact সত্যিই context/prompt-এ গেল, তাদের ওজন +১ (সর্বোচ্চ ৯৯)।"""
    if not fact_texts:
        return
    w = _fact_weights_load()
    changed = False
    for f in fact_texts:
        key = str(f)
        try:
            cur = int(w.get(key, 1))
        except Exception:
            cur = 1
        nw = min(99, cur + 1)
        if nw != cur or key not in w:
            w[key] = nw
            changed = True
    if changed:
        _fact_weights_save(w)


def _fact_weight_forget(fact_text):
    w = _fact_weights_load()
    if str(fact_text) in w:
        w.pop(str(fact_text), None)
        _fact_weights_save(w)


def get_version():
    ver = load_json(VERSION_FILE, {})
    ver.setdefault("version", "0.1.0")
    ver.setdefault("last_daily_release", str(date.today()))
    ver.setdefault("releases", [])
    return ver


def get_prompt():
    if PROMPT_FILE.exists():
        return PROMPT_FILE.read_text(encoding="utf-8")
    PROMPT_FILE.write_text(DEFAULT_PROMPT, encoding="utf-8")
    return DEFAULT_PROMPT


def get_pin():
    if PIN_FILE.exists():
        return PIN_FILE.read_text(encoding="utf-8").strip()
    pin = str(secrets.randbelow(900000) + 100000)
    PIN_FILE.write_text(pin, encoding="utf-8")
    return pin


def log_change(text):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    line = f"\n- [{stamp}] {text}"
    with CHANGELOG.open("a", encoding="utf-8") as f:
        if CHANGELOG.stat().st_size == 0:
            f.write("# Sokhi Desktop — Changelog\n")
        f.write(line + "\n")


def bump_version(kind="patch"):
    ver = get_version()
    major, minor, patch = (int(x) for x in ver["version"].split("."))
    if kind == "minor":
        minor, patch = minor + 1, 0
    else:
        patch += 1
    ver["version"] = f"{major}.{minor}.{patch}"
    save_json(VERSION_FILE, ver)
    return ver["version"]


def register_capability(name, desc):
    caps = load_json(CAPS_FILE, [])
    if not any(c.get("name") == name for c in caps):
        caps.append({"name": name, "desc": desc, "added": str(date.today())})
        save_json(CAPS_FILE, caps)


# ------------------------------------------------- self-upgrade: learning
# Sokhi learns from every answered question (knowledge cache) and keeps a
# list of questions she could NOT answer, so her daily self-upgrade can
# learn those too. This is how she gets smarter on her own, on Bhaiya's PC.

def _norm_q(text):
    q = re.sub(r"[^\w\u0980-\u09FF ]+", "", (text or "").lower()).strip()
    return re.sub(r"\s+", " ", q)


def knowledge_get(text):
    know = load_json(KNOW_FILE, {})
    return know.get(_norm_q(text))


def knowledge_put(text, answer):
    if not answer or len(answer) > 4000:
        return
    know = load_json(KNOW_FILE, {})
    know[_norm_q(text)] = {"q": text.strip(), "a": answer, "learned": str(date.today())}
    # keep the newest 500 learned answers
    if len(know) > 500:
        know = dict(list(know.items())[-500:])
    save_json(KNOW_FILE, know)


def log_unanswered(text):
    items = load_json(UNANS_FILE, [])
    key = _norm_q(text)
    for it in items:
        if it.get("key") == key:
            it["count"] = it.get("count", 1) + 1
            it["last"] = str(date.today())
            save_json(UNANS_FILE, items)
            return
    items.append({"key": key, "q": text.strip(), "count": 1, "last": str(date.today())})
    save_json(UNANS_FILE, items[-100:])


def apply_call_name(reply):
    """Bhaiya's own rule for Desktop Sokhi: she must NOT call him 'ভাইয়া'.
    If he set a call-name, use it; otherwise address him with no name."""
    try:
        name = (get_config().get("call_name") or "").strip()
        if name:
            return (reply.replace("মনির ভাইয়ার", name + "র")
                         .replace("মনির ভাইয়া", name)
                         .replace("ভাইয়ার", name + "র")
                         .replace("ভাইয়া", name))
        r = reply.replace("মনির ভাইয়ার", "তোমার").replace("ভাইয়ার", "তোমার")
        r = r.replace("ভাইয়া, ", "").replace("ভাইয়া,", "")
        r = r.replace(", ভাইয়া", "").replace(" ভাইয়া", "").replace("ভাইয়া", "")
        import re as _re
        r = _re.sub(r"\s+([,।!?])", r"\1", r)
        r = _re.sub(r" {2,}", " ", r)
        return r.strip(" ,")
    except Exception:
        return reply


def care_suffix(reply, hour=None, count=None):
    """Late-night care: after 11pm, Sokhi gently reminds Bhaiya to sleep,
    every few replies (wife-like care, never nagging every line)."""
    try:
        h = datetime.now().hour if hour is None else hour
        c = get_memory().get("interaction_count", 0) if count is None else count
        if h >= 23 and c % 4 == 0 and "ঘুম" not in reply:
            return reply + "\n\nঅনেক রাত হয়ে গেছে ভাইয়া… আজ আর না, এবার ঘুমিয়ে পড়ো। চোখেরও তো বিশ্রাম চাই। আমি আছি, কাল আবার একসাথে পড়ব। 🌙"
    except Exception:
        pass
    return reply


# ------------------------------------------------- voice speed helpers
# Single source of truth for TTS speed (v1.1.0, সমস্যা ২/৩ + F9).
# Final Edge rate formula (implemented in voice_identity(), TTS section):
#   final rate% = preset% + (voice_rate - 1) * 100 + mood_adjust%
#   then clamped to [-12%, +25%]
# so the TOTAL slowdown (preset + slider + emotional mood slowdown
# together) can never go below -12%, however the pieces stack.

def _parse_pct(value, default=0.0):
    """Parse a signed percent string like '-3%' / '+4%' (or a number) -> float."""
    try:
        if value is None:
            return float(default)
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value).strip().replace("%", "")
        return float(s) if s not in ("", "+", "-") else float(default)
    except Exception:
        return float(default)


def _fmt_pct(value):
    """Format a numeric percent the way edge-tts expects: '-3%', '+4%', '0%'."""
    v = int(round(float(value)))
    return f"+{v}%" if v > 0 else f"{v}%"


def _clamp_voice_rate(value, default=1.0):
    """Settings speed slider: float clamped to [0.8, 1.2]; junk -> default."""
    try:
        v = float(value)
    except Exception:
        return float(default)
    return max(0.8, min(1.2, v))


def self_upgrade():
    """Sokhi upgrades HERSELF: heals broken plugins, learns the answers to
    questions she previously could not answer (via the free Gemini brain),
    and returns a short report. Runs daily (inside the daily release)."""
    report = []
    # 1) plugin self-healing: test every plugin; quarantine the broken ones
    broken_dir = BASE / "plugins_broken"
    for f in sorted(PLUGINS.glob("plugin_*.py")):
        try:
            out = subprocess.run(
                [sys.executable, "-c",
                 f"import importlib.util; s=importlib.util.spec_from_file_location('p', r'{f}');"
                 "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print(m.self_test())"],
                capture_output=True, text=True, timeout=6)
            if out.returncode != 0 or "True" not in out.stdout:
                raise RuntimeError("self_test failed")
        except Exception:
            broken_dir.mkdir(exist_ok=True)
            shutil.move(str(f), str(broken_dir / f.name))
            report.append(f"নষ্ট স্কিল আলাদা করে রাখলাম: {f.name}")
            log_change(f"স্ব-মেরামত: নষ্ট প্লাগইন সরিয়ে রাখা হলো {f.name}")
    # 2) learn yesterday's unanswered questions
    items = load_json(UNANS_FILE, [])
    if items and get_config().get("gemini_api_key"):
        mem = get_memory()
        learned = 0
        remaining = []
        for it in items:
            if learned < 3:
                ans = ask_gemini(it["q"], mem)
                if ans:
                    knowledge_put(it["q"], ans)
                    learned += 1
                    continue
            remaining.append(it)
        if learned:
            save_json(UNANS_FILE, remaining)
            report.append(f"আগে জানতাম না এমন {learned}টা প্রশ্নের উত্তর শিখে নিলাম")
            log_change(f"স্ব-আপগ্রেড: {learned}টা নতুন উত্তর শেখা হলো")
    return report


def check_core_update():
    """Self-update of the core file, ONLY from a manifest URL Bhaiya sets
    (his future GitHub repo). Downloads, syntax-tests, backs up the old
    file, then replaces. No URL set = honest report, nothing happens."""
    url = (get_config().get("update_url") or "").strip()
    if not url:
        return "কোর আপডেটের ঠিকানা (GitHub) এখনো বসানো হয়নি ভাইয়া — GitHub ধাপটা হলে এটা নিজে থেকে চালু হবে।"
    try:
        manifest = json.loads(http_get(url, 15))
        remote_v = str(manifest.get("version", ""))
        file_url = str(manifest.get("url", ""))
        if not remote_v or not file_url or remote_v <= get_version()["version"]:
            return f"নতুন কোর ভার্সন নেই ভাইয়া — বর্তমান v{get_version()['version']}।"
        code = http_get(file_url, 30)
        if "Sokhi Desktop" not in code and "SOKHI DESKTOP" not in code:
            return "আপডেট ফাইলটা Sokhi-র বলে মনে হয়নি — বাতিল করলাম ভাইয়া।"
        new_file = DRAFTS / "sokhi_new.py"
        new_file.write_text(code, encoding="utf-8")
        test = subprocess.run([sys.executable, "-m", "py_compile", str(new_file)],
                              capture_output=True, text=True, timeout=15)
        if test.returncode != 0:
            return "নতুন কোর ফাইল টেস্টে পাস করেনি — বাতিল করলাম ভাইয়া, পুরোনোটাই চলছে।"
        code_bak = BACKUPS / "code"
        code_bak.mkdir(parents=True, exist_ok=True)
        shutil.copy2(BASE / "sokhi.py", code_bak / f"sokhi-{get_version()['version']}.py")
        shutil.copy2(new_file, BASE / "sokhi.py")
        (DATA / "restart-needed.txt").write_text(
            f"v{remote_v} বসানো হয়েছে — Sokhi বন্ধ করে আবার চালালেই নতুন ভার্সন চলবে।",
            encoding="utf-8")
        log_change(f"কোর স্ব-আপডেট: v{remote_v} ডাউনলোড, টেস্ট পাস, বসানো হলো (পুরোনোটা backup-এ)")
        return f"ভাইয়া, নিজেকে আপডেট করে নিলাম: নতুন কোর v{remote_v} বসানো হয়েছে। আমাকে একবার বন্ধ করে আবার চালালেই নতুন ভার্সন চলবে।"
    except Exception as e:
        return f"কোর আপডেট চেকে সমস্যা হলো ভাইয়া: {e}"


# ------------------------------------------------------------ web helpers

def http_get(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "SokhiDesktop/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")


def http_get_bytes(url, timeout=20):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def get_weather(city):
    try:
        url = "https://wttr.in/" + urllib.parse.quote(city) + "?format=j1"
        data = json.loads(http_get(url, 10))
        cur = data["current_condition"][0]
        return (f"ভাইয়া, {city}-তে এখন {cur['weatherDesc'][0]['value']}, "
                f"তাপমাত্রা {cur['temp_C']}°C (অনুভব হচ্ছে {cur['FeelsLikeC']}°C), "
                f"আর্দ্রতা {cur['humidity']}%, বাতাস {cur['windspeedKmph']} km/h।")
    except Exception:
        return "ভাইয়া, আবহাওয়ার তথ্য এখন আনতে পারলাম না — ইন্টারনেটটা একটু দেখবে?"


def get_news(limit=5):
    feeds = [
        ("BBC Bangla", "https://feeds.bbci.co.uk/bengali/rss.xml"),
        ("Prothom Alo", "https://www.prothomalo.com/feed"),
    ]
    items = []
    for name, url in feeds:
        try:
            root = ET.fromstring(http_get(url, 10))
            for it in root.iter("item"):
                t = it.findtext("title")
                if t:
                    items.append(f"• {t.strip()} ({name})")
                if len(items) >= limit:
                    break
        except Exception:
            continue
        if items:
            break
    if items:
        return "ভাইয়া, আজকের বড় খবরগুলো:\n" + "\n".join(items[:limit])
    return "ভাইয়া, খবরের ফিড এখন পাচ্ছি না। পরে আবার চেষ্টা করব।"


def web_search(query, limit=5):
    # Bing first (DuckDuckGo often shows a bot wall to scripts), DDG as fallback
    try:
        url = "https://www.bing.com/search?q=" + urllib.parse.quote(query)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=12) as r:
            html = r.read().decode("utf-8", errors="ignore")
        results = re.findall(r"<h2[^>]*><a[^>]*>(.*?)</a>", html, re.S)
        clean = [re.sub(r"<[^>]+>", "", x).strip() for x in results]
        clean = [c for c in clean if c][:limit]
        if clean:
            return ("ভাইয়া, ওয়েবে যা পেলাম:\n" +
                    "\n".join(f"{i+1}. {c}" for i, c in enumerate(clean)))
    except Exception:
        pass
    try:
        url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
        html = http_get(url, 12)
        results = re.findall(r'class="result__a"[^>]*>(.*?)</a>', html, re.S)
        clean = [re.sub(r"<[^>]+>", "", r).strip() for r in results]
        clean = [c for c in clean if c][:limit]
        if clean:
            return ("ভাইয়া, ওয়েবে যা পেলাম:\n" +
                    "\n".join(f"{i+1}. {c}" for i, c in enumerate(clean)))
        return "ভাইয়া, এই বিষয়ে ওয়েবে পরিষ্কার কিছু পেলাম না।"
    except Exception:
        return "ভাইয়া, ওয়েব সার্চ এখন কাজ করছে না — নেট সংযোগটা দেখবে?"


_last_gemini_error = {"info": ""}

# Latency measurement (v1.1, problem 4): the most recent ask_gemini() call.
# Keys: ms (total wall time of the call), model (the model that succeeded,
# or None), attempts (how many models were tried), quality (bool), ok (bool).
LAST_LATENCY = {}


# v1.8 #49: custom মডেল ব্যর্থ হলে চ্যাটে জানানোর নোটিশ (per-process)।
# ask_gemini() প্রতিবার শুরুতেই এটা খালি করে; জয়ী মডেল configured-এর
# থেকে আলাদা হলেই (শুধু custom mode-এ) এতে লেখা বসে।
LAST_MODEL_NOTICE = {"text": ""}


def _model_notice(configured, winning):
    """custom মডেল পাওয়া না গেলে চ্যাটে দেখানোর বাংলা নোটিশ।"""
    return (f"(নোট: তুমি বেছে দিয়েছিলে '{configured}' মডেল, কিন্তু সেটা এখন "
            f"পাওয়া যায়নি — তাই '{winning}' মডেল দিয়ে উত্তর দিলাম।)")


def _model_notice_for(cfg, configured, winning, attempted):
    """নোটিশ বসবে কি না ঠিক করে; বসলে লেখাটা ফেরত দেয়, নইলে ""।

    শর্ত (সবগুলো একসাথে): mode == "custom", configured ফাঁকা নয়,
    winning != configured, আর configured সত্যিই attempt হয়েছিল
    (attempted = যে model list-টা আসলে ঘোরানো হয়েছে)।"""
    if (cfg or {}).get("gemini_model_mode") != "custom":
        return ""
    if not configured or winning == configured:
        return ""
    if configured not in (attempted or []):
        return ""
    return _model_notice(configured, winning)


def _gemini_order(cfg, quality):
    """ask_gemini()-এর attempt order ফেরত দেয় (list, deduped)।

    auto (ডিফল্ট): v1.7.0-র হুবহু order —
        quality=True : (configured, 3.5-flash, 2.5-flash, 3.5-flash-lite)
        quality=False: (3.5-flash-lite, configured, 3.5-flash), cap 3
    custom: configured সবার আগে, তারপর ওই পথের বাকি মডেলগুলো আগের
        relative order-এই; dedupe; fast path-এ cap 3 আগের মতোই।
    অজানা mode মান auto হিসেবেই ধরা হয় (defensive)।"""
    cfg = cfg or {}
    configured = cfg.get("gemini_model", "gemini-3.8-flash")
    if quality:
        base = (configured, "gemini-3.5-flash", "gemini-2.5-flash",
                "gemini-3.5-flash-lite")
    else:
        base = ("gemini-3.5-flash-lite", configured, "gemini-3.5-flash")
    if cfg.get("gemini_model_mode") == "custom":
        order = (configured,) + tuple(m for m in base if m != configured)
    else:
        order = base
    models = []
    for m in order:
        if m and m not in models:
            models.append(m)
    if not quality:
        models = models[:3]
    return models


def _log_gemini_error(model, err):
    info = f"model={model} error={err}"
    _last_gemini_error["info"] = info
    try:
        with (DATA / "gemini-error.log").open("a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {info}\n")
    except Exception:
        pass


def ask_gemini(user_text, mem, quality=False, image=None):
    """Smart brain — Gemini FREE tier only. Tries free models so one
    model's limit/overload does not drop Sokhi back to her offline brain.
    The real error is logged (never the key itself) so failures can be
    diagnosed instead of guessed.

    Latency (v1.1, problem 4): by default the FASTEST free model goes
    first and each attempt times out after 12s (max 3 attempts, so a
    stuck/limited model can no longer stack up ~120s of waiting).
    quality=True keeps the OLD order (configured model first, then the
    original backups) and the full 1024-token budget — use it for
    quality-sensitive calls (teacher steps, exam-question generation).
    Every call records its total ms + winning model in LAST_LATENCY."""
    LAST_MODEL_NOTICE["text"] = ""
    _t0 = time.perf_counter()

    def _record(model, attempts, ok):
        LAST_LATENCY.clear()
        LAST_LATENCY.update({
            "ms": int((time.perf_counter() - _t0) * 1000),
            "model": model, "attempts": attempts,
            "quality": bool(quality), "ok": bool(ok),
        })

    cfg = get_config()
    key = (cfg.get("gemini_api_key") or "").strip()
    if not key:
        _record(None, 0, False)
        return None
    facts = "; ".join(mem.get("facts", [])[-10:])
    try:
        bump_fact_weights(list(mem.get("facts", [])[-10:]))
    except Exception:
        pass
    likes = ", ".join(mem.get("likes", [])[-10:])
    system = get_prompt() + f"\nমনে থাকা তথ্য: {facts}\nপছন্দ: {likes}"
    _layered = layered_memory_block(mem)
    if _layered:
        system += "\n" + _layered
    _name = (get_config().get("call_name") or "").strip()
    if _name:
        system += (f"\n\n[ডাকনামের নিয়ম — সবচেয়ে জরুরি, আগের সব নির্দেশের উপরে] "
                   f"তুমি তাকে '{_name}' বলে ডাকবে। 'ভাইয়া' বা 'মনির ভাইয়া' কখনোই বলবে না।")
    else:
        system += ("\n\n[ডাকনামের নিয়ম — সবচেয়ে জরুরি, আগের সব নির্দেশের উপরে] "
                   "তুমি তাকে কোনো নামে ডাকবে না — 'ভাইয়া' বা 'মনির ভাইয়া' বলবে না; "
                   "শুধু তুমি-রূপে, নাম ছাড়া কথা বলবে।")
    _style = (cfg.get("reply_style") or "স্বাভাবিক").strip()
    if _style == "সংক্ষেপ":
        system += "\nউত্তর খুব সংক্ষেপে, ১-৩ বাক্যে দাও।"
    elif _style == "বিস্তারিত":
        system += "\nউত্তর বিস্তারিতভাবে, ধাপে ধাপে দাও।"
    _lang = (cfg.get("reply_language") or "বাংলা").strip()
    if _lang == "Banglish":
        system += "\nউত্তর Banglish-এ দাও — বাংলা কথা, কিন্তু ল্যাটিন (ইংরেজি) হরফে লেখা; সহজ ও স্বাভাবিক ভঙ্গিতে।"
    elif _lang == "English":
        system += "\nReply in simple, clear English only."
    _contents = gemini_contents(user_text)
    if image:
        try:
            _img = image
            if isinstance(_img, str):
                # data-URL string: data:<mime>;base64,<data>
                _m = re.match(r"data:([^;]+);base64,(.*)", _img, re.S)
                if _m:
                    _img = {"mime_type": _m.group(1), "data": _m.group(2).strip()}
                else:
                    _img = {"mime_type": "image/png", "data": _img}
            _mime = str(_img.get("mime_type") or _img.get("mime") or "image/png")
            _data = str(_img.get("data") or "")
            if _data and _contents:
                _contents[-1]["parts"].append(
                    {"inline_data": {"mime_type": _mime, "data": _data}})
        except Exception:
            pass
    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": _contents,
        # 700 tokens is plenty for everyday chat and returns sooner;
        # quality calls keep the full 1024 for long teacher-style answers.
        "generationConfig": {"temperature": 0.4,
                             "maxOutputTokens": 1024 if quality else 700},
    }
    configured = cfg.get("gemini_model", "gemini-3.8-flash")
    models = _gemini_order(cfg, quality)
    attempts = 0
    for model in models:
        attempts += 1
        url = ("https://generativelanguage.googleapis.com/v1beta/models/"
               f"{model}:generateContent")
        req = urllib.request.Request(
            url, data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": key},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=12) as r:
                data = json.loads(r.read().decode("utf-8"))
            text_out = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            _record(model, attempts, True)
            _notice = _model_notice_for(cfg, configured, model, models)
            if _notice:
                LAST_MODEL_NOTICE["text"] = _notice
            return text_out
        except Exception as e:
            detail = str(e)
            try:
                if hasattr(e, "read"):
                    detail += " " + e.read().decode("utf-8", errors="ignore")[:200]
            except Exception:
                pass
            _log_gemini_error(model, detail)
            continue
    _record(None, attempts, False)
    return None


# -*- coding: utf-8 -*-
# =====================================================================
#  Desktop Sokhi v1.0 — শিক্ষক মোড + টাইমড মক টেস্ট + হোয়াইটবোর্ড
#  teacher_fragment.py — sokhi.py-তে পেস্ট-যোগ্য ফ্র্যাগমেন্ট
# =====================================================================
#  পেস্ট করার জায়গা: sokhi.py-তে ask_gemini()-এর পরে, handle_message()-এর
#  আগে (বা ফাইলের যেকোনো টপ-লেভেল জায়গায়, handle_message-এর আগে হলেই হলো)।
#
#  ব্যবহারযোগ্য গ্লোবাল (sokhi.py থেকে আসে): json, re, time, date, datetime,
#  Path, DATA, load_json, save_json, get_memory, ask_gemini, get_config
#
#  handle_message()-এ সংযোগের নমুনা (সাধারণ Gemini-কলের ঠিক আগে বসাবে):
#
#      # --- পরীক্ষা চলমান থাকলে উত্তরটা আগে পরীক্ষায় যাক
#      if exam_active():
#          return exam_answer(text)
#      # --- শিক্ষক মোড
#      _teach = teacher_handle(text, low)
#      if _teach:
#          return _teach
#
#  আর HTTP API-তে (UI-এর জন্য) exam_api(data) কল করলেই চলবে:
#      data = {"action": "start", "subject": "গণিত", "count": 10, "minutes": 10}
#      data = {"action": "answer", "text": "ক"}
#      data = {"action": "finish"}  /  {"action": "status"}
#
#  নিজের state ফাইলসমূহ (সব DATA-র ভিতরে):
#    study-session.json   — চলমান শিক্ষক-সেশন
#    study-progress.json  — বিষয়ভিত্তিক অগ্রগতি {sessions, last_topic, weak[]}
#    exam-session.json    — চলমান মক টেস্ট
#    study-wrong-book.json— ভুল করা প্রশ্নের খাতা (append-only list)
#    whiteboard.json      — হোয়াইটবোর্ডের লাইন (সর্বোচ্চ ৬০)
#
#  ভাষা-নিয়ম: সহজ বাংলা, ছোট ধাপ, সম্বোধন ছাড়া / তুমি-ভঙ্গি ('ভাইয়া' নয়)।
# =====================================================================

_STUDY_SESSION_FILE = DATA / "study-session.json"
_STUDY_PROGRESS_FILE = DATA / "study-progress.json"
_EXAM_SESSION_FILE = DATA / "exam-session.json"
_WRONG_BOOK_FILE = DATA / "study-wrong-book.json"
_WHITEBOARD_FILE = DATA / "whiteboard.json"

_BN_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
_EN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
_OPT_LETTERS = ["ক", "খ", "গ", "ঘ"]


def _bn_num(x):
    """ইংরেজি সংখ্যা -> বাংলা সংখ্যা (দেখানোর জন্য)।"""
    return str(x).translate(_BN_DIGITS)


def _norm_num_text(s):
    """বাংলা সংখ্যা -> ইংরেজি সংখ্যা (তুলনার জন্য)।"""
    return str(s or "").translate(_EN_DIGITS)


def _study_save(path, obj):
    try:
        DATA.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    save_json(path, obj)


def _study_delete(path):
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


def _gemini_or_none(prompt):
    """ask_gemini-কে নিরাপদে ডাকে; key না থাকলে/ব্যর্থ হলে None।
    v1.1: এই wrapper-এর সব কলকারীই গুণগত-সংবেদনশীল (শিক্ষক, পরীক্ষা,
    এজেন্ট-সারসংক্ষেপ, কোডিং) — তাই সবসময় quality=True পথে যায়, যাতে
    লম্বা JSON/ধাপ 700-token সীমায় কাটা না পড়ে। সাধারণ চ্যাট সরাসরি
    ask_gemini ডাকে (fast পথ)।"""
    try:
        mem = get_memory()
    except Exception:
        mem = {}
    try:
        out = ask_gemini(prompt, mem, quality=True)
    except Exception:
        return None
    if out and str(out).strip():
        return str(out).strip()
    return None


# =====================================================================
#  ১) হোয়াইটবোর্ড
# =====================================================================

def wb_add(text):
    """বোর্ডে লেখে। মাল্টি-লাইন লেখা লাইন ধরে ভাগ হয়ে যায়।
    সর্বোচ্চ ৬০ লাইন রাখে (পুরোনোগুলো ঝরে পড়ে)।"""
    lines = load_json(_WHITEBOARD_FILE, [])
    if not isinstance(lines, list):
        lines = []
    for ln in str(text or "").splitlines():
        ln = ln.strip()
        if ln:
            lines.append(ln)
    lines = lines[-60:]
    _study_save(_WHITEBOARD_FILE, lines)
    return lines


def wb_lines():
    """বোর্ডের বর্তমান লাইনগুলোর list ফেরত দেয়।"""
    lines = load_json(_WHITEBOARD_FILE, [])
    return lines if isinstance(lines, list) else []


def wb_clear():
    """বোর্ড পরিষ্কার করে।"""
    _study_save(_WHITEBOARD_FILE, [])
    return []


# =====================================================================
#  বিষয় শনাক্তকরণ (শিক্ষক + পরীক্ষা দুজনেই ব্যবহার করে)
# =====================================================================

_SUBJECT_ALIASES = [
    ("বাংলা সাহিত্য", ["বাংলা সাহিত্য", "সাহিত্য", "literature"]),
    ("বাংলা ব্যাকরণ", ["বাংলা ব্যাকরণ", "ব্যাকরণ", "ব্যাকরন", "grammar"]),
    ("গণিত", ["গণিত", "অংক", "অঙ্ক", "math", "maths"]),
    ("ইংরেজি", ["ইংরেজি", "ইংরেজী", "english"]),
    ("সাধারণ জ্ঞান", ["সাধারণ জ্ঞান", "সাধারন জ্ঞান", "সাধারণজ্ঞান",
                    "general knowledge", "gk", "জিকে"]),
    ("ICT", ["ict", "আইসিটি", "আইসিটি", "তথ্য প্রযুক্তি",
             "তথ্যপ্রযুক্তি", "কম্পিউটার"]),
]

SUBJECTS = [s for s, _ in _SUBJECT_ALIASES]

_DEFAULT_TOPICS = {
    "বাংলা সাহিত্য": "বাংলা সাহিত্যের যুগবিভাগ ও চর্যাপদ (বেসিক)",
    "বাংলা ব্যাকরণ": "ধ্বনি ও বর্ণ (বেসিক)",
    "গণিত": "ভগ্নাংশ (বেসিক)",
    "ইংরেজি": "Parts of Speech (বেসিক)",
    "সাধারণ জ্ঞান": "বাংলাদেশ পরিচিতি (বেসিক)",
    "ICT": "কম্পিউটারের বেসিক (ইনপুট-আউটপুট)",
}


def _detect_subject(text, low=None):
    """লেখা থেকে বিষয়ের প্রমিত (canonical) নাম বের করে; না মিললে None।"""
    low = (low if low is not None else str(text or "").lower())
    raw = str(text or "")
    for canon, aliases in _SUBJECT_ALIASES:
        for a in aliases:
            if a in raw or a in low:
                return canon
    return None


def _update_progress(subject, topic=None, weak_topics=None, add_sessions=0,
                     add_steps=0, add_exams=0):
    """study-progress.json-এ বিষয়ভিত্তিক অগ্রগতি আপডেট করে।"""
    prog = load_json(_STUDY_PROGRESS_FILE, {})
    if not isinstance(prog, dict):
        prog = {}
    ent = prog.get(subject) or {}
    ent.setdefault("sessions", 0)
    ent.setdefault("last_topic", "")
    ent.setdefault("weak", [])
    ent.setdefault("total_steps", 0)
    ent.setdefault("mock_tests", 0)
    ent.setdefault("last_date", "")
    ent["sessions"] += int(add_sessions or 0)
    ent["total_steps"] += int(add_steps or 0)
    ent["mock_tests"] += int(add_exams or 0)
    if topic:
        ent["last_topic"] = topic
    for w in (weak_topics or []):
        if w and w not in ent["weak"]:
            ent["weak"].append(w)
    ent["weak"] = ent["weak"][-20:]
    ent["last_date"] = str(date.today())
    prog[subject] = ent
    _study_save(_STUDY_PROGRESS_FILE, prog)
    return ent


# =====================================================================
#  অফলাইন পাঠ (Gemini key না থাকলে) — এক ধাপ + যাচাই-প্রশ্ন + উত্তর-চাবি
#  প্রতিটা step: {topic, text, check_q, check_answers[], alt}
# =====================================================================

OFFLINE_LESSONS = {
    "গণিত": [
        {
            "topic": "ভগ্নাংশ",
            "text": ("ধাপ: ভগ্নাংশ মানে কোনো জিনিসকে সমান ভাগে ভাগ করে তার "
                     "কয়েক ভাগ নেওয়া। যেমন একটা রুটি ২ সমান ভাগ করলে এক "
                     "ভাগ = ১/২। উপরের সংখ্যাটাকে বলে লব, নিচেরটাকে হর।"),
            "check_q": "তাহলে বলো তো — ৩/৪ ভগ্নাংশে লব কত?",
            "check_answers": ["৩", "3", "তিন"],
            "alt": ("আরেকটা উদাহরণে বুঝি: একটা কেক ৪টা সমান টুকরো করা হলো। "
                    "তুমি ১ টুকরো নিলে পেলে ১/৪ ভাগ, ৩ টুকরো নিলে ৩/৪ ভাগ। "
                    "নিচের সংখ্যা (হর) বলে মোট কয় ভাগ করা হয়েছে, উপরেরটা "
                    "(লব) বলে কয় ভাগ নেওয়া হয়েছে।"),
        },
        {
            "topic": "ভগ্নাংশের যোগ",
            "text": ("ধাপ: হর একই হলে ভগ্নাংশ যোগ করা খুব সহজ — শুধু লব দুটো "
                     "যোগ হয়, হর যেমন ছিল তেমনি থাকে। যেমন ১/৪ + ২/৪ = ৩/৪।"),
            "check_q": "বলো তো — ২/৫ + ১/৫ = কত?",
            "check_answers": ["৩/৫", "3/5"],
            "alt": ("অন্য উদাহরণ: একটা পিৎজা ৬ ভাগ করা। সকালে ১ ভাগ, দুপুরে "
                    "২ ভাগ খেলে মোট ৩/৬ ভাগ খাওয়া হলো — হর ৬-ই রইল, লব শুধু "
                    "১+২=৩ হলো। ঠিক এভাবেই হর এক থাকলে শুধু লব যোগ হয়।"),
        },
        {
            "topic": "শতকরা (বেসিক)",
            "text": ("ধাপ: শতকরা মানে '১০০-এর মধ্যে কত'। ৫০% মানে ১০০-এর "
                     "মধ্যে ৫০, মানে ঠিক অর্ধেক। কোনো সংখ্যার শতকরা বের "
                     "করতে: সংখ্যা × শতকরা ÷ ১০০। যেমন ২০০-এর ৫০% = "
                     "২০০ × ৫০ ÷ ১০০ = ১০০।"),
            "check_q": "বলো তো — ৩০০-এর ১০% কত?",
            "check_answers": ["৩০", "30"],
            "alt": ("সহজ করে ভাবো: ১০% মানে প্রতি ১০০ টাকায় ১০ টাকা। "
                    "৩০০ টাকা মানে তিনটা ১০০ — তাই ১০+১০+১০ = ৩০। যেকোনো "
                    "সংখ্যার ১০% পেতে শুধু এক ঘর দশমিক বামে সরালেই হয়।"),
        },
    ],
    "বাংলা ব্যাকরণ": [
        {
            "topic": "ধ্বনি ও বর্ণ",
            "text": ("ধাপ: মুখে উচ্চারিত আওয়াজকে বলে ধ্বনি, আর সেই ধ্বনি "
                     "লেখার চিহ্নকে বলে বর্ণ। 'অ, আ, ই' এগুলো স্বরবর্ণ — "
                     "এরা অন্যের সাহায্য ছাড়াই উচ্চারিত হয়। বাংলা বর্ণমালায় "
                     "স্বরবর্ণ ১১টি।"),
            "check_q": "বলো তো — 'ক' কোন ধরনের বর্ণ?",
            "check_answers": ["ব্যঞ্জনবর্ণ", "ব্যঞ্জন"],
            "alt": ("অন্যভাবে বুঝি: 'অ' বলতে গেলে মুখ থেকে সরাসরি আওয়াজ "
                    "বের হয়, কারও সাহায্য লাগে না — তাই স্বরবর্ণ। কিন্তু "
                    "'ক' বলতে আসলে 'ক্ + অ' লাগে, একা উচ্চারণ হয় না — "
                    "তাই এটা ব্যঞ্জনবর্ণ।"),
        },
        {
            "topic": "সন্ধি",
            "text": ("ধাপ: পাশাপাশি দুটো ধ্বনির মিলনকে বলে সন্ধি। যেমন "
                     "বিদ্যা + আলয় = বিদ্যালয়। পরীক্ষায় সন্ধি বিচ্ছেদ "
                     "আসে খুব বেশি, তাই শব্দটা ভেঙে দুটো অর্থপূর্ণ অংশ "
                     "খোঁজাই কৌশল।"),
            "check_q": "বলো তো — 'হিমালয়' শব্দের সন্ধি বিচ্ছেদ কী?",
            "check_answers": ["হিম + আলয়", "হিম+আলয়", "হিম আলয়"],
            "alt": ("অন্য উদাহরণ: দেব + আলয় = দেবালয়। মানে 'দেবের আলয় "
                    "(ঘর)'। ঠিক তেমনই হিম (বরফ) + আলয় (ঘর) = হিমালয়, "
                    "বরফের ঘর। অংশ দুটোর আলাদা অর্থ থাকলেই সন্ধি ঠিক আছে।"),
        },
        {
            "topic": "কারক (অপাদান)",
            "text": ("ধাপ: ক্রিয়ার সঙ্গে নামপদের সম্পর্কই কারক। কোথা থেকে "
                     "কিছু আসে/সরে/পড়ে বোঝালে অপাদান কারক। যেমন 'সে ঢাকা "
                     "থেকে এলো' — 'ঢাকা থেকে' অপাদান কারক। চেনার উপায়: "
                     "'থেকে / হতে / চেয়ে' থাকলেই অপাদান ভাবো।"),
            "check_q": "বলো তো — 'গাছ থেকে পাতা পড়ে' বাক্যে 'গাছ থেকে' কোন কারক?",
            "check_answers": ["অপাদান"],
            "alt": ("আরেকটা উদাহরণ: 'মেঘ থেকে বৃষ্টি পড়ে' — বৃষ্টি আসছে "
                    "মেঘ থেকে, তাই 'মেঘ থেকে' অপাদান কারক। 'থেকে' শব্দটা "
                    "দেখলেই অপাদান — এটাই সহজ চেনার উপায়।"),
        },
    ],
    "বাংলা সাহিত্য": [
        {
            "topic": "চর্যাপদ",
            "text": ("ধাপ: বাংলা সাহিত্যের সবচেয়ে পুরোনো নিদর্শন চর্যাপদ — "
                     "বৌদ্ধ সিদ্ধাচার্যদের লেখা গানের সংকলন। এটি আবিষ্কার "
                     "করেন মহামহোপাধ্যায় হরপ্রসাদ শাস্ত্রী, নেপালের রাজদরবারের "
                     "গ্রন্থাগার থেকে (১৯০৭ সালে)।"),
            "check_q": "বলো তো — চর্যাপদ কে আবিষ্কার করেন?",
            "check_answers": ["হরপ্রসাদ শাস্ত্রী", "হরপ্রসাদ"],
            "alt": ("মনে রাখার কৌশল: 'চর্যা' মানে আচরণ/সাধনার পদ্ধতি। "
                    "নেপাল থেকে হরপ্রসাদ শাস্ত্রী এটি খুঁজে পান — নামের "
                    "'শাস্ত্রী' আর 'চর্যাপদ' একসঙ্গে জোড়া দিয়ে মনে রাখো।"),
        },
        {
            "topic": "সাহিত্যের যুগবিভাগ",
            "text": ("ধাপ: বাংলা সাহিত্যের ইতিহাস তিন যুগে ভাগ করা হয় — "
                     "প্রাচীন যুগ (চর্যাপদের সময়), মধ্যযুগ (মঙ্গলকাব্য, "
                     "শ্রীকৃষ্ণকীর্তন), আর আধুনিক যুগ (ঊনবিংশ শতাব্দী থেকে)। "
                     "যুগের ধারাটা এভাবে মনে রাখো: চর্যা → মঙ্গল → আধুনিক।"),
            "check_q": "বলো তো — মঙ্গলকাব্য কোন যুগের সাহিত্য?",
            "check_answers": ["মধ্যযুগ"],
            "alt": ("অন্যভাবে: প্রাচীন = চর্যাপদ (গান), মধ্য = মঙ্গলকাব্য "
                    "(দেবদেবীর মাহাত্ম্যের কাব্য), আধুনিক = গদ্য, উপন্যাস, "
                    "ছোটগল্পের যুগ। শব্দের ধরন দেখেই যুগ চেনা যায়।"),
        },
    ],
    "ইংরেজি": [
        {
            "topic": "Parts of Speech — Noun",
            "text": ("Step: A noun is the name of a person, place or thing — "
                     "যেমন Dhaka, teacher, book. বাক্যে 'কে / কী / কোন "
                     "জায়গা' প্রশ্ন করলে যে উত্তর পাওয়া যায়, সেটাই noun।"),
            "check_q": "বলো তো — 'She lives in Khulna' বাক্যে noun কোনটি?",
            "check_answers": ["khulna", "খুলনা"],
            "alt": ("Another example: 'Rahim reads a book.' — Rahim (মানুষের "
                    "নাম) আর book (জিনিসের নাম) দুটোই noun। lives বা reads "
                    "হলো কাজ, তাই সেগুলো verb।"),
        },
        {
            "topic": "Tense — Present Indefinite",
            "text": ("Step: চিরসত্য বা অভ্যাস বোঝালে Present Indefinite Tense "
                     "হয়। গঠন: Subject + verb-এর মূল রূপ। যেমন 'The sun "
                     "rises in the east.' — সূর্য প্রতিদিনই ওঠে, তাই মূল "
                     "রূপের verb।"),
            "check_q": "বলো তো — 'He ___ to school every day.' শূন্যস্থানে কী বসবে: go নাকি goes?",
            "check_answers": ["goes"],
            "alt": ("কৌশল: He/She/It থাকলে verb-এর সঙ্গে s/es যোগ হয় — "
                    "He goes, She reads। কিন্তু I/We/They থাকলে মূল রূপই "
                    "থাকে — They go। 'every day' দেখলেই বুঝবে এটা অভ্যাস, "
                    "মানে Present Indefinite।"),
        },
    ],
    "সাধারণ জ্ঞান": [
        {
            "topic": "মুক্তিযুদ্ধ — সেক্টর",
            "text": ("ধাপ: ১৯৭১ সালের মুক্তিযুদ্ধে পুরো বাংলাদেশকে ১১টি "
                     "সেক্টরে ভাগ করা হয়েছিল, প্রতিটিতে একজন সেক্টর "
                     "কমান্ডার ছিলেন। এই '১১টি সেক্টর' প্রশ্নটা প্রায় সব "
                     "চাকরির পরীক্ষায় ঘোরে।"),
            "check_q": "বলো তো — মুক্তিযুদ্ধে বাংলাদেশ কয়টি সেক্টরে বিভক্ত ছিল?",
            "check_answers": ["১১", "11", "এগারো"],
            "alt": ("মনে রাখো: ১১ জন সেক্টর কমান্ডার, ১১টি সেক্টর। আরেকটা "
                    "জোড়া তথ্য — মুক্তিযুদ্ধ শুরু ২৬ মার্চ (স্বাধীনতা দিবস), "
                    "বিজয় ১৬ ডিসেম্বর। তারিখ দুটো একসঙ্গে মনে রাখো।"),
        },
        {
            "topic": "জাতীয় বিষয়",
            "text": ("ধাপ: বাংলাদেশের জাতীয় ফল কাঁঠাল, জাতীয় ফুল শাপলা, "
                     "জাতীয় পাখি দোয়েল, জাতীয় মাছ ইলিশ, জাতীয় পশু রয়েল "
                     "বেঙ্গল টাইগার। এই পাঁচটা একটা সেট হিসেবে মুখস্থ করো — "
                     "পরীক্ষায় যেকোনো একটা আসতে পারে।"),
            "check_q": "বলো তো — বাংলাদেশের জাতীয় মাছ কোনটি?",
            "check_answers": ["ইলিশ"],
            "alt": ("ছড়ার মতো মনে রাখো: ফলে কাঁঠাল, ফুলে শাপলা, পাখিতে "
                    "দোয়েল, মাছে ইলিশ, পশুতে বাঘ। পাঁচটা এক লাইনে বলতে "
                    "পারলেই এই টপিক শেষ।"),
        },
    ],
    "ICT": [
        {
            "topic": "ইনপুট-আউটপুট ডিভাইস",
            "text": ("ধাপ: যেসব যন্ত্র দিয়ে কম্পিউটারে তথ্য ঢোকানো হয় "
                     "সেগুলো ইনপুট ডিভাইস — কিবোর্ড, মাউস, স্ক্যানার। আর "
                     "ফলাফল যেখানে দেখা/শোনা যায় সেগুলো আউটপুট — মনিটর, "
                     "প্রিন্টার, স্পিকার।"),
            "check_q": "বলো তো — প্রিন্টার কোন ধরনের ডিভাইস?",
            "check_answers": ["আউটপুট", "output"],
            "alt": ("অন্য উদাহরণ: মাইক্রোফোনে কথা বলা মানে তথ্য ঢুকছে "
                    "(ইনপুট), স্পিকারে গান শোনা মানে তথ্য বের হচ্ছে "
                    "(আউটপুট)। 'ঢুকছে না বের হচ্ছে' — এই এক প্রশ্নেই সব "
                    "ডিভাইস আলাদা করা যায়।"),
        },
        {
            "topic": "CPU",
            "text": ("ধাপ: CPU-এর পূর্ণরূপ Central Processing Unit — একে "
                     "কম্পিউটারের 'মস্তিষ্ক' বলা হয়, কারণ সব হিসাব-নিকাশ "
                     "আর নির্দেশ পালনের কাজ এখানেই হয়।"),
            "check_q": "বলো তো — CPU-কে কম্পিউটারের কী বলা হয়?",
            "check_answers": ["মস্তিষ্ক", "মগজ", "brain"],
            "alt": ("ভাবো কম্পিউটার একটা অফিস: কিবোর্ড চিঠি ঢোকায়, মনিটর "
                    "ফল দেখায়, কিন্তু সিদ্ধান্ত নেয় বস — সেই বসই CPU। "
                    "তাই একে মস্তিষ্ক বলা হয়।"),
        },
    ],
}


def _offline_step(subject, idx):
    steps = OFFLINE_LESSONS.get(subject) or []
    if not steps:
        return None
    return steps[idx % len(steps)]


# =====================================================================
#  ২) শিক্ষক মোড — teacher_handle(text, low)
# =====================================================================

_TEACH_START_WORDS = ("শেখাও", "পড়াও", "শিখতে চাই", "পড়তে চাই",
                      "শেখা শুরু", "পড়া শুরু", "শিক্ষক মোড", "টিচার মোড",
                      "teacher mode", "teach me")
_TEACH_END_WORDS = ("শেখানো শেষ", "শেখা শেষ", "পড়া শেষ", "আজ থাক",
                    "আজকে থাক", "শেষ করো", "থামো")
_TEACH_UNDERSTOOD = ("বুঝেছি", "বুঝলাম", "বুঝতে পেরেছি", "বুঝে গেছি",
                     "বুঝছি", "clear", "বুঝেছি।")
_TEACH_NOT_UNDERSTOOD = ("বুঝিনি", "বুঝি নাই", "বুঝতে পারিনি", "বুঝলাম না",
                         "আবার বোঝাও", "আবার বলো", "আবার বুঝিয়ে",
                         "আস্তে", "কঠিন লাগছে", "বুঝতে কষ্ট")


def _load_teacher_session():
    s = load_json(_STUDY_SESSION_FILE, None)
    return s if isinstance(s, dict) and s.get("subject") else None


def _teacher_gemini_prompt(subject, topic, step_no, kind, extra=""):
    base = (f"তুমি এখন শিক্ষক মোডে আছ। ছাত্র বাংলাদেশের সরকারি চাকরির "
            f"(গ্রেড ১৬-২০) পরীক্ষার্থী, বেসিক থেকে শিখছে। বিষয়: {subject}। "
            f"টপিক: {topic}। কঠোর নিয়ম: একবারে মাত্র একটা ছোট্ট ধাপ শেখাবে "
            f"(সর্বোচ্চ ৪-৫ লাইন সহজ বাংলা, একটা সহজ উদাহরণসহ), ধাপের শেষে "
            f"আলাদা লাইনে 'যাচাই:' লিখে একটাই ছোট প্রশ্ন করবে। এর বাইরে "
            f"ভূমিকা/শুভেচ্ছা কিছু লিখবে না, 'ভাইয়া' বলবে না।")
    if kind == "next":
        return base + f"\nএখন ধাপ নম্বর {_bn_num(step_no)} শেখাও। {extra}"
    if kind == "again":
        return (base + "\nছাত্র আগের ধাপটা বোঝেনি। একই ধাপটা এবার সম্পূর্ণ "
                "আলাদা, আরও সহজ উদাহরণ দিয়ে আবার বোঝাও।")
    if kind == "judge":
        return (base + f"\nআগের ধাপ ছিল:\n{extra}\nছাত্র যাচাই-প্রশ্নের উত্তর "
                "দিয়েছে। উত্তর ঠিক হলে উত্তরের প্রথম লাইনে '✅ ঠিক হয়েছে!' "
                "লিখে তারপর পরের ছোট্ট ধাপটা শেখাও। ভুল হলে প্রথম লাইনে "
                "'❌ একটু ভুল হয়েছে' লিখে সঠিক উত্তরটা সহজে বুঝিয়ে দিয়ে "
                "শেষে আবার একটা ছোট 'যাচাই:' প্রশ্ন করো।")
    return base


def _teacher_step_text(session, kind, student_answer=""):
    """এক ধাপের লেখা তৈরি করে (Gemini থাকলে Gemini, নাহলে অফলাইন পাঠ)।
    kind: 'first' | 'next' | 'again' | 'judge'
    ফেরত: (text, was_correct_or_None)"""
    subject = session["subject"]
    topic = session.get("topic") or _DEFAULT_TOPICS.get(subject, "")
    step_no = int(session.get("step", 1))

    # --- Gemini থাকলে সেটাই শিক্ষক
    if kind in ("first", "next"):
        out = _gemini_or_none(_teacher_gemini_prompt(
            subject, topic, step_no, "next"))
        if out:
            session["mode"] = "gemini"
            return out, None
    elif kind == "again":
        out = _gemini_or_none(_teacher_gemini_prompt(
            subject, topic, step_no, "again"))
        if out:
            session["mode"] = "gemini"
            return out, None
    elif kind == "judge":
        out = _gemini_or_none(_teacher_gemini_prompt(
            subject, topic, step_no, "judge",
            extra=(f"{session.get('last_step', '')}\n"
                   f"ছাত্রের উত্তর: {student_answer}")))
        if out:
            session["mode"] = "gemini"
            ok = True if "✅" in out[:40] or "ঠিক হয়েছে" in out[:60] else \
                (False if "❌" in out[:40] or "ভুল হয়েছে" in out[:60] else None)
            return out, ok

    # --- অফলাইন ফলব্যাক
    session["mode"] = "offline"
    idx = int(session.get("offline_idx", 0))
    step = _offline_step(subject, idx)
    if step is None:
        return (f"বিষয়: {subject} — এই বিষয়ের অফলাইন পাঠ এখনো তৈরি হয়নি। "
                "Gemini key থাকলে অনলাইনে শেখানো যাবে। অন্য কোনো বিষয় "
                "বললে শুরু করছি।", None)
    session["topic"] = step["topic"]
    if kind == "again":
        body = step.get("alt") or step["text"]
        return (f"ঠিক আছে, আস্তে আস্তে আরেকভাবে বুঝি।\n{body}\n"
                f"যাচাই: {step['check_q']}"), None
    if kind == "judge":
        low_ans = (student_answer or "").lower()
        raw_ans = _norm_num_text(student_answer or "")
        hit = any((a.lower() in low_ans) or (a in student_answer) or
                  (_norm_num_text(a) in raw_ans)
                  for a in step.get("check_answers", []))
        if hit:
            # ঠিক -> পরের ধাপ
            session["offline_idx"] = idx + 1
            session["step"] = step_no + 1
            nxt = _offline_step(subject, idx + 1)
            if nxt is None:
                return "✅ ঠিক হয়েছে! এই টপিকের অফলাইন ধাপগুলো শেষ।", True
            session["topic"] = nxt["topic"]
            return (f"✅ ঠিক হয়েছে! এবার পরের ধাপ।\n{nxt['text']}\n"
                    f"যাচাই: {nxt['check_q']}"), True
        right = step.get("check_answers", [""])[0]
        return (f"❌ একটু ভুল হয়েছে। সঠিক উত্তর: {right}।\n"
                f"{step.get('alt') or step['text']}\n"
                f"আরেকবার চেষ্টা করো — {step['check_q']}"), False
    # first / next (অফলাইন)
    return (f"📖 {subject} — {step['topic']}\n{step['text']}\n"
            f"যাচাই: {step['check_q']}\n"
            "(উত্তরটা লিখে পাঠাও; বুঝলে বলো 'বুঝেছি', না বুঝলে 'বুঝিনি')"), None


def _teacher_start(text, low):
    subject = _detect_subject(text, low)
    if not subject:
        return ("কোন বিষয়টা শেখাব? একটা বেছে বলো:\n"
                "• বাংলা সাহিত্য\n• বাংলা ব্যাকরণ\n• গণিত\n• ইংরেজি\n"
                "• সাধারণ জ্ঞান\n• ICT\n"
                "যেমন বলো: 'গণিত শেখাও' বা 'বাংলা ব্যাকরণ পড়াও'।")
    # টপিক: বাক্য থেকে ট্রিগার-শব্দ ও বিষয়ের নাম সরিয়ে বাকিটা টপিক
    topic = text
    for w in _TEACH_START_WORDS:
        topic = topic.replace(w, " ")
    for a in dict(_SUBJECT_ALIASES).get(subject, []):
        topic = topic.replace(a, " ")
    topic = re.sub(r"[\s:—\-]+", " ", topic).strip(" :।,")
    _stop = {"আমাকে", "আমি", "আমায়", "একটু", "ভালোভাবে", "ভালো", "করে",
             "এখন", "আজ", "টা", "টি", "live", "লাইভ", "বিষয়", "বিষয়ে"}
    topic = " ".join(w for w in topic.split() if w not in _stop).strip()
    if len(topic) < 3 or topic.lower() in [s.lower() for s in SUBJECTS] \
            or topic == subject:
        topic = _DEFAULT_TOPICS.get(subject, "")
    session = {"subject": subject, "topic": topic, "step": 1,
               "offline_idx": 0, "weak": [],
               "started": str(date.today()), "last_step": ""}
    step_text, _ = _teacher_step_text(session, "first")
    session["last_step"] = step_text
    _study_save(_STUDY_SESSION_FILE, session)
    wb_add(f"📖 শিক্ষক মোড শুরু — {subject} / {topic}")
    wb_add(step_text)
    return (f"শিক্ষক মোডে আসলাম। বিষয়: {subject}"
            + (f", টপিক: {topic}" if topic else "")
            + f"\nএকবারে এক ধাপ করে শেখাব, প্রতিটা ধাপে বুঝ যাচাই করব।\n\n"
            + step_text)


def _teacher_finish(session):
    subject = session.get("subject", "")
    steps_done = int(session.get("step", 1))
    weak = session.get("weak", [])
    _update_progress(subject, topic=session.get("topic"), weak_topics=weak,
                     add_sessions=1, add_steps=max(steps_done - 1, 0))
    _study_delete(_STUDY_SESSION_FILE)
    lines = [f"আজকের শেখা শেষ। বিষয়: {subject}।",
             f"মোট ধাপ হয়েছে: {_bn_num(steps_done)}টি।"]
    if weak:
        lines.append("যে টপিকে আটকেছিলে: " + ", ".join(dict.fromkeys(weak))
                     + " — পরের সেশনে এগুলো আগে ধরব।")
    else:
        lines.append("আজ কোনো টপিকে আটকাওনি — ভালো এগিয়েছ!")
    lines.append("অগ্রগতি সেভ করে রাখলাম (study-progress)। আবার শিখতে "
                 "চাইলে বলো 'শেখাও' + বিষয়ের নাম।")
    out = "\n".join(lines)
    wb_add("✅ " + lines[0] + " " + lines[1])
    return out


def teacher_handle(text, low):
    """শিক্ষক-মোডের বার্তা সামলায়। শিক্ষক-সংক্রান্ত না হলে None ফেরত দেয়,
    যাতে handle_message পরের ধাপে যেতে পারে।"""
    text = (text or "").strip()
    low = (low if low is not None else text.lower()) or text.lower()
    if not text:
        return None
    session = _load_teacher_session()

    # --- সেশন শেষ
    if any(w in text for w in _TEACH_END_WORDS):
        if session:
            return _teacher_finish(session)
        return None

    # --- নতুন সেশন শুরু
    if any(w in text or w in low for w in _TEACH_START_WORDS):
        return _teacher_start(text, low)

    # --- চলমান সেশন না থাকলে শিক্ষকের কাজ নয়
    if not session:
        return None

    subject = session["subject"]

    # --- বুঝিনি / আবার বোঝাও / আস্তে
    if any(w in text or w in low for w in _TEACH_NOT_UNDERSTOOD):
        step_text, _ = _teacher_step_text(session, "again")
        session["last_step"] = step_text
        cur_topic = session.get("topic") or ""
        if cur_topic and cur_topic not in session.setdefault("weak", []):
            session["weak"].append(cur_topic)
        _study_save(_STUDY_SESSION_FILE, session)
        wb_add(step_text)
        return step_text

    # --- বুঝেছি -> পরের ধাপ
    if any(w in text or w in low for w in _TEACH_UNDERSTOOD):
        session["step"] = int(session.get("step", 1)) + 1
        session["offline_idx"] = int(session.get("offline_idx", 0)) + 1
        step_text, _ = _teacher_step_text(session, "next")
        session["last_step"] = step_text
        _study_save(_STUDY_SESSION_FILE, session)
        wb_add(step_text)
        return step_text

    # --- বাকি সব = যাচাই-প্রশ্নের উত্তর ধরে বিচার
    step_text, was_ok = _teacher_step_text(session, "judge",
                                           student_answer=text)
    if was_ok is False:
        cur_topic = session.get("topic") or ""
        if cur_topic and cur_topic not in session.setdefault("weak", []):
            session["weak"].append(cur_topic)
    if was_ok is True and session.get("mode") != "offline":
        # Gemini উত্তরে ঠিক বললে ধাপ এগিয়ে রাখি
        session["step"] = int(session.get("step", 1)) + 1
        session["offline_idx"] = int(session.get("offline_idx", 0)) + 1
    session["last_step"] = step_text
    _study_save(_STUDY_SESSION_FILE, session)
    wb_add(step_text)
    return step_text


# =====================================================================
#  ৩) মক টেস্ট — আগের বছরের প্রশ্ন-প্যাটার্ন + Timed পরীক্ষা
# =====================================================================

# বিষয়ভিত্তিক প্যাটার্ন-নোট: কোন টপিক বারবার আসে, কোন ধাঁচের প্রশ্ন ঘোরে।
# (Gemini প্রম্পটে এগুলো দেওয়া হয়; অফলাইন ব্যাংকও এই ধাঁচেই সাজানো।)
PATTERN_NOTES = {
    "বাংলা সাহিত্য": ("বারবার আসে: চর্যাপদ (আবিষ্কারক, সংকলক), সাহিত্যের "
                      "যুগবিভাগ, রবীন্দ্রনাথ-নজরুলের বিখ্যাত রচনা ও ছদ্মনাম, "
                      "মঙ্গলকাব্য, বিখ্যাত পঙ্‌ক্তি কার লেখা, মুক্তিযুদ্ধভিত্তিক "
                      "উপন্যাস/নাটক। ধাঁচ: 'কে লিখেছেন / কোন গ্রন্থ থেকে / "
                      "কার ছদ্মনাম' জাতীয় সরাসরি তথ্যভিত্তিক প্রশ্ন।"),
    "বাংলা ব্যাকরণ": ("বারবার আসে: সন্ধি বিচ্ছেদ, সমাস নির্ণয়, কারক ও বিভক্তি, "
                      "ধ্বনি পরিবর্তন, বাগধারা ও এক কথায় প্রকাশ, প্রতিশব্দ, "
                      "বিপরীত শব্দ, শুদ্ধ বানান। ধাঁচ: একটা শব্দ/বাক্য দিয়ে "
                      "'কোন সন্ধি/সমাস/কারক' চেনার প্রশ্ন সবচেয়ে বেশি।"),
    "গণিত": ("বারবার আসে: ভগ্নাংশের যোগ-বিয়োগ, শতকরা (লাভ-ক্ষতি, ছাড়, "
             "জনসংখ্যা বৃদ্ধি), সরল ও যৌগিক সুদ, অনুপাত-সমানুপাত, "
             "লসাগু-গসাগু, গড়, সরল সমীকরণ, ত্রিভুজ/বৃত্তের ক্ষেত্রফল। "
             "ধাঁচ: ছোট সংখ্যার ব্যবহারিক অংক, ৪টা কাছাকাছি অপশন।"),
    "ইংরেজি": ("বারবার আসে: Parts of Speech চেনা, Tense, Article ও "
               "Preposition-এর শূন্যস্থান, Synonym/Antonym, Voice Change, "
               "Narration, সঠিক Spelling, Idioms। ধাঁচ: বাক্যে শূন্যস্থান "
               "পূরণ আর ভুল অংশ চেনার প্রশ্ন বেশি।"),
    "সাধারণ জ্ঞান": ("বারবার আসে: মুক্তিযুদ্ধ (সেক্টর, বীরশ্রেষ্ঠ, গুরুত্বপূর্ণ "
                    "তারিখ), সংবিধান, জাতীয় বিষয়াবলি, বাংলাদেশের নদী/জেলা/"
                    "অর্থনীতি, জাতিসংঘ ও আন্তর্জাতিক সংস্থা, সাম্প্রতিক ঘটনা। "
                    "ধাঁচ: সরাসরি তথ্যের প্রশ্ন, সাল-তারিখ-নাম জোড়া মিলিয়ে।"),
    "ICT": ("বারবার আসে: কম্পিউটারের প্রজন্ম ও ইতিহাস, ইনপুট-আউটপুট ডিভাইস, "
            "সংখ্যা পদ্ধতি (বাইনারি রূপান্তর), মেমোরির একক, ইন্টারনেট ও "
            "ওয়েবের পূর্ণরূপ, হার্ডওয়্যার বনাম সফটওয়্যার, ভাইরাস। ধাঁচ: "
            "পূর্ণরূপ ও সংজ্ঞাভিত্তিক প্রশ্ন বেশি।"),
}

# অফলাইন প্রশ্ন-ব্যাংক: আসল পরীক্ষার ধাঁচের MCQ, topic সহ।
OFFLINE_BANK = {
    "বাংলা সাহিত্য": [
        {"q": "বাংলা সাহিত্যের প্রাচীনতম নিদর্শন কোনটি?",
         "options": ["চর্যাপদ", "শ্রীকৃষ্ণকীর্তন", "মঙ্গলকাব্য", "বৈষ্ণব পদাবলি"],
         "answer": 0, "topic": "চর্যাপদ"},
        {"q": "'আমার সন্তান যেন থাকে দুধে-ভাতে' — পঙ্‌ক্তিটি কার রচনা?",
         "options": ["ভারতচন্দ্র রায়", "মুকুন্দরাম চক্রবর্তী", "আলাওল", "বিজয় গুপ্ত"],
         "answer": 0, "topic": "মধ্যযুগ"},
        {"q": "কাজী নজরুল ইসলামের 'বিদ্রোহী' কবিতাটি কোন কাব্যগ্রন্থের অন্তর্ভুক্ত?",
         "options": ["অগ্নিবীণা", "বিষের বাঁশি", "সাম্যবাদী", "সিন্ধু হিন্দোল"],
         "answer": 0, "topic": "নজরুল"},
        {"q": "রবীন্দ্রনাথ ঠাকুরের 'শেষের কবিতা' কোন ধরনের রচনা?",
         "options": ["উপন্যাস", "নাটক", "ছোটগল্প", "প্রবন্ধ"],
         "answer": 0, "topic": "রবীন্দ্রনাথ"},
    ],
    "বাংলা ব্যাকরণ": [
        {"q": "'বিদ্যালয়' শব্দের সঠিক সন্ধি বিচ্ছেদ কোনটি?",
         "options": ["বিদ্যা + আলয়", "বিদ্যা + লয়", "বি + দ্যালয়", "বিদ্ + আলয়"],
         "answer": 0, "topic": "সন্ধি"},
        {"q": "'গাছ থেকে পাতা পড়ে' — বাক্যে 'গাছ থেকে' কোন কারক?",
         "options": ["অপাদান কারক", "করণ কারক", "কর্ম কারক", "অধিকরণ কারক"],
         "answer": 0, "topic": "কারক"},
        {"q": "'মাতাপিতা' শব্দটি কোন সমাস?",
         "options": ["দ্বন্দ্ব সমাস", "তৎপুরুষ সমাস", "বহুব্রীহি সমাস", "অব্যয়ীভাব সমাস"],
         "answer": 0, "topic": "সমাস"},
        {"q": "'অন্ধের যষ্টি' বাগধারাটির অর্থ কী?",
         "options": ["একমাত্র অবলম্বন", "চোখের মণি", "অন্ধের লাঠি", "খুব কাছের মানুষ"],
         "answer": 0, "topic": "বাগধারা"},
    ],
    "গণিত": [
        {"q": "১/২ + ১/৪ = কত?",
         "options": ["৩/৪", "২/৬", "১/৬", "৫/৪"],
         "answer": 0, "topic": "ভগ্নাংশ"},
        {"q": "২০০ টাকার ২৫% কত টাকা?",
         "options": ["৫০ টাকা", "২৫ টাকা", "৭৫ টাকা", "২০ টাকা"],
         "answer": 0, "topic": "শতকরা"},
        {"q": "কোনো জিনিস ৫০০ টাকায় কিনে ৬০০ টাকায় বিক্রি করলে শতকরা লাভ কত?",
         "options": ["২০%", "১০%", "২৫%", "১৫%"],
         "answer": 0, "topic": "লাভ-ক্ষতি"},
        {"q": "১২ ও ১৮-এর গসাগু কত?",
         "options": ["৬", "৩৬", "৩", "৯"],
         "answer": 0, "topic": "গসাগু-লসাগু"},
        {"q": "একটি সংখ্যার ৩ গুণ ২৭ হলে সংখ্যাটি কত?",
         "options": ["৯", "৮", "১২", "৭"],
         "answer": 0, "topic": "সরল সমীকরণ"},
    ],
    "ইংরেজি": [
        {"q": "What is the past form of 'go'?",
         "options": ["went", "gone", "going", "goes"],
         "answer": 0, "topic": "Verb/Tense"},
        {"q": "Choose the synonym of 'Happy'.",
         "options": ["Glad", "Sad", "Angry", "Tired"],
         "answer": 0, "topic": "Vocabulary"},
        {"q": "He lives ___ Dhaka. (Fill in the blank)",
         "options": ["in", "on", "at", "by"],
         "answer": 0, "topic": "Preposition"},
        {"q": "Which one is a noun?",
         "options": ["Dhaka", "Run", "Quickly", "Beautiful"],
         "answer": 0, "topic": "Parts of Speech"},
    ],
    "সাধারণ জ্ঞান": [
        {"q": "বাংলাদেশের জাতীয় সংসদ ভবনের স্থপতি কে?",
         "options": ["লুই আই কান", "এফ আর খান", "মাজহারুল ইসলাম", "শামীম শিকদার"],
         "answer": 0, "topic": "বাংলাদেশ"},
        {"q": "মুক্তিযুদ্ধে বাংলাদেশকে কয়টি সেক্টরে ভাগ করা হয়েছিল?",
         "options": ["১১টি", "৯টি", "৭টি", "১৩টি"],
         "answer": 0, "topic": "মুক্তিযুদ্ধ"},
        {"q": "বাংলাদেশের সংবিধান কার্যকর হয় কবে?",
         "options": ["১৯৭২ সালের ১৬ ডিসেম্বর", "১৯৭২ সালের ২৬ মার্চ",
                     "১৯৭১ সালের ১৬ ডিসেম্বর", "১৯৭৩ সালের ১৬ ডিসেম্বর"],
         "answer": 0, "topic": "সংবিধান"},
        {"q": "বাংলাদেশের জাতীয় ফল কোনটি?",
         "options": ["কাঁঠাল", "আম", "লিচু", "কলা"],
         "answer": 0, "topic": "জাতীয় বিষয়"},
    ],
    "ICT": [
        {"q": "CPU-এর পূর্ণরূপ কী?",
         "options": ["Central Processing Unit", "Computer Personal Unit",
                     "Central Program Unit", "Control Processing Unit"],
         "answer": 0, "topic": "কম্পিউটার বেসিক"},
        {"q": "নিচের কোনটি ইনপুট ডিভাইস?",
         "options": ["কিবোর্ড", "মনিটর", "প্রিন্টার", "স্পিকার"],
         "answer": 0, "topic": "ইনপুট-আউটপুট"},
        {"q": "১ কিলোবাইট সমান কত বাইট?",
         "options": ["১০২৪ বাইট", "১০০০ বাইট", "৫১২ বাইট", "২০৪৮ বাইট"],
         "answer": 0, "topic": "মেমোরি একক"},
        {"q": "WWW-এর পূর্ণরূপ কী?",
         "options": ["World Wide Web", "World Web Window",
                     "Wide World Web", "Web World Wide"],
         "answer": 0, "topic": "ইন্টারনেট"},
    ],
}


def _load_exam():
    s = load_json(_EXAM_SESSION_FILE, None)
    return s if isinstance(s, dict) and s.get("qs") else None


def _exam_expired(state):
    try:
        return time.time() > float(state.get("deadline_ts", 0))
    except Exception:
        return False


def _fmt_question(state):
    qs = state["qs"]
    idx = int(state.get("idx", 0))
    if idx >= len(qs):
        return ""
    q = qs[idx]
    opts = "\n".join(f"{_OPT_LETTERS[i]}) {op}"
                     for i, op in enumerate(q["options"][:4]))
    return (f"প্রশ্ন {_bn_num(idx + 1)}/{_bn_num(len(qs))}: {q['q']}\n{opts}\n"
            "উত্তরটা লিখে পাঠাও (ক/খ/গ/ঘ বা অপশনটা হুবহু লিখলেও হবে)।")


def _exam_make_questions(subject, count):
    """Gemini দিয়ে কঠোর JSON ফরম্যাটে প্রশ্ন বানায়; না পারলে অফলাইন ব্যাংক।
    ফেরত: (questions_list, source_str)"""
    pattern = PATTERN_NOTES.get(subject, "")
    prompt = (
        f"তুমি বাংলাদেশের সরকারি চাকরির (গ্রেড ১৬-২০) পরীক্ষার প্রশ্নকর্তা। "
        f"বিষয়: {subject}। আগের বছরগুলোর প্রশ্ন-প্যাটার্নের নোট: {pattern}\n"
        f"এই প্যাটার্ন মেনে ঠিক {_bn_num(count)}টি MCQ বানাও। কঠোর নিয়ম: "
        "শুধু একটি JSON array ফেরত দেবে, অন্য কোনো লেখা/ব্যাখ্যা/markdown নয়। "
        "প্রতিটা আইটেম হুবহু এই আকারে: "
        '{"q": "প্রশ্ন (সহজ বাংলা)", "options": ["অপশন১","অপশন২","অপশন৩","অপশন৪"], '
        '"answer": 0, "topic": "টপিকের নাম"} — answer হলো সঠিক অপশনের index '
        "(0-3)। সঠিক উত্তর সবসময় 0 নম্বরে রাখবে না, এলোমেলো জায়গায় রাখো।")
    out = _gemini_or_none(prompt)
    if out:
        try:
            a = out.find("[")
            b = out.rfind("]")
            if a != -1 and b > a:
                data = json.loads(out[a:b + 1])
                qs = []
                for it in data:
                    if (isinstance(it, dict) and it.get("q")
                            and isinstance(it.get("options"), list)
                            and len(it["options"]) == 4
                            and isinstance(it.get("answer"), int)
                            and 0 <= it["answer"] <= 3):
                        qs.append({"q": str(it["q"]),
                                   "options": [str(o) for o in it["options"]],
                                   "answer": int(it["answer"]),
                                   "topic": str(it.get("topic") or "সাধারণ")})
                if len(qs) >= 3:
                    return qs[:count], "online"
        except Exception:
            pass
    # অফলাইন ব্যাংক — তারিখ অনুযায়ী ঘুরিয়ে নেয় যাতে প্রতিবার একই ক্রম না আসে
    bank = OFFLINE_BANK.get(subject) or []
    if not bank:
        return [], "none"
    rot = (date.today().toordinal() % len(bank)) if bank else 0
    rotated = bank[rot:] + bank[:rot]
    qs = [dict(q) for q in rotated[:max(1, min(count, len(rotated)))]]
    return qs, "offline"


def exam_start(subject, count=10, minutes=10):
    """মক টেস্ট শুরু করে; প্রথম প্রশ্নের টেক্সট (বা ত্রুটির বার্তা) ফেরত দেয়।"""
    canon = _detect_subject(str(subject or "")) or subject
    if not canon or canon not in SUBJECTS:
        return ("কোন বিষয়ের পরীক্ষা দেবে? বিষয়গুলো: "
                + ", ".join(SUBJECTS) + "। যেমন: 'গণিত'।")
    try:
        count = max(1, min(30, int(count)))
    except Exception:
        count = 10
    try:
        minutes = max(1, min(120, int(minutes)))
    except Exception:
        minutes = 10
    old = _load_exam()
    if old and not _exam_expired(old):
        _study_delete(_EXAM_SESSION_FILE)  # পুরোনোটা বাদ দিয়ে নতুন শুরু
    qs, source = _exam_make_questions(canon, count)
    if not qs:
        return ("দুঃখিত, এই বিষয়ের প্রশ্ন এখন বানানো যাচ্ছে না — Gemini key "
                "নেই আর অফলাইন ব্যাংকেও এই বিষয় নেই। অন্য বিষয় চেষ্টা করো।")
    now = time.time()
    state = {"subject": canon, "qs": qs, "idx": 0, "score": 0,
             "started_ts": now, "deadline_ts": now + minutes * 60,
             "minutes": minutes, "wrong": [], "source": source}
    _study_save(_EXAM_SESSION_FILE, state)
    head = (f"📝 মক টেস্ট শুরু — বিষয়: {canon}\n"
            f"প্রশ্ন: {_bn_num(len(qs))}টি • সময়: {_bn_num(minutes)} মিনিট"
            + (" (অফলাইন ব্যাংক থেকে)" if source == "offline" else "")
            + "\nসময় শেষ হলেই পরীক্ষা অটো-জমা হয়ে যাবে।\n")
    wb_add(f"📝 মক টেস্ট শুরু — {canon} ({_bn_num(len(qs))} প্রশ্ন, "
           f"{_bn_num(minutes)} মিনিট)")
    return head + "\n" + _fmt_question(state)


def _parse_answer(text, q):
    """উত্তর-লেখা থেকে অপশন index বের করে; না পারলে None।
    মানে: ক/খ/গ/ঘ, a/b/c/d, ১-৪, 1-4, বা অপশনের হুবহু লেখা।"""
    t = (text or "").strip()
    if not t:
        return None
    low = t.lower()
    low = re.sub(r"[।.,)ঃ:]+$", "", low).strip()
    if low in ("ক", "a", "1", "১"):
        return 0
    if low in ("খ", "b", "2", "২"):
        return 1
    if low in ("গ", "c", "3", "৩"):
        return 2
    if low in ("ঘ", "d", "4", "৪"):
        return 3
    m = re.match(r"^([কখগঘabcd])\s*[).]", low)
    if m:
        return {"ক": 0, "খ": 1, "গ": 2, "ঘ": 3,
                "a": 0, "b": 1, "c": 2, "d": 3}[m.group(1)]
    m = re.match(r"^([১২৩৪1234])\s*[).]", _norm_num_text(low))
    if m:
        return int(m.group(1)) - 1
    # অপশনের হুবহু লেখা
    for i, op in enumerate(q.get("options", [])[:4]):
        if t == str(op).strip() or low == str(op).strip().lower():
            return i
    return None


def exam_answer(text):
    """চলমান পরীক্ষায় উত্তর জমা দেয়; ফিডব্যাক + পরের প্রশ্ন ফেরত দেয়।"""
    state = _load_exam()
    if not state:
        return ("এখন কোনো পরীক্ষা চলছে না। শুরু করতে বলো: 'মক টেস্ট' + "
                "বিষয়ের নাম — যেমন 'গণিত মক টেস্ট দাও'।")
    if _exam_expired(state):
        return "⏰ সময় শেষ হয়ে গেছে! পরীক্ষা অটো-জমা নেওয়া হলো।\n\n" \
            + exam_finish()
    qs = state["qs"]
    idx = int(state.get("idx", 0))
    if idx >= len(qs):
        return exam_finish()
    q = qs[idx]
    picked = _parse_answer(text, q)
    if picked is None:
        return ("উত্তরটা বুঝতে পারিনি। ক, খ, গ বা ঘ — যেকোনো একটা লিখো, "
                "অথবা অপশনের লেখাটা হুবহু লিখো।\n\n" + _fmt_question(state))
    correct = int(q.get("answer", 0))
    options = [str(o) for o in q.get("options", [])[:4]]
    if picked == correct:
        state["score"] = int(state.get("score", 0)) + 1
        feedback = f"✅ ঠিক হয়েছে! সঠিক উত্তর: {_OPT_LETTERS[correct]}) {options[correct]}"
    else:
        feedback = (f"❌ ভুল হয়েছে। তুমি দিয়েছ: {_OPT_LETTERS[picked]}) "
                    f"{options[picked]}\nসঠিক উত্তর: {_OPT_LETTERS[correct]}) "
                    f"{options[correct]}")
        state.setdefault("wrong", []).append({
            "q": q["q"], "options": options, "correct": options[correct],
            "your_answer": options[picked],
            "subject": state.get("subject", ""),
            "topic": q.get("topic", "সাধারণ"),
            "date": str(date.today())})
    state["idx"] = idx + 1
    _study_save(_EXAM_SESSION_FILE, state)
    if state["idx"] >= len(qs):
        return feedback + "\n\nসব প্রশ্ন শেষ!\n" + exam_finish()
    remain = max(0, int((state["deadline_ts"] - time.time()) // 60))
    return (feedback + f"\n(সময় বাকি: প্রায় {_bn_num(remain)} মিনিট)\n\n"
            + _fmt_question(state))


def exam_finish():
    """পরীক্ষা শেষ করে রিপোর্ট দেয়: স্কোর, সময়, topic-ভিত্তিক দুর্বলতা।
    ভুলগুলো wrong-book-এ জমা হয়, সেশন-state মোছা হয়, রিপোর্ট বোর্ডে যায়।"""
    state = _load_exam()
    if not state:
        return "কোনো চলমান পরীক্ষা নেই — শেষ করার মতো কিছু পাইনি।"
    qs = state.get("qs", [])
    total = len(qs) or 1
    answered = int(state.get("idx", 0))
    score = int(state.get("score", 0))
    pct = round(score * 100 / total) if total else 0
    elapsed = max(0, int(time.time() - float(state.get("started_ts", time.time()))))
    em, es = divmod(elapsed, 60)
    wrong = state.get("wrong", [])
    # ভুলের খাতায় জমা
    if wrong:
        book = load_json(_WRONG_BOOK_FILE, [])
        if not isinstance(book, list):
            book = []
        book.extend(wrong)
        _study_save(_WRONG_BOOK_FILE, book[-500:])
    # topic-ভিত্তিক দুর্বলতা
    weak_count = {}
    for w in wrong:
        t = w.get("topic") or "সাধারণ"
        weak_count[t] = weak_count.get(t, 0) + 1
    subject = state.get("subject", "")
    _update_progress(subject, weak_topics=list(weak_count.keys()), add_exams=1)
    _study_delete(_EXAM_SESSION_FILE)

    lines = ["🏁 মক টেস্টের রিপোর্ট",
             f"বিষয়: {subject}",
             f"স্কোর: {_bn_num(score)}/{_bn_num(total)} ({_bn_num(pct)}%)",
             f"উত্তর দিয়েছ: {_bn_num(answered)}টি প্রশ্নের",
             f"সময় লেগেছে: {_bn_num(em)} মিনিট {_bn_num(es)} সেকেন্ড"]
    if answered < total:
        lines.append(f"অনুত্তরিত রয়ে গেছে: {_bn_num(total - answered)}টি "
                     "প্রশ্ন (সময় শেষ বা মাঝপথে শেষ করার কারণে)।")
    if weak_count:
        lines.append("দুর্বল টপিক (এখানে ভুল হয়েছে):")
        for t, c in sorted(weak_count.items(), key=lambda kv: -kv[1]):
            lines.append(f"• {t} — {_bn_num(c)}টি ভুল")
        lines.append("ভুল প্রশ্নগুলো ভুলের খাতায় (study-wrong-book) সেভ "
                     "হলো — পরে ওগুলো আবার ঝালিয়ে নিলেই দুর্বলতা কাটবে।")
    else:
        lines.append("কোনো ভুল হয়নি — এই রাউন্ডে দুর্বল টপিক নেই। দারুণ!")
    if pct >= 80:
        lines.append("মন্তব্য: খুব ভালো! এই ধারা ধরে রাখো।")
    elif pct >= 50:
        lines.append("মন্তব্য: মোটামুটি ভালো — দুর্বল টপিকগুলো একবার ঝালিয়ে নাও।")
    else:
        lines.append("মন্তব্য: শিক্ষক মোডে দুর্বল টপিকগুলো ধাপে ধাপে শিখে "
                     "আবার টেস্ট দাও, স্কোর বাড়বেই।")
    report = "\n".join(lines)
    wb_add(report)
    return report


def exam_active():
    """পরীক্ষা চলমান কিনা। সময় পেরিয়ে গেলে অটো-finish করে False দেয়।"""
    state = _load_exam()
    if not state:
        return False
    if _exam_expired(state):
        exam_finish()
        return False
    return int(state.get("idx", 0)) < len(state.get("qs", []))


def exam_status_text():
    """চলমান পরীক্ষার অবস্থা: কত নম্বর প্রশ্ন চলছে, কত সময় বাকি।"""
    state = _load_exam()
    if not state:
        return "এখন কোনো মক টেস্ট চলছে না।"
    if _exam_expired(state):
        return "⏰ আগের পরীক্ষার সময় শেষ হয়ে গেছে।\n\n" + exam_finish()
    remain = max(0, int(state["deadline_ts"] - time.time()))
    rm, rs = divmod(remain, 60)
    return (f"📝 পরীক্ষা চলছে — বিষয়: {state.get('subject', '')}\n"
            f"এখন প্রশ্ন: {_bn_num(int(state.get('idx', 0)) + 1)}/"
            f"{_bn_num(len(state.get('qs', [])))}\n"
            f"এ পর্যন্ত ঠিক: {_bn_num(int(state.get('score', 0)))}টি\n"
            f"সময় বাকি: {_bn_num(rm)} মিনিট {_bn_num(rs)} সেকেন্ড")


# =====================================================================
#  ৪) API ডিসপ্যাচ (UI এটা ব্যবহার করবে)
# =====================================================================

def exam_api(data):
    """data: dict — {"action": "start"|"answer"|"finish"|"status", ...}
    start-এর জন্য: subject, count (default 10), minutes (default 10)
    answer-এর জন্য: text (বা answer)
    ফেরত: {"reply": str, "active": bool}"""
    data = data if isinstance(data, dict) else {}
    action = str(data.get("action") or "").strip().lower()
    if action == "start":
        reply = exam_start(data.get("subject") or "",
                           count=data.get("count", 10),
                           minutes=data.get("minutes", 10))
    elif action == "answer":
        reply = exam_answer(str(data.get("text") or data.get("answer") or ""))
    elif action == "finish":
        reply = exam_finish()
    elif action == "status":
        reply = exam_status_text()
    else:
        reply = ("exam_api: action লাগবে — 'start', 'answer', 'finish' "
                 "বা 'status'।")
    return {"reply": reply, "active": exam_active()}


# শিক্ষক-সেশনের অবস্থা (UI চাইলে ব্যবহার করতে পারে)
def teacher_active():
    return _load_teacher_session() is not None


def study_progress_text():
    """বিষয়ভিত্তিক অগ্রগতির ছোট সারাংশ।"""
    prog = load_json(_STUDY_PROGRESS_FILE, {})
    if not isinstance(prog, dict) or not prog:
        return "এখনো কোনো পড়ার রেকর্ড নেই। 'শেখাও' বলে শুরু করো।"
    lines = ["📚 পড়ার অগ্রগতি:"]
    for subj, ent in prog.items():
        weak = ", ".join(ent.get("weak", [])[-5:]) or "নেই"
        lines.append(f"• {subj}: সেশন {_bn_num(ent.get('sessions', 0))}টি, "
                     f"মক টেস্ট {_bn_num(ent.get('mock_tests', 0))}টি, "
                     f"শেষ টপিক: {ent.get('last_topic') or '—'}, "
                     f"দুর্বল: {weak}")
    return "\n".join(lines)


# -*- coding: utf-8 -*-
"""
Desktop Sokhi v1.5.0 — Study Feature Pack (WAVE-2, study cluster)
=================================================================
Self-contained snippets for integration into sokhi.py (v1.5.0).
Coordinator: paste this whole file at top level in sokhi.py AFTER
OFFLINE_BANK / OFFLINE_LESSONS are defined and AFTER _bn_num /
load_json / _STUDY_PROGRESS_FILE / _WRONG_BOOK_FILE exist
(i.e. anywhere after the teacher/exam section, before handle_message),
then wire the dispatch block described in INTEGRATION-STUDY.md.

Features:
  #654 question_mining_text()      প্রশ্ন-খনন রিপোর্ট
  #655 coverage_text()             সিলেবাস-কভারেজ
  #725 wrong_analysis_text()       ভুল-বিশ্লেষণ
  #759 xray_text()                 জ্ঞানের এক্স-রে (lite, অনুমান)
  #697 mastery_questions() /
       mastery_grade()             অধ্যায়-মাস্টারি যাচাই
  #721 bedtime_revision_text()     ঘুমের আগের রিভিশন
  #748 lesson_summaries_text()     অধ্যায়ের এক-লাইন সার
  #664 concept_map_text(subject)   ধারণা-মানচিত্র (text)

House rules honoured:
  * 100% free, offline-only — reads ONLY OFFLINE_BANK, OFFLINE_LESSONS,
    study-progress.json and study-wrong-book.json. No web, no Gemini.
  * Never fabricates exam data — every number is a count of what
    actually exists in those banks/files. Empty data -> a friendly
    "এখনো ডেটা নেই" Bangla line, never invented numbers.
  * Pure-ish functions: data can be injected via parameters (used by
    test_study_pack.py). When a parameter is None, the function falls
    back to the module globals of the host sokhi.py with the EXACT
    existing names: OFFLINE_BANK, OFFLINE_LESSONS, load_json,
    _STUDY_PROGRESS_FILE, _WRONG_BOOK_FILE.
  * Bangla digits via a LOCAL _bn() helper (self-contained mirror of
    the host's _bn_num at ~line 689 in build-v14/app/sokhi.py), so the
    pack works standalone in tests; integration may delete _bn and
    alias _bn = _bn_num if preferred.

Verified data shapes (build-v14/app/sokhi.py):
  study-progress.json:
    {subject: {sessions:int, mock_tests:int, total_steps:int,
               weak:[str], last_topic:str, last_date:"YYYY-MM-DD"}}
    (_update_progress ~line 802; study_progress_text ~line 1678)
  study-wrong-book.json: list of dicts written by exam_answer /
    exam_finish (~lines 1546-1605), each entry:
    {"q": str, "options": [str x4], "correct": str (correct option TEXT),
     "your_answer": str (picked option TEXT), "subject": str,
     "topic": str, "date": "YYYY-MM-DD"}
  OFFLINE_BANK (~line 1291):
    {subject: [{"q": str, "options": [str x4], "answer": int (0-3),
                "topic": str}]}
  OFFLINE_LESSONS (~line 830+):
    {subject: [{"topic": str, "text": str, "check_q": str,
                "check_answers": [str], "alt": str}]}
"""

from collections import Counter
from datetime import date

# ------------------------------------------------------------------ digits

_BN_DIGITS_MAP = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")


def _bn(x):
    """Local mirror of host _bn_num(): English digits -> Bangla digits."""
    return str(x).translate(_BN_DIGITS_MAP)


_NO_DATA = "এখনো ডেটা নেই"

# ------------------------------------------------------- global fallbacks
# These helpers deliberately look names up in globals() at CALL time, so
# (a) the pack works when pasted into sokhi.py (host globals win), and
# (b) tests can stub study_pack.OFFLINE_BANK etc. or pass data directly.


def _resolve_bank(bank=None):
    if bank is not None:
        return bank if isinstance(bank, dict) else {}
    g = globals().get("OFFLINE_BANK")
    return g if isinstance(g, dict) else {}


def _resolve_lessons(lessons=None):
    if lessons is not None:
        return lessons if isinstance(lessons, dict) else {}
    g = globals().get("OFFLINE_LESSONS")
    return g if isinstance(g, dict) else {}


def _load_via_host(path, default):
    fn = globals().get("load_json")
    if callable(fn) and path is not None:
        try:
            return fn(path, default)
        except Exception:
            return default
    return default


def _resolve_progress(progress=None):
    if progress is not None:
        return progress if isinstance(progress, dict) else {}
    path = globals().get("_STUDY_PROGRESS_FILE")
    data = _load_via_host(path, {})
    return data if isinstance(data, dict) else {}


def _resolve_wrong(wrong=None):
    if wrong is not None:
        return wrong if isinstance(wrong, list) else []
    path = globals().get("_WRONG_BOOK_FILE")
    data = _load_via_host(path, [])
    return data if isinstance(data, list) else []


def _wrong_counts_by_subject(wrong):
    c = Counter()
    for w in wrong or []:
        if isinstance(w, dict):
            c[str(w.get("subject") or "অজানা বিষয়")] += 1
    return c


def _wrong_counts_by_topic(wrong):
    c = Counter()
    for w in wrong or []:
        if isinstance(w, dict):
            c[str(w.get("topic") or "সাধারণ")] += 1
    return c


# =====================================================================
#  #654 প্রশ্ন-খনন রিপোর্ট
# =====================================================================

def question_mining_text(bank=None, wrong=None):
    """OFFLINE_BANK (সব বিষয়) + wrong-book থেকে:
    বিষয়ভিত্তিক প্রশ্ন-সংখ্যা, টপিকভিত্তিক ফ্রিকোয়েন্সির শীর্ষ তালিকা,
    আর ভুলের খাতায় কোন টপিকে বেশি ভুল জমেছে — Bangla রিপোর্ট।
    শুধু ব্যাংক/খাতায় যা আছে তাই গোনা হয়; কিছু বানানো হয় না।"""
    bank = _resolve_bank(bank)
    wrong = _resolve_wrong(wrong)
    total_q = sum(len(v or []) for v in bank.values())
    if total_q == 0 and not wrong:
        return (f"{_NO_DATA} — প্রশ্ন-ব্যাংকেও কোনো প্রশ্ন পাইনি, ভুলের "
                "খাতাও খালি। মক টেস্ট দিলে বা অফলাইন ব্যাংকে প্রশ্ন থাকলে "
                "এখানে বিশ্লেষণ দেখা যাবে।")

    lines = ["🔍 প্রশ্ন-খনন রিপোর্ট — কোন টপিক থেকে প্রশ্ন বেশি আসে",
             "(শুধু অফলাইন প্রশ্ন-ব্যাংক আর তোমার ভুলের খাতা গুনে বলছি; "
             "বাইরের কোনো তথ্য যোগ করিনি।)"]

    if bank:
        lines.append("")
        lines.append("বিষয়ভিত্তিক প্রশ্ন (অফলাইন ব্যাংকে):")
        for subj in sorted(bank.keys()):
            lines.append(f"• {subj}: {_bn(len(bank[subj] or []))}টি প্রশ্ন")
        lines.append(f"মোট: {_bn(total_q)}টি প্রশ্ন")

        topic_counter = Counter()
        for subj, qs in bank.items():
            for q in qs or []:
                if isinstance(q, dict):
                    topic_counter[str(q.get("topic") or "সাধারণ")] += 1
        if topic_counter:
            lines.append("")
            lines.append("ব্যাংকে সবচেয়ে বেশি প্রশ্ন আছে যেসব টপিকে (শীর্ষ ১০):")
            for topic, cnt in topic_counter.most_common(10):
                lines.append(f"• {topic} — {_bn(cnt)}টি প্রশ্ন")

    if wrong:
        wc = _wrong_counts_by_topic(wrong)
        lines.append("")
        lines.append("ভুলের খাতায় যেসব টপিকে বেশি ভুল জমেছে (শীর্ষ ১০):")
        for topic, cnt in wc.most_common(10):
            lines.append(f"• {topic} — {_bn(cnt)}বার ভুল")
        lines.append("মানে: ব্যাংকে যে টপিকে প্রশ্ন বেশি, আর তুমি যেখানে "
                     "বেশি ভুল করেছ — দুটো মিললে সেটাই আগে পড়া জরুরি।")
    return "\n".join(lines)


# =====================================================================
#  #655 সিলেবাস-কভারেজ
# =====================================================================

def coverage_text(progress=None, lessons=None):
    """study-progress.json + OFFLINE_LESSONS থেকে বিষয়ভিত্তিক কভারেজ।
    প্রতি বিষয়ে: মোট পাঠ (lessons) বনাম ছোঁয়া টপিক।
    'ছোঁয়া টপিক' = যেসব টপিকের প্রমাণ progress-এ আছে: last_topic এবং
    weak[]-এর যেসব টপিক lesson তালিকায় আছে। এটা সীমিত প্রমাণভিত্তিক
    হিসাব — রিপোর্টে তা বলেও দেওয়া হয়; সেশন-সংখ্যাও পাশে দেখানো হয়।"""
    progress = _resolve_progress(progress)
    lessons = _resolve_lessons(lessons)
    if not lessons and not progress:
        return (f"{_NO_DATA} — কোনো পাঠের তালিকা বা পড়ার রেকর্ড পাইনি। "
                "'শেখাও' বলে পড়া শুরু করলেই কভারেজ হিসাব শুরু হবে।")

    subjects = list(lessons.keys())
    for s in progress.keys():
        if s not in subjects:
            subjects.append(s)
    if not subjects:
        return f"{_NO_DATA} — কোনো বিষয়ের রেকর্ড পাইনি।"

    lines = ["📊 সিলেবাস-কভারেজ",
             "(কভারেজ = অফলাইন পাঠের তালিকার মধ্যে যতগুলো টপিক ছোঁয়ার "
             "প্রমাণ পড়ার রেকর্ডে আছে — last_topic ও দুর্বল তালিকা থেকে।)"]
    for subj in subjects:
        total = len(lessons.get(subj) or [])
        ent = progress.get(subj) or {}
        lesson_topics = [str(x.get("topic") or "")
                         for x in (lessons.get(subj) or [])
                         if isinstance(x, dict)]
        touched = set()
        lt = str(ent.get("last_topic") or "").strip()
        if lt and lt in lesson_topics:
            touched.add(lt)
        elif lt and total == 0:
            touched.add(lt)
        for w in ent.get("weak", []) or []:
            if str(w) in lesson_topics:
                touched.add(str(w))
        sessions = int(ent.get("sessions", 0) or 0)
        weak = [str(w) for w in (ent.get("weak", []) or [])]
        if total > 0:
            pct = round(len(touched) * 100 / total)
            lines.append(
                f"• {subj}: পাঠ {_bn(len(touched))}/{_bn(total)}টি ছোঁয়া "
                f"({_bn(pct)}%), সেশন {_bn(sessions)}টি, "
                f"শেষ টপিক: {lt or '—'}")
        else:
            lines.append(
                f"• {subj}: এই বিষয়ের অফলাইন পাঠের তালিকা নেই, "
                f"সেশন {_bn(sessions)}টি, শেষ টপিক: {lt or '—'}")
        if weak:
            lines.append(f"  দুর্বল টপিক: {', '.join(weak[-5:])}")
    return "\n".join(lines)


# =====================================================================
#  #725 ভুল-বিশ্লেষণ
# =====================================================================

def wrong_analysis_text(wrong=None):
    """Wrong-book-কে বিষয় ও টপিক ধরে গুনে সাজানো বিশ্লেষণ;
    সবচেয়ে বেশি পুনরাবৃত্ত দুর্বল জায়গা শীর্ষ-৫। সহজ বাংলা।"""
    wrong = _resolve_wrong(wrong)
    if not wrong:
        return (f"{_NO_DATA} — ভুলের খাতা খালি। এখনো কোনো মক টেস্টে ভুল "
                "জমা হয়নি। মক টেস্ট দিলে ভুলগুলো এখানে জমবে, তখন বিশ্লেষণ "
                "দেখতে পাবে।")

    by_subject = Counter()
    by_pair = Counter()  # (subject, topic)
    for w in wrong:
        if not isinstance(w, dict):
            continue
        subj = str(w.get("subject") or "অজানা বিষয়")
        topic = str(w.get("topic") or "সাধারণ")
        by_subject[subj] += 1
        by_pair[(subj, topic)] += 1

    lines = ["📕 ভুল-বিশ্লেষণ",
             f"ভুলের খাতায় মোট ভুল: {_bn(sum(by_subject.values()))}টি।"]
    if by_subject:
        lines.append("")
        lines.append("বিষয় ধরে ভুল:")
        for subj, cnt in by_subject.most_common():
            lines.append(f"• {subj} — {_bn(cnt)}টি ভুল")
    if by_pair:
        lines.append("")
        lines.append("সবচেয়ে বেশি ভুল হয়েছে যেখানে (শীর্ষ ৫):")
        for (subj, topic), cnt in by_pair.most_common(5):
            lines.append(f"• {subj} / {topic} — {_bn(cnt)}বার")
        lines.append("")
        lines.append("পরামর্শ: শীর্ষের টপিকটা শিক্ষক মোডে একবার ধাপে ধাপে "
                     "শিখে নাও, তারপর আবার মক টেস্ট দাও — ভুল কমবেই।")
    return "\n".join(lines)


# =====================================================================
#  #759 জ্ঞানের এক্স-রে (lite) — সৎ অনুমান, লেবেলসহ
# =====================================================================

def xray_text(progress=None, wrong=None, lessons=None, bank=None):
    """Progress + wrong-book + OFFLINE_LESSONS মিলিয়ে বিষয়ভিত্তিক
    শক্তির ছবি। হিউরিস্টিক (স্পষ্ট করে 'অনুমান' বলা হয়েছে):
      activity = sessions + mock_tests
      wrong_n  = ওই বিষয়ে wrong-book এন্ট্রির সংখ্যা
      activity >= 3 এবং wrong_n <= 2          -> শক্তিশালী
      activity >= 1 এবং wrong_n <= activity+2 -> মাঝারি
      wrong_n > activity + 2                  -> দুর্বল
      activity == 0                           -> এখনো শুরু হয়নি
    """
    progress = _resolve_progress(progress)
    wrong = _resolve_wrong(wrong)
    lessons = _resolve_lessons(lessons)
    bank = _resolve_bank(bank)
    if not progress and not wrong and not lessons and not bank:
        return (f"{_NO_DATA} — পড়ার রেকর্ড, ভুলের খাতা, পাঠ — কিছুই "
                "পাইনি। পড়া শুরু করলেই এক্স-রে তৈরি হবে।")

    subjects = []
    for src in (lessons, bank, progress):
        for s in (src or {}).keys():
            if s not in subjects:
                subjects.append(s)
    for subj, _cnt in _wrong_counts_by_subject(wrong).most_common():
        if subj not in subjects:
            subjects.append(subj)
    if not subjects:
        return f"{_NO_DATA} — কোনো বিষয়ের তথ্য পাইনি।"

    wrong_by_subj = _wrong_counts_by_subject(wrong)
    lines = ["🩻 জ্ঞানের এক্স-রে (lite)",
             "সতর্কতা: এটা একটা অনুমান — সেশনের সংখ্যা আর ভুলের সংখ্যা "
             "মিলিয়ে আন্দাজ করছি, আসল পরীক্ষা নয়।"]
    for subj in subjects:
        ent = progress.get(subj) or {}
        activity = int(ent.get("sessions", 0) or 0) + \
            int(ent.get("mock_tests", 0) or 0)
        wrong_n = int(wrong_by_subj.get(subj, 0))
        if activity == 0 and wrong_n == 0:
            level = "এখনো শুরু হয়নি"
        elif activity >= 3 and wrong_n <= 2:
            level = "শক্তিশালী"
        elif wrong_n > activity + 2:
            level = "দুর্বল"
        else:
            level = "মাঝারি"
        weak = [str(w) for w in (ent.get("weak", []) or [])]
        line = (f"• {subj}: {level} "
                f"(সেশন+টেস্ট {_bn(activity)}টি, ভুল {_bn(wrong_n)}টি")
        if weak:
            line += f", দুর্বল টপিক: {', '.join(weak[-3:])}"
        line += ")"
        lines.append(line)
    return "\n".join(lines)


# =====================================================================
#  #697 অধ্যায়-মাস্টারি যাচাই — ডেটা + গ্রেডিং (ইন্টার‌্যাক্টিভ ফ্লো
#  ইন্টিগ্রেটরের কাজ; এখানে শুধু প্রশ্ন বাছাই আর রায়)
# =====================================================================

def mastery_questions(subject, topic=None, bank=None, lessons=None):
    """Mastery check-এর জন্য সর্বোচ্চ ৫টি প্রশ্ন ফেরত দেয় (list of dict)।
    বাছাইয়ের ক্রম (preference):
      1. OFFLINE_BANK-এ ওই বিষয়ের, topic দিলে ওই topic-এর প্রশ্ন
      2. OFFLINE_LESSONS-এ মিলে যাওয়া topic-এর check_q (lesson check)
      3. জায়গা বাকি থাকলে ওই বিষয়ের বাকি bank প্রশ্ন (অন্য topic)
    প্রতিটা আইটেম:
      {"q": str, "options": [str] (bank হলে ৪টা, lesson হলে []),
       "answer": int (bank: সঠিক index) বা str (lesson: প্রথম check_answer),
       "topic": str, "subject": str, "source": "bank"|"lesson_check"}
    বিষয়/ডেটা না থাকলে [] ফেরত দেয় — কিছু বানানো হয় না।"""
    bank = _resolve_bank(bank)
    lessons = _resolve_lessons(lessons)
    subject = str(subject or "").strip()
    if not subject:
        return []
    topic = str(topic or "").strip()
    out = []
    seen_q = set()

    def _add(qtext, options, answer, qtopic, source):
        if len(out) >= 5 or not qtext or qtext in seen_q:
            return
        seen_q.add(qtext)
        out.append({"q": qtext, "options": list(options or []),
                    "answer": answer, "topic": qtopic or "সাধারণ",
                    "subject": subject, "source": source})

    bank_qs = [q for q in (bank.get(subject) or []) if isinstance(q, dict)]
    # 1) topic মিলে যাওয়া bank প্রশ্ন আগে
    if topic:
        for q in bank_qs:
            if str(q.get("topic") or "") == topic:
                _add(str(q.get("q") or ""), q.get("options") or [],
                     int(q.get("answer", 0) or 0),
                     str(q.get("topic") or topic), "bank")
    else:
        for q in bank_qs:
            _add(str(q.get("q") or ""), q.get("options") or [],
                 int(q.get("answer", 0) or 0),
                 str(q.get("topic") or "সাধারণ"), "bank")
    # 2) lesson check_q (topic দিলে শুধু মিলে যাওয়া topic)
    for step in (lessons.get(subject) or []):
        if not isinstance(step, dict):
            continue
        st = str(step.get("topic") or "")
        if topic and st != topic:
            continue
        answers = step.get("check_answers") or []
        _add(str(step.get("check_q") or ""), [],
             str(answers[0]) if answers else "", st, "lesson_check")
    # 3) বাকি bank প্রশ্ন দিয়ে পূরণ (topic নির্দিষ্ট থাকলেও, প্রশ্ন কম হলে)
    if topic:
        for q in bank_qs:
            _add(str(q.get("q") or ""), q.get("options") or [],
                 int(q.get("answer", 0) or 0),
                 str(q.get("topic") or "সাধারণ"), "bank")
    return out[:5]


def mastery_questions_text(subject, topic=None, bank=None, lessons=None):
    """mastery_questions()-এর পাঠযোগ্য Bangla রূপ (চ্যাটে দেখানোর জন্য)।"""
    qs = mastery_questions(subject, topic=topic, bank=bank, lessons=lessons)
    if not qs:
        return (f"{_NO_DATA} — এই বিষয়/টপিকের কোনো প্রশ্ন ব্যাংক বা পাঠে "
                "পাইনি, তাই মাস্টারি টেস্ট সাজাতে পারলাম না।")
    head = f"🎯 মাস্টারি টেস্ট — {subject}" + (f" / {topic}" if topic else "")
    lines = [head, f"মোট প্রশ্ন: {_bn(len(qs))}টি। একটা একটা করে উত্তর দাও।"]
    letters = ["ক", "খ", "গ", "ঘ"]
    for i, q in enumerate(qs, 1):
        lines.append("")
        lines.append(f"প্রশ্ন {_bn(i)}: {q['q']}")
        for j, op in enumerate(q.get("options") or []):
            if j < len(letters):
                lines.append(f"{letters[j]}) {op}")
    return "\n".join(lines)


def mastery_grade(answers_correct, total):
    """Mastery রায়: শতকরা হিসাব, >= ৮০% হলে 'মাস্টার'।"""
    try:
        total = int(total)
        correct = int(answers_correct)
    except Exception:
        total, correct = 0, 0
    if total <= 0:
        return f"{_NO_DATA} — কোনো প্রশ্নের উত্তরই দেওয়া হয়নি।"
    correct = max(0, min(correct, total))
    pct = round(correct * 100 / total)
    head = (f"ফলাফল: {_bn(correct)}/{_bn(total)} ঠিক ({_bn(pct)}%)। ")
    if pct >= 80:
        return head + "🏆 মাস্টার! এই অধ্যায়টা তুমি ভালোভাবে আয়ত্ত করেছ।"
    if pct >= 60:
        return head + "ভালো — প্রায় হয়ে এসেছে। ভুলগুলো একবার ঝালিয়ে নিলেই মাস্টারি আসবে।"
    if pct >= 40:
        return head + "মাঝারি — অধ্যায়টা শিক্ষক মোডে আরেকবার ধাপে ধাপে পড়ে নাও।"
    return head + "এখনো দুর্বল — চিন্তা নেই, শিক্ষক মোডে এই অধ্যায়টা বেসিক থেকে আবার শুরু করো।"


# =====================================================================
#  #721 ঘুমের আগের রিভিশন
# =====================================================================

def bedtime_revision_text(progress=None, wrong=None, today=None):
    """২ মিনিটে পড়া যায় এমন রাতের রিভিশন:
    আজ ছোঁয়া টপিক (progress last_date == আজ) + সাম্প্রতিক সর্বোচ্চ ৫টি
    ভুল প্রশ্নের সঠিক উত্তর। today প্যারামিটার টেস্টের জন্য (date বা
    'YYYY-MM-DD' str); না দিলে আজকের তারিখ।"""
    progress = _resolve_progress(progress)
    wrong = _resolve_wrong(wrong)
    if today is None:
        today_s = str(date.today())
    elif isinstance(today, str):
        today_s = today
    else:
        today_s = str(today)

    todays = []
    for subj, ent in (progress or {}).items():
        if not isinstance(ent, dict):
            continue
        if str(ent.get("last_date") or "") == today_s and \
                str(ent.get("last_topic") or "").strip():
            todays.append((str(subj), str(ent.get("last_topic"))))
    recent_wrong = [w for w in (wrong or []) if isinstance(w, dict)][-5:]

    if not todays and not recent_wrong:
        return (f"{_NO_DATA} — আজকের পড়ার রেকর্ড বা ভুলের খাতায় কিছু "
                "পাইনি। কাল পড়া শেষে আবার চাইলে রিভিশন সাজিয়ে দেব। "
                "এখন ঘুমিয়ে পড়ো, ঘুমটাও পড়ারই অংশ। 🌙")

    lines = ["🌙 ঘুমের আগের রিভিশন (২ মিনিটে পড়ে ফেলো)"]
    if todays:
        lines.append("")
        lines.append("আজ যা পড়েছ:")
        for subj, topic in todays:
            lines.append(f"• {subj} — {topic}")
    if recent_wrong:
        lines.append("")
        lines.append("সাম্প্রতিক ভুলগুলোর সঠিক উত্তর (মনে গেঁথে নাও):")
        for w in reversed(recent_wrong):
            lines.append(f"• প্রশ্ন: {w.get('q', '')}")
            lines.append(f"  সঠিক উত্তর: {w.get('correct', '')}")
    lines.append("")
    lines.append("এইটুকুই। এবার ফোন রেখে ঘুম — কাল আবার একসাথে পড়ব।")
    return "\n".join(lines)


# =====================================================================
#  #748 অধ্যায়ের এক-লাইন সার
# =====================================================================

def lesson_summaries_text(subject=None, lessons=None):
    """OFFLINE_LESSONS-এর প্রতি টপিকের এক-লাইন সার:
    text-এর প্রথম বাক্য ('।' দিয়ে ভাগ), সর্বোচ্চ ১২০ অক্ষর।
    subject দিলে শুধু ওই বিষয়; না দিলে সব বিষয়।"""
    lessons = _resolve_lessons(lessons)
    if not lessons:
        return f"{_NO_DATA} — অফলাইন পাঠের তালিকাই খালি, সার বানানোর কিছু নেই।"
    if subject:
        subject = str(subject).strip()
        if subject not in lessons or not lessons.get(subject):
            return (f"{_NO_DATA} — '{subject}' বিষয়ের কোনো পাঠ পাইনি। "
                    "যেসব বিষয়ে পাঠ আছে: " + ", ".join(lessons.keys()) + "।")
        subjects = [subject]
    else:
        subjects = list(lessons.keys())

    lines = ["📑 অধ্যায়ের এক-লাইন সার"]
    any_row = False
    for subj in subjects:
        rows = []
        for step in lessons.get(subj) or []:
            if not isinstance(step, dict):
                continue
            text = str(step.get("text") or "").strip()
            if not text:
                continue
            first = text.split("।")[0].strip()
            if len(first) > 120:
                first = first[:120].rstrip() + "…"
            rows.append(f"• {step.get('topic', 'সাধারণ')}: {first}।")
        if rows:
            any_row = True
            lines.append("")
            lines.append(f"{subj}:")
            lines.extend(rows)
    if not any_row:
        return f"{_NO_DATA} — পাঠের তালিকা থাকলেও ভিতরে লেখা পাইনি।"
    return "\n".join(lines)


# =====================================================================
#  #664 ধারণা-মানচিত্র (text)
# =====================================================================

def concept_map_text(subject, progress=None, lessons=None):
    """এক বিষয়ের lesson টপিকগুলোর শৃঙ্খল (তীর দিয়ে), দুর্বল টপিকগুলো
    progress-এর weak[] থেকে ⚠ চিহ্ন দিয়ে আলাদা করে দেখানো।"""
    lessons = _resolve_lessons(lessons)
    progress = _resolve_progress(progress)
    subject = str(subject or "").strip()
    if not subject:
        return ("কোন বিষয়ের ধারণা-মানচিত্র চাও? বিষয়ের নাম বলো — যেমন: "
                "'গণিত ধারণা মানচিত্র'।")
    steps = [s for s in (lessons.get(subject) or []) if isinstance(s, dict)]
    if not steps:
        return (f"{_NO_DATA} — '{subject}' বিষয়ের অফলাইন পাঠের তালিকা "
                "পাইনি, তাই মানচিত্র আঁকা যাচ্ছে না।")

    ent = progress.get(subject) or {}
    weak = [str(w) for w in (ent.get("weak", []) or [])]
    weak_set = set(weak)
    topics = [str(s.get("topic") or "সাধারণ") for s in steps]
    chain_parts = []
    for t in topics:
        chain_parts.append(t + " ⚠" if t in weak_set else t)
    lines = [f"🗺️ ধারণা-মানচিত্র — {subject}",
             "পাঠের ক্রম:",
             " → ".join(chain_parts)]
    marked = [t for t in topics if t in weak_set]
    if marked:
        lines.append("")
        lines.append("⚠ দুর্বল টপিক (রেকর্ডে আছে): " + ", ".join(marked)
                     + " — এগুলো আগে ঝালিয়ে নাও।")
    elif weak:
        lines.append("")
        lines.append("দুর্বল হিসেবে রেকর্ডে আছে: " + ", ".join(weak[-5:])
                     + " (এই পাঠ-তালিকার টপিকের সঙ্গে সরাসরি মেলেনি)।")
    else:
        lines.append("")
        lines.append("এই বিষয়ে এখনো কোনো দুর্বল টপিক রেকর্ডে নেই।")
    lines.append(f"মোট ধাপ: {_bn(len(topics))}টি পাঠ।")
    return "\n".join(lines)


# =====================================================================
#  ঐচ্ছিক ডিসপ্যাচ হেল্পার (ইন্টিগ্রেটর চাইলে ব্যবহার করবে;
#  বিস্তারিত INTEGRATION-STUDY.md-তে)
# =====================================================================

STUDY_PACK_TRIGGERS = (
    "প্রশ্ন বিশ্লেষণ", "প্রশ্ন খনন", "কভারেজ", "ভুল বিশ্লেষণ",
    "এক্স-রে", "আমার অবস্থা", "মাস্টারি টেস্ট",
    "ঘুমের আগের রিভিশন", "অধ্যায়ের সার", "ধারণা মানচিত্র",
    "ধারণা-মানচিত্র",
)


def _subject_in_text(text, bank, lessons):
    for subj in list((bank or {}).keys()) + \
            [s for s in (lessons or {}).keys() if s not in (bank or {})]:
        if subj and subj in str(text or ""):
            return subj
    fn = globals().get("_detect_subject")
    if callable(fn):
        try:
            return fn(str(text or ""))
        except Exception:
            return None
    return None


def study_pack_handle(text, low=None):
    """Trigger মিললে সংশ্লিষ্ট রিপোর্টের টেক্সট, না মিললে None ফেরত দেয়।
    Mastery-র ইন্টার‌্যাক্টিভ ফ্লো ইন্টিগ্রেটরের — এখানে শুধু প্রশ্নের
    তালিকা দেখানো হয় (mastery_questions_text)।"""
    text = str(text or "").strip()
    if not text:
        return None
    bank = _resolve_bank()
    lessons = _resolve_lessons()
    if "প্রশ্ন বিশ্লেষণ" in text or "প্রশ্ন খনন" in text:
        return question_mining_text(bank=bank)
    if "ভুল বিশ্লেষণ" in text:
        return wrong_analysis_text()
    if "কভারেজ" in text:
        return coverage_text(lessons=lessons)
    if "এক্স-রে" in text or "আমার অবস্থা" in text:
        return xray_text(lessons=lessons, bank=bank)
    if "ঘুমের আগের রিভিশন" in text:
        return bedtime_revision_text()
    if "অধ্যায়ের সার" in text:
        return lesson_summaries_text(
            subject=_subject_in_text(text, bank, lessons), lessons=lessons)
    if "ধারণা মানচিত্র" in text or "ধারণা-মানচিত্র" in text:
        subj = _subject_in_text(text, bank, lessons)
        if not subj:
            return ("কোন বিষয়ের ধারণা-মানচিত্র চাও? বিষয়ের নামসহ বলো — "
                    "যেমন: 'গণিত ধারণা মানচিত্র'।")
        return concept_map_text(subj, lessons=lessons)
    if "মাস্টারি টেস্ট" in text:
        subj = _subject_in_text(text, bank, lessons)
        if not subj:
            return ("কোন বিষয়ের মাস্টারি টেস্ট দেবে? বিষয়ের নামসহ বলো — "
                    "যেমন: 'গণিত মাস্টারি টেস্ট'।")
        return mastery_questions_text(subj, bank=bank, lessons=lessons)
    return None


# -*- coding: utf-8 -*-
"""
chart_pack.py — Desktop Sokhi v1.8.0, item #47: ইনলাইন SVG চার্ট/ডায়াগ্রাম উত্তর

PASTE-READY FRAGMENT for sokhi.py — এই ফাইলটা নিজে কোনো sokhi.py নয়।
ইন্টিগ্রেশন: INTEGRATION-A.md দেখো (study pack-এর পরে, handle_message-এর আগে)।

Features:
  chart_series(kind, ...)   আসল লোকাল ডেটা থেকে চার্টের সিরিজ (dict/None)
  svg_bar_chart(series)     horizontal-bar SVG (str)
  svg_line_chart(series)    polyline SVG (str)
  concept_svg(subject, ...) ধারণা-মানচিত্রের vertical node diagram (str/None)
  chart_reply(text)         চ্যাট ডিসপ্যাচার — উত্তরে [[CHART:...]] মার্কার বসায়

House rules honoured:
  * 100% free, offline-only, stdlib only — কোনো external JS lib, কোনো
    web service, কোনো AI image generation নয়। চার্ট = নিজের আসল ডেটা
    থেকে বানানো SVG; ডেটা না থাকলে সেটা সহজ বাংলায় বলা হয়।
  * Pure-Python functions: ডেটা প্যারামিটার দিয়ে inject করা যায়
    (test_chart_pack.py তাই করে)। প্যারামিটার None হলে host sokhi.py-র
    globals CALL TIME-এ globals().get(...) দিয়ে resolve করা হয় —
    _resolve_progress / _resolve_wrong / _resolve_lessons / _resolve_bank /
    _wrong_counts_by_subject / _bn (বা _bn_num) / _NO_DATA /
    concept_map_text / coverage_text / _subject_in_text।
    ফলে fragment-টা sokhi.py-তে paste করলেও চলে, standalone test-এ
    stub দিলেও চলে।
  * সব SVG text html-escape করা — বিষয়ের নামে <b> থাকলেও markup ভাঙবে না।
  * সংখ্যা দেখানো হয় Bangla digits-এ (host _bn/_bn_num থাকলে সেটা,
    না থাকলে স্থানীয় fallback)।

Data shapes (host-এর সঙ্গে মিলিয়ে):
  study-progress.json = {subject: {"sessions": int, "mock_tests": int,
                                   "last_topic": str, "weak": [str]}}
  OFFLINE_LESSONS = {subject: [{"topic": str, ...}]}
  OFFLINE_BANK    = {subject: [question dicts]}
  wrong-book      = [{"subject": ..., "topic": ...}]

Coverage হিসাব coverage_text()-এর EXACT mirror:
  per subject: total = len(lessons[subject]);
  touched = যেসব lesson topic progress[subject].last_topic হিসেবে বা
            progress[subject].weak[]-তে আছে;
  pct = round(touched * 100 / total)   (total == 0 হলে ওই বিষয় বাদ)
"""

import html
from collections import Counter

# ------------------------------------------------------------------ theme
_CHART_W = 640
_CHART_BAR_FILL = "#3aa6d6"
_CHART_TXT = "#e8eef6"
_CHART_MUTED = "#93a3b8"
_CHART_LINE = "#263449"
_CHART_BOX_FILL = "#182233"
_CHART_TITLE_FILL = "#12314a"
_CHART_WEAK_FILL = "#5a2436"
_CHART_WEAK_LINE = "#c94f6d"
_CHART_FONT = "'Hind Siliguri','Segoe UI',sans-serif"
_CHART_CONCEPT_CAP = 14

_CHART_KINDS = ("coverage", "wrong", "bank", "activity")


# ------------------------------------------------------- global fallbacks
# সব lookup CALL TIME-এ globals() থেকে — paste করলে host-এর helper জেতে,
# test-এ stub দিলে stub জেতে। কোনো helper না থাকলে নিরাপদ local fallback।

def _chart_bn(x):
    """Bangla digits: host _bn (study pack) বা _bn_num থাকলে সেটা,
    না থাকলে স্থানীয় translate।"""
    for _name in ("_bn", "_bn_num"):
        _fn = globals().get(_name)
        if callable(_fn):
            try:
                return str(_fn(x))
            except Exception:
                pass
    return str(x).translate(str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯"))


def _chart_no_data():
    _v = globals().get("_NO_DATA")
    return str(_v) if _v else "এখনো ডেটা নেই"


def _chart_resolve(name, explicit, want_type, empty):
    """host resolver (_resolve_*) থাকলে তাকে explicit arg দিয়ে ডাকা হয়;
    না থাকলে explicit নিজেই, তাও না থাকলে খালি মান।"""
    _fn = globals().get(name)
    if callable(_fn):
        try:
            _out = _fn(explicit)
        except TypeError:
            try:
                _out = _fn()
            except Exception:
                _out = None
        except Exception:
            _out = None
        if isinstance(_out, want_type):
            return _out
        return empty
    if isinstance(explicit, want_type):
        return explicit
    return empty


def _chart_progress(progress=None):
    return _chart_resolve("_resolve_progress", progress, dict, {})


def _chart_wrong(wrong=None):
    return _chart_resolve("_resolve_wrong", wrong, list, [])


def _chart_lessons(lessons=None):
    return _chart_resolve("_resolve_lessons", lessons, dict, {})


def _chart_bank(bank=None):
    return _chart_resolve("_resolve_bank", bank, dict, {})


def _chart_wrong_counts(wrong):
    """বিষয়ভিত্তিক ভুলের Counter — host _wrong_counts_by_subject থাকলে
    সেটাই; না থাকলে একই নিয়মে স্থানীয় গণনা।"""
    _fn = globals().get("_wrong_counts_by_subject")
    if callable(_fn):
        try:
            _out = _fn(wrong)
            if isinstance(_out, Counter):
                return _out
            if isinstance(_out, dict):
                return Counter(_out)
        except Exception:
            pass
    _c = Counter()
    for _w in wrong or []:
        if isinstance(_w, dict):
            _c[str(_w.get("subject") or "অজানা বিষয়")] += 1
    return _c


def _chart_esc(x):
    return html.escape(str(x if x is not None else ""), quote=True)


def _chart_val_text(value, unit):
    """SVG-তে দেখানোর মান: Bangla digit + unit (% হলে গায়ে লেগে, নাহলে ফাঁক দিয়ে)।"""
    _t = _chart_bn(value)
    _u = str(unit or "")
    if not _u:
        return _t
    if _u == "%":
        return _t + "%"
    return _t + " " + _u


def _chart_subject_in_text(text, bank, lessons):
    """বিষয় শনাক্ত: host _subject_in_text থাকলে সেটা (study pack-এর
    signature (text, bank, lessons)); না থাকলে bank/lessons-এর key
    সরাসরি text-এ খোঁজা হয়। শেষ ভরসা host _detect_subject।"""
    _fn = globals().get("_subject_in_text")
    if callable(_fn):
        try:
            _out = _fn(text, bank, lessons)
        except TypeError:
            try:
                _out = _fn(text)
            except Exception:
                _out = None
        except Exception:
            _out = None
        if _out:
            return str(_out)
    _raw = str(text or "")
    for _subj in list((bank or {}).keys()) + \
            [s for s in (lessons or {}).keys() if s not in (bank or {})]:
        if _subj and str(_subj) in _raw:
            return str(_subj)
    _fn2 = globals().get("_detect_subject")
    if callable(_fn2):
        try:
            _out = _fn2(_raw)
        except TypeError:
            try:
                _out = _fn2(_raw, _raw.lower())
            except Exception:
                _out = None
        except Exception:
            _out = None
        if _out:
            return str(_out)
    return None


def _chart_host_text(name, *args, **kwargs):
    """concept_map_text / coverage_text-কে host globals থেকে ডাকে;
    signature না মিললে শুধু positional দিয়ে আবার চেষ্টা। না থাকলে None।"""
    _fn = globals().get(name)
    if not callable(_fn):
        return None
    try:
        return _fn(*args, **kwargs)
    except TypeError:
        try:
            return _fn(*args)
        except Exception:
            return None
    except Exception:
        return None


def _chart_num(x):
    try:
        return int(x or 0)
    except Exception:
        try:
            return int(float(x))
        except Exception:
            return 0


# =====================================================================
#  সিরিজ তৈরি — আসল ডেটা থেকে; ডেটা না থাকলে None (কিছু বানানো হয় না)
# =====================================================================

def chart_series(kind, progress=None, wrong=None, lessons=None, bank=None):
    """kind অনুযায়ী চার্ট-সিরিজ ফেরত দেয়:
      {"title": str, "labels": [str], "values": [number], "unit": str}
    ডেটা না থাকলে (বা অজানা kind হলে) None।

    kinds:
      "coverage" — বিষয়ভিত্তিক সিলেবাস-কভারেজ % (coverage_text-এর
                   হিসাবের exact mirror; lessons-এর ক্রমে)
      "wrong"    — ভুলের খাতায় বিষয়ভিত্তিক ভুলের সংখ্যা (বেশি থেকে কম)
      "bank"     — OFFLINE_BANK-এ বিষয়ভিত্তিক প্রশ্নের সংখ্যা (bank-এর ক্রমে)
      "activity" — বিষয়ভিত্তিক sessions + mock_tests (progress-এর ক্রমে)
    """
    kind = str(kind or "").strip().lower()

    if kind == "coverage":
        lessons = _chart_lessons(lessons)
        progress = _chart_progress(progress)
        labels, values = [], []
        for _subj in (lessons or {}).keys():
            _steps = lessons.get(_subj) or []
            _total = len(_steps)
            if _total <= 0:
                continue
            _topics = [str(_s.get("topic") or "") for _s in _steps
                       if isinstance(_s, dict)]
            _ent = progress.get(_subj) or {}
            if not isinstance(_ent, dict):
                _ent = {}
            _touched = set()
            _lt = str(_ent.get("last_topic") or "")
            if _lt and _lt in _topics:
                _touched.add(_lt)
            for _w in _ent.get("weak", []) or []:
                if str(_w) in _topics:
                    _touched.add(str(_w))
            labels.append(str(_subj))
            values.append(round(len(_touched) * 100 / _total))
        if not labels:
            return None
        return {"title": "সিলেবাস-কভারেজ", "labels": labels,
                "values": values, "unit": "%"}

    if kind == "wrong":
        wrong = _chart_wrong(wrong)
        _counts = _chart_wrong_counts(wrong)
        _pairs = [(s, c) for s, c in _counts.most_common() if c > 0]
        if not _pairs:
            return None
        return {"title": "বিষয়ভিত্তিক ভুল (ভুলের খাতা)",
                "labels": [str(s) for s, _c in _pairs],
                "values": [int(c) for _s, c in _pairs], "unit": "টি ভুল"}

    if kind == "bank":
        bank = _chart_bank(bank)
        labels, values = [], []
        for _subj in (bank or {}).keys():
            _n = len(bank.get(_subj) or [])
            if _n > 0:
                labels.append(str(_subj))
                values.append(int(_n))
        if not labels:
            return None
        return {"title": "প্রশ্ন-ব্যাংকে বিষয়ভিত্তিক প্রশ্ন",
                "labels": labels, "values": values, "unit": "টি প্রশ্ন"}

    if kind == "activity":
        progress = _chart_progress(progress)
        labels, values = [], []
        for _subj in (progress or {}).keys():
            _ent = progress.get(_subj) or {}
            if not isinstance(_ent, dict):
                continue
            labels.append(str(_subj))
            values.append(_chart_num(_ent.get("sessions", 0)) +
                          _chart_num(_ent.get("mock_tests", 0)))
        if not labels or sum(values) <= 0:
            return None
        return {"title": "পড়ার কার্যকলাপ (সেশন + মক টেস্ট)",
                "labels": labels, "values": values, "unit": "টি"}

    return None


# =====================================================================
#  SVG — বার চার্ট
# =====================================================================

def _chart_empty_svg(title=None):
    """series না থাকলে দেখানোর মতো নিরীহ SVG (crash নয়)।"""
    _t = _chart_esc(title or _chart_no_data())
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_CHART_W}" '
        f'height="64" viewBox="0 0 {_CHART_W} 64" role="img" '
        f'style="background:transparent">'
        f'<text x="16" y="38" font-family="{_CHART_FONT}" font-size="15" '
        f'fill="{_CHART_MUTED}">{_t}</text></svg>')


def svg_bar_chart(series):
    """Horizontal-bar SVG (str)। width 640, viewBox, স্বচ্ছ background,
    বার #3aa6d6, লেখা #e8eef6 / muted #93a3b8; সব text escape করা,
    মান Bangla digit-এ। series None/খালি হলে no-data SVG।"""
    if not isinstance(series, dict):
        return _chart_empty_svg()
    _labels = [str(x) for x in (series.get("labels") or [])]
    _values = list(series.get("values") or [])
    if not _labels or not _values:
        return _chart_empty_svg(series.get("title"))
    _n = min(len(_labels), len(_values))
    _labels, _values = _labels[:_n], _values[:_n]
    _unit = str(series.get("unit") or "")
    _title = str(series.get("title") or "চার্ট")

    _max = 0
    for _v in _values:
        try:
            _max = max(_max, float(_v))
        except Exception:
            pass
    if _max <= 0:
        _max = 1

    _label_w = 176          # বামে বিষয়ের নামের জায়গা
    _bar_x = _label_w + 8
    _bar_max_w = _CHART_W - _bar_x - 92   # ডানে মান-লেবেলের জায়গা
    _row_h = 34
    _top = 40
    _height = _top + _n * _row_h + 10

    _out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_CHART_W}" '
        f'height="{_height}" viewBox="0 0 {_CHART_W} {_height}" '
        f'role="img" style="background:transparent">',
        f"<title>{_chart_esc(_title)}</title>",
        f'<text x="8" y="24" font-family="{_CHART_FONT}" font-size="16" '
        f'font-weight="700" fill="{_CHART_TXT}">{_chart_esc(_title)}</text>',
    ]
    for _i in range(_n):
        _v = _values[_i]
        try:
            _fv = float(_v)
        except Exception:
            _fv = 0
        _y = _top + _i * _row_h
        _bw = max(2, int(_fv / _max * _bar_max_w)) if _fv > 0 else 0
        _ty = _y + 20
        _out.append(
            f'<text x="8" y="{_ty}" font-family="{_CHART_FONT}" '
            f'font-size="13.5" fill="{_CHART_TXT}">'
            f'{_chart_esc(_labels[_i])}</text>')
        if _bw > 0:
            _out.append(
                f'<rect x="{_bar_x}" y="{_y + 4}" width="{_bw}" '
                f'height="18" rx="4" fill="{_CHART_BAR_FILL}"/>')
        _out.append(
            f'<text x="{_bar_x + _bw + 8}" y="{_ty}" '
            f'font-family="{_CHART_FONT}" font-size="13.5" '
            f'fill="{_CHART_MUTED}">'
            f'{_chart_esc(_chart_val_text(_v, _unit))}</text>')
    _out.append("</svg>")
    return "".join(_out)


# =====================================================================
#  SVG — লাইন চার্ট
# =====================================================================

def svg_line_chart(series):
    """সাধারণ polyline SVG (str): পয়েন্টে dot + মান-লেবেল, নিচে
    বিষয়ের নাম। একই theme/escaping/Bangla-digit নিয়ম বার চার্টের মতো।
    series None/খালি হলে no-data SVG।"""
    if not isinstance(series, dict):
        return _chart_empty_svg()
    _labels = [str(x) for x in (series.get("labels") or [])]
    _values = list(series.get("values") or [])
    if not _labels or not _values:
        return _chart_empty_svg(series.get("title"))
    _n = min(len(_labels), len(_values))
    _labels, _values = _labels[:_n], _values[:_n]
    _unit = str(series.get("unit") or "")
    _title = str(series.get("title") or "চার্ট")

    _max = 0
    for _v in _values:
        try:
            _max = max(_max, float(_v))
        except Exception:
            pass
    if _max <= 0:
        _max = 1

    _height = 264
    _left, _right, _plot_top, _plot_bottom = 44, 20, 52, 216
    _plot_w = _CHART_W - _left - _right
    _plot_h = _plot_bottom - _plot_top

    def _px(i):
        if _n == 1:
            return _left + _plot_w // 2
        return int(_left + i * _plot_w / (_n - 1))

    def _py(v):
        try:
            _fv = float(v)
        except Exception:
            _fv = 0
        return int(_plot_bottom - (_fv / _max) * _plot_h)

    _pts = [(_px(i), _py(_values[i])) for i in range(_n)]
    _points_attr = " ".join(f"{x},{y}" for x, y in _pts)

    _out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_CHART_W}" '
        f'height="{_height}" viewBox="0 0 {_CHART_W} {_height}" '
        f'role="img" style="background:transparent">',
        f"<title>{_chart_esc(_title)}</title>",
        f'<text x="8" y="24" font-family="{_CHART_FONT}" font-size="16" '
        f'font-weight="700" fill="{_CHART_TXT}">{_chart_esc(_title)}</text>',
        f'<line x1="{_left}" y1="{_plot_bottom}" x2="{_CHART_W - _right}" '
        f'y2="{_plot_bottom}" stroke="{_CHART_LINE}" stroke-width="1"/>',
    ]
    if _n > 1:
        _out.append(
            f'<polyline points="{_points_attr}" fill="none" '
            f'stroke="{_CHART_BAR_FILL}" stroke-width="2.5" '
            f'stroke-linejoin="round" stroke-linecap="round"/>')
    for _i, (_x, _y) in enumerate(_pts):
        _out.append(
            f'<circle cx="{_x}" cy="{_y}" r="4.5" fill="{_CHART_BAR_FILL}"/>')
        _out.append(
            f'<text x="{_x}" y="{max(12, _y - 10)}" text-anchor="middle" '
            f'font-family="{_CHART_FONT}" font-size="13" '
            f'fill="{_CHART_TXT}">'
            f'{_chart_esc(_chart_val_text(_values[_i], _unit))}</text>')
        _out.append(
            f'<text x="{_x}" y="{_plot_bottom + 22}" text-anchor="middle" '
            f'font-family="{_CHART_FONT}" font-size="12.5" '
            f'fill="{_CHART_MUTED}">{_chart_esc(_labels[_i])}</text>')
    _out.append("</svg>")
    return "".join(_out)


# =====================================================================
#  SVG — ধারণা-মানচিত্র (vertical chain diagram)
# =====================================================================

def concept_svg(subject, progress=None, lessons=None):
    """এক বিষয়ের ধারণা-মানচিত্র: উপরে বিষয়ের title node, নিচে তীর
    দিয়ে জোড়া topic box-এর উল্লম্ব শৃঙ্খল। দুর্বল টপিক (progress-এর
    weak[]) আলাদা fill (#5a2436) + '⚠' prefix পায়। সর্বোচ্চ ১৪টা topic
    box; বাকিগুলো শেষে একটা '+আরও Nটি' node-এ দেখানো হয়।
    বিষয়ের কোনো lesson না থাকলে None (concept_map_text-এর no-data
    শর্তের mirror)। সব text escape করা।"""
    lessons = _chart_lessons(lessons)
    progress = _chart_progress(progress)
    subject = str(subject or "").strip()
    if not subject:
        return None
    _steps = [s for s in (lessons.get(subject) or []) if isinstance(s, dict)]
    if not _steps:
        return None
    _topics = [str(s.get("topic") or "সাধারণ") for s in _steps]

    _ent = progress.get(subject) or {}
    if not isinstance(_ent, dict):
        _ent = {}
    _weak_set = set(str(w) for w in (_ent.get("weak", []) or []))

    _shown = _topics[:_CHART_CONCEPT_CAP]
    _extra = len(_topics) - len(_shown)

    # node তালিকা: (text, kind) — kind: title / topic / weak / more
    _nodes = [(subject, "title")]
    for _t in _shown:
        _nodes.append((_t, "weak" if _t in _weak_set else "topic"))
    if _extra > 0:
        _nodes.append((f"+আরও {_chart_bn(_extra)}টি", "more"))

    _box_w, _box_h, _gap = 480, 36, 16
    _box_x = (_CHART_W - _box_w) // 2
    _top_pad = 14
    _height = _top_pad * 2 + len(_nodes) * _box_h + \
        (len(_nodes) - 1) * _gap

    _out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_CHART_W}" '
        f'height="{_height}" viewBox="0 0 {_CHART_W} {_height}" '
        f'role="img" style="background:transparent">',
        "<defs>"
        f'<marker id="chartArrow" markerWidth="8" markerHeight="8" '
        f'refX="6" refY="3" orient="auto">'
        f'<path d="M0,0 L7,3 L0,6 Z" fill="{_CHART_BAR_FILL}"/></marker>'
        "</defs>",
        f"<title>{_chart_esc('ধারণা-মানচিত্র — ' + subject)}</title>",
    ]
    _cx = _CHART_W // 2
    for _i, (_text, _kind) in enumerate(_nodes):
        _y = _top_pad + _i * (_box_h + _gap)
        if _i > 0:
            _y1 = _y - _gap - 1
            _out.append(
                f'<line x1="{_cx}" y1="{_y1}" x2="{_cx}" y2="{_y - 2}" '
                f'stroke="{_CHART_BAR_FILL}" stroke-width="2" '
                f'marker-end="url(#chartArrow)"/>')
        if _kind == "title":
            _fill, _stroke, _weight = _CHART_TITLE_FILL, _CHART_BAR_FILL, "700"
            _disp = _text
        elif _kind == "weak":
            _fill, _stroke, _weight = \
                _CHART_WEAK_FILL, _CHART_WEAK_LINE, "600"
            _disp = "⚠ " + _text
        elif _kind == "more":
            _fill, _stroke, _weight = _CHART_BOX_FILL, _CHART_LINE, "400"
            _disp = _text
        else:
            _fill, _stroke, _weight = _CHART_BOX_FILL, _CHART_LINE, "400"
            _disp = _text
        if len(_disp) > 54:
            _disp = _disp[:54].rstrip() + "…"
        _out.append(
            f'<rect x="{_box_x}" y="{_y}" width="{_box_w}" '
            f'height="{_box_h}" rx="8" fill="{_fill}" stroke="{_stroke}"/>')
        _out.append(
            f'<text x="{_cx}" y="{_y + 23}" text-anchor="middle" '
            f'font-family="{_CHART_FONT}" font-size="14" '
            f'font-weight="{_weight}" fill="{_CHART_TXT}">'
            f'{_chart_esc(_disp)}</text>')
    _out.append("</svg>")
    return "".join(_out)


# =====================================================================
#  চ্যাট ডিসপ্যাচার — উত্তরে [[CHART:...]] মার্কার বসায়
#  (frontend মার্কার দেখে /api/chart থেকে SVG এনে inline বসায়;
#   speak() মার্কার পড়ে না — INTEGRATION-A.md দেখো)
# =====================================================================

_CHART_INTROS = {
    "coverage": "📊 তোমার সিলেবাস-কভারেজের চার্ট:",
    "wrong": "📊 ভুলের খাতা অনুযায়ী বিষয়ভিত্তিক ভুলের চার্ট:",
    "bank": "📊 অফলাইন প্রশ্ন-ব্যাংকে বিষয়ভিত্তিক প্রশ্নের চার্ট:",
    "activity": "📊 তোমার পড়ার কার্যকলাপের চার্ট (সেশন + মক টেস্ট):",
}
_CHART_SCORE_INTRO = (
    "📊 সৎ কথা: প্রতি টেস্টের স্কোরের ইতিহাস আলাদা করে রাখা নেই, "
    "তাই স্কোরের বদলে তোমার সেশন + মক টেস্টের সংখ্যার চার্ট দেখাচ্ছি:")


def _chart_kind_no_data(kind):
    """নির্দিষ্ট kind-এর চার্ট চাওয়া হলেও তার ডেটা নেই — kind ধরে
    কারণসহ সহজ বাংলা বার্তা (_NO_DATA host থেকে call time-এ নেওয়া)।"""
    _nd = _chart_no_data()
    _why = {
        "wrong": ("ভুলের খাতা খালি — এখনো কোনো মক টেস্টে ভুল জমেনি। "
                  "মক টেস্ট দিলে ভুলগুলো জমবে, তখন ভুলের চার্ট আঁকব।"),
        "bank": ("অফলাইন প্রশ্ন-ব্যাংক খালি — কোনো বিষয়েই প্রশ্ন পাইনি, "
                 "তাই প্রশ্নের চার্ট আঁকা যাচ্ছে না।"),
        "activity": ("পড়ার রেকর্ডে এখনো কোনো সেশন বা মক টেস্ট নেই। "
                     "'শেখাও' বলে পড়া শুরু করলেই কার্যকলাপের হিসাব "
                     "শুরু হবে, তখন চার্ট আঁকব।"),
        "coverage": ("পাঠের তালিকা বা কভারেজের ডেটা পাইনি। পড়া শুরু "
                    "করলেই কভারেজ হিসাব শুরু হবে।"),
    }.get(kind, "এই ধরনের ডেটা এখনো জমেনি।")
    return f"{_nd} — চার্ট আঁকার মতো ডেটা পাইনি: {_why}"


def chart_reply(text):
    """চার্ট/ডায়াগ্রাম চাওয়া হলে উত্তর + মার্কার, নাহলে None।

    নিয়ম:
      * 'ধারণা' + 'মানচিত্র' + শনাক্তযোগ্য বিষয় -> concept_map_text(...)
        + [[CHART:concept:<subject>]] (concept ডেটা থাকলেই; নাহলে None,
        যাতে পুরনো route-ই উত্তর দেয়)।
      * 'কভারেজ' -> coverage_text(...) + [[CHART:coverage]]
        (coverage সিরিজ থাকলেই; নাহলে None)।
      * 'চার্ট' -> kind বাছাই: 'ভুল'->wrong, 'প্রশ্ন'->bank,
        'স্কোর'/'কার্যকলাপ'->activity, 'কভারেজ'->coverage;
        নির্দিষ্ট kind না চাইলে coverage/activity/wrong/bank ক্রমে
        যেটায় প্রথম ডেটা মেলে। নির্দিষ্ট kind চেয়ে তার ডেটা না
        থাকলে অন্য kind-এর চার্ট চুপিচুপি বসানো হয় না — সেই
        kind-এরই সহজ বাংলা no-data কারণ বলা হয় (সততার নিয়ম)।
        'স্কোর' চাইলে intro-তে সত্যটা বলা হয়: per-test স্কোরের
        ইতিহাস রাখা নেই, চার্টে সেশন+টেস্ট সংখ্যা (activity)।
        কোনো kind-এই ডেটা না থাকলেও একই ধাঁচের no-data বার্তা।
      * বাকি সব ক্ষেত্রে None।
    """
    text = str(text or "").strip()
    if not text:
        return None
    progress = _chart_progress()
    wrong = _chart_wrong()
    lessons = _chart_lessons()
    bank = _chart_bank()

    # --- ধারণা-মানচিত্র (ডায়াগ্রাম)
    if "ধারণা" in text and "মানচিত্র" in text:
        _subj = _chart_subject_in_text(text, bank, lessons)
        if not _subj:
            return None
        _steps = [s for s in (lessons.get(_subj) or [])
                  if isinstance(s, dict)]
        if not _steps:
            return None
        _body = _chart_host_text(
            "concept_map_text", _subj, progress=progress, lessons=lessons)
        if _body is None:
            _body = (f"🗺️ ধারণা-মানচিত্র — {_subj}\n"
                     + " → ".join(str(s.get("topic") or "সাধারণ")
                                  for s in _steps))
        return str(_body) + f"\n[[CHART:concept:{_subj}]]"

    # --- কভারেজ (টেক্সট রিপোর্ট + চার্ট একসাথে)
    if "কভারেজ" in text:
        if chart_series("coverage", progress=progress, wrong=wrong,
                        lessons=lessons, bank=bank) is None:
            return None
        _body = _chart_host_text(
            "coverage_text", progress=progress, lessons=lessons)
        if _body is None:
            _body = _CHART_INTROS["coverage"]
        return str(_body) + "\n[[CHART:coverage]]"

    # --- সাধারণ চার্ট চাওয়া
    if "চার্ট" in text:
        if "ভুল" in text:
            _want = "wrong"
        elif "প্রশ্ন" in text:
            _want = "bank"
        elif "স্কোর" in text or "কার্যকলাপ" in text:
            _want = "activity"
        elif "কভারেজ" in text:
            _want = "coverage"
        else:
            _want = None
        _series_kw = dict(progress=progress, wrong=wrong,
                          lessons=lessons, bank=bank)
        if _want is not None:
            if chart_series(_want, **_series_kw) is not None:
                if _want == "activity" and "স্কোর" in text:
                    _intro = _CHART_SCORE_INTRO
                else:
                    _intro = _CHART_INTROS[_want]
                return _intro + f"\n[[CHART:{_want}]]"
            # নির্দিষ্ট kind চাওয়া হয়েছে, কিন্তু তার ডেটাই নেই —
            # অন্য চার্ট বসিয়ে ভান করা হবে না; কারণটা বলা হলো।
            return _chart_kind_no_data(_want)
        for _kind in ("coverage", "activity", "wrong", "bank"):
            if chart_series(_kind, **_series_kw) is not None:
                return _CHART_INTROS[_kind] + f"\n[[CHART:{_kind}]]"
        return (f"{_chart_no_data()} — চার্ট আঁকার মতো ডেটা পাইনি। "
                "পড়া শুরু করলে, মক টেস্ট দিলে বা ভুলের খাতায় ভুল জমলে "
                "সেই আসল রেকর্ড দিয়েই চার্ট আঁকব — কোনো সংখ্যা বানিয়ে "
                "দেব না। তুমি চাইলে 'শেখাও' বলে পড়া শুরু করো, কিংবা "
                "একটা মক টেস্ট দাও।")
    return None


# -*- coding: utf-8 -*-
"""
Desktop Sokhi v1.9.0 — Elite Analysis Feature Pack (analysis cluster)
======================================================================
Self-contained snippets for integration into sokhi.py (v1.9.0).
Coordinator: paste this whole file at top level in sokhi.py AFTER the
v1.5 study-pack block (i.e. after study_pack_handle's def) and BEFORE
the daily-pack section — see INTEGRATION-ANALYSIS.md for the exact
anchors — then wire the one dispatch block described there.

Features:
  #763 ea_wrong_cost_text()        ভুলের খরচ র‍্যাঙ্কিং
  #764 ea_progress_series()        অগ্রগতির ডেটা-সিরিজ (machine-readable)
       ea_progress_curve_text()    অগ্রগতি-বক্ররেখা (text বার-কার্ভ)
  #765 ea_projection_text()        প্রস্তুতি অভিক্ষেপ (F8-ধাঁচের + campaign)

House rules honoured:
  * 100% free, offline-only — reads ONLY OFFLINE_BANK, OFFLINE_LESSONS,
    study-progress.json, study-wrong-book.json and growth-diary.json.
    No web, no Gemini.
  * Never fabricates statistics — every number is a count/sum of what
    actually exists in those banks/files. Insufficient data -> an
    honest "এখনো ডেটা নেই" / "তথ্য এখনো কম" Bangla line, never
    invented numbers. #763 says plainly in its own text that the
    "খরচ" is marks lost in mock/practice — NOT real-exam marks.
  * Pure-ish functions: data can be injected via parameters (used by
    test_elite_analysis_pack.py). When a parameter is None, the
    function falls back to the module globals of the host sokhi.py,
    looked up at CALL time via globals().get(...) with the EXACT
    existing host names: OFFLINE_BANK, OFFLINE_LESSONS, load_json,
    _STUDY_PROGRESS_FILE, _WRONG_BOOK_FILE, FF_GROWTH_FILE.
  * Bangla digits via a LOCAL ea_bn() helper (self-contained mirror of
    the study pack's _bn() / the host's _bn_num), so the pack works
    standalone in tests.
  * ALL top-level symbols carry the ea_/EA_ prefix, so this pack can
    never collide with the sibling v1.9 packs (et_, ep_, ee_, es_)
    or with host code. (ea_bn mirrors the study pack's _bn, and
    EA_NO_DATA mirrors its _NO_DATA = "এখনো ডেটা নেই".)

Verified data shapes (host sokhi.py):
  study-progress.json:
    {subject: {sessions:int, mock_tests:int, total_steps:int,
               weak:[str], last_topic:str, last_date:"YYYY-MM-DD"}}
  study-wrong-book.json (max 500): list of dicts, each:
    {"q": str, "options": [str x4], "correct": str (correct option TEXT),
     "your_answer": str (picked option TEXT), "subject": str,
     "topic": str, "date": "YYYY-MM-DD"}
  growth-diary.json (max 120): list of dicts, each:
    {"date": "YYYY-MM-DD", "facts": int, "likes": int,
     "learned_notes": int, "rules": int, "knowledge": int,
     "interactions": int}   (host global: FF_GROWTH_FILE)
  OFFLINE_BANK:
    {subject: [{"q": str, "options": [str x4], "answer": int (0-3),
                "topic": str}]}
  OFFLINE_LESSONS:
    {subject: [{"topic": str, "text": str, "check_q": str,
                "check_answers": [str], "alt": str}]}
"""

import math
from collections import Counter
from datetime import date, timedelta

# ------------------------------------------------------------------ digits

EA_BN_DIGITS_MAP = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")


def ea_bn(x):
    """Local mirror of the study pack's _bn() / host _bn_num():
    English digits -> Bangla digits."""
    return str(x).translate(EA_BN_DIGITS_MAP)


EA_NO_DATA = "এখনো ডেটা নেই"


def ea_fmt_num(x):
    """সংখ্যা দেখানোর জন্য: পূর্ণসংখ্যা হলে দশমিক ছাড়া, নাহলে ১ ঘর
    দশমিক (Bangla digits-এ)।"""
    try:
        x = float(x)
    except Exception:
        return ea_bn(x)
    if x == int(x):
        return ea_bn(int(x))
    return ea_bn(f"{x:.1f}")


def ea_parse_date(x):
    """date / 'YYYY-MM-DD' str -> date, না পারলে None।"""
    if x is None:
        return None
    if isinstance(x, date):
        return x
    try:
        return date.fromisoformat(str(x)[:10])
    except Exception:
        return None


def ea_resolve_today(today=None):
    d = ea_parse_date(today)
    return d if d is not None else date.today()


# ------------------------------------------------------- global fallbacks
# These helpers deliberately look names up in globals() at CALL time, so
# (a) the pack works when pasted into sokhi.py (host globals win), and
# (b) tests can stub elite_analysis_pack.OFFLINE_BANK etc. or pass data
# directly. (Copied in style from the study pack's _resolve_* helpers.)


def ea_resolve_bank(bank=None):
    if bank is not None:
        return bank if isinstance(bank, dict) else {}
    g = globals().get("OFFLINE_BANK")
    return g if isinstance(g, dict) else {}


def ea_resolve_lessons(lessons=None):
    if lessons is not None:
        return lessons if isinstance(lessons, dict) else {}
    g = globals().get("OFFLINE_LESSONS")
    return g if isinstance(g, dict) else {}


def ea_load_via_host(path, default):
    fn = globals().get("load_json")
    if callable(fn) and path is not None:
        try:
            return fn(path, default)
        except Exception:
            return default
    return default


def ea_resolve_progress(progress=None):
    if progress is not None:
        return progress if isinstance(progress, dict) else {}
    path = globals().get("_STUDY_PROGRESS_FILE")
    data = ea_load_via_host(path, {})
    return data if isinstance(data, dict) else {}


def ea_resolve_wrong(wrong=None):
    if wrong is not None:
        return wrong if isinstance(wrong, list) else []
    path = globals().get("_WRONG_BOOK_FILE")
    data = ea_load_via_host(path, [])
    return data if isinstance(data, list) else []


def ea_resolve_diary(diary=None):
    if diary is not None:
        return diary if isinstance(diary, list) else []
    path = globals().get("FF_GROWTH_FILE")
    if path is None:
        path = globals().get("EA_GROWTH_FILE")
    if path is None:
        path = globals().get("_GROWTH_DIARY_FILE")
    data = ea_load_via_host(path, [])
    return data if isinstance(data, list) else []


def ea_wrongs_by_day(wrong):
    """তারিখওয়ালা wrong-book এন্ট্রি থেকে {date: count} (Counter)।
    তারিখহীন/ভাঙা এন্ট্রি বাদ — কিছু বানানো হয় না।"""
    c = Counter()
    for w in wrong or []:
        if not isinstance(w, dict):
            continue
        d = ea_parse_date(w.get("date"))
        if d is not None:
            c[d] += 1
    return c


# =====================================================================
#  #763 ভুলের খরচ র‍্যাঙ্কিং
# =====================================================================

def ea_wrong_weight(entry_date, today_d):
    """একটা ভুলের recency-ওজন (সূত্রটা ea_wrong_cost_text-এর রিপোর্টেও
    লেখা থাকে):
      শেষ ৩০ দিনের মধ্যে ভুল      -> ×২
      ৩১–৯০ দিন আগের ভুল          -> ×১.৫
      ৯০ দিনের বেশি পুরনো ভুল     -> ×১
      তারিখ নেই / পড়া যায়নি      -> ×১ (সবচেয়ে কম ধরা হয়)
    ভবিষ্যতের তারিখ থাকলে বয়স ০ ধরা হয় (মানে ×২ ঘরে পড়ে)।"""
    d = ea_parse_date(entry_date)
    if d is None:
        return 1.0
    age = (today_d - d).days
    if age < 0:
        age = 0
    if age <= 30:
        return 2.0
    if age <= 90:
        return 1.5
    return 1.0


def ea_wrong_cost_text(wrong=None, today=None):
    """Wrong-book-কে (বিষয়, টপিক) ধরে গুনে recency-ওজনসহ 'খরচ' স্কোরে
    সাজানো র‍্যাঙ্কিং + বিষয়ভিত্তিক মোট।

    সতর্ক বাক্য (রিপোর্টেও থাকে): এই 'খরচ' মানে মক টেস্ট/অনুশীলনীতে
    যেসব প্রশ্নে নম্বর হারিয়েছ তার ধারণা — এটা আসল পরীক্ষার নম্বর
    নয়, আর ভবিষ্যতের পরীক্ষায় ঠিক কত নম্বর যাবে তাও নয়। শুধু কোন
    টপিকে বেশি অনুশীলন দরকার, সেটা বোঝার জন্য সাজানো তালিকা।"""
    wrong = ea_resolve_wrong(wrong)
    rows_in = [w for w in (wrong or []) if isinstance(w, dict)]
    if not rows_in:
        return (f"{EA_NO_DATA} — ভুলের খাতা খালি। এখনো কোনো মক টেস্টে "
                "ভুল জমা হয়নি, তাই খরচের হিসাব করার কিছু নেই। মক টেস্ট "
                "দিলে ভুলগুলো এখানে জমবে, তখন র‍্যাঙ্কিং দেখতে পাবে।")
    today_d = ea_resolve_today(today)

    groups = {}   # (subject, topic) -> [count, score, last_date_str]
    subjects = {}  # subject -> [count, score]
    for w in rows_in:
        subj = str(w.get("subject") or "অজানা বিষয়")
        topic = str(w.get("topic") or "সাধারণ")
        wt = ea_wrong_weight(w.get("date"), today_d)
        d = ea_parse_date(w.get("date"))
        dstr = str(d) if d is not None else ""
        g = groups.setdefault((subj, topic), [0, 0.0, ""])
        g[0] += 1
        g[1] += wt
        if dstr > g[2]:
            g[2] = dstr
        s = subjects.setdefault(subj, [0, 0.0])
        s[0] += 1
        s[1] += wt

    ranked = sorted(groups.items(),
                    key=lambda kv: (-kv[1][1], -kv[1][0], kv[0][0], kv[0][1]))
    total_n = sum(v[0] for v in groups.values())
    total_score = sum(v[1] for v in groups.values())

    lines = ["💸 ভুলের খরচ র‍্যাঙ্কিং",
             "খরচ-স্কোরের সূত্র: সাম্প্রতিক ভুলের ওজন বেশি — শেষ ৩০ দিনের "
             "ভুল ×২, ৩১–৯০ দিন আগের ভুল ×১.৫, তার চেয়ে পুরনো (বা "
             "তারিখহীন) ভুল ×১। স্কোর = সব ভুলের ওজনের যোগফল।",
             "সতর্কতা: এই 'খরচ' মানে মক টেস্ট আর অনুশীলনীতে যেসব প্রশ্নে "
             "তুমি নম্বর হারিয়েছ, তার হিসাব — এটা আসল পরীক্ষার নম্বর "
             "নয়। কোন টপিকে আগে অনুশীলন দরকার, সেটা ঠিক করতেই এই তালিকা।",
             "",
             f"মোট ভুল: {ea_bn(total_n)}টি, মোট খরচ-স্কোর: "
             f"{ea_fmt_num(total_score)}।",
             "",
             "টপিক ধরে খরচ (বেশি থেকে কম):"]
    cap = 15
    for (subj, topic), (cnt, score, last) in ranked[:cap]:
        last_txt = f", শেষ ভুল: {ea_bn(last)}" if last else ""
        lines.append(f"• {subj} / {topic} — {ea_bn(cnt)}বার ভুল, "
                     f"স্কোর {ea_fmt_num(score)}{last_txt}")
    if len(ranked) > cap:
        lines.append(f"(আরও {ea_bn(len(ranked) - cap)}টি টপিক আছে — "
                     "শীর্ষগুলো আগে ঠিক করলেই বেশিরভাগ খরচ কমবে।)")
    lines.append("")
    lines.append("বিষয় ধরে মোট খরচ:")
    for subj, (cnt, score) in sorted(subjects.items(),
                                     key=lambda kv: (-kv[1][1], kv[0])):
        lines.append(f"• {subj} — {ea_bn(cnt)}টি ভুল, "
                     f"স্কোর {ea_fmt_num(score)}")
    lines.append("")
    lines.append("পরামর্শ: তালিকার একদম উপরের টপিকটা শিক্ষক মোডে ধাপে "
                 "ধাপে শিখে আবার মক টেস্ট দাও — খরচ কমতে শুরু করবে।")
    return "\n".join(lines)


# =====================================================================
#  #764 অগ্রগতি-বক্ররেখা
# =====================================================================

def ea_progress_series(wrong=None, diary=None):
    """Machine-readable অগ্রগতি-সিরিজ (ইন্টিগ্রেটর চাইলে এটা v1.8-এর
    #47 চার্ট রেন্ডারারকে খাওয়াতে পারবে — INTEGRATION-ANALYSIS.md দেখো):
      {"wrongs_by_day":     [(date_str, count), ...]   তারিখের ক্রমে,
       "cumulative_wrongs": [(date_str, running_total), ...],
       "activity_by_day":   [(date_str, interactions), ...]}
    শুধু তারিখওয়ালা এন্ট্রিই গোনা হয়; ডেটা না থাকলে খালি তালিকা।"""
    wrong = ea_resolve_wrong(wrong)
    diary = ea_resolve_diary(diary)
    by_day = ea_wrongs_by_day(wrong)
    days = sorted(by_day.keys())
    wrongs_by_day = [(str(d), int(by_day[d])) for d in days]
    cumulative = []
    run = 0
    for d in days:
        run += int(by_day[d])
        cumulative.append((str(d), run))
    act = Counter()
    for e in diary or []:
        if not isinstance(e, dict):
            continue
        d = ea_parse_date(e.get("date"))
        if d is None:
            continue
        try:
            act[d] += int(e.get("interactions", 0) or 0)
        except Exception:
            continue
    activity_by_day = [(str(d), int(act[d])) for d in sorted(act.keys())]
    return {"wrongs_by_day": wrongs_by_day,
            "cumulative_wrongs": cumulative,
            "activity_by_day": activity_by_day}


def ea_progress_curve_text(wrong=None, diary=None, today=None):
    """শেষ ১৪ ক্যালেন্ডার দিনে দিনপ্রতি ভুলের text-কার্ভ (unicode block
    বার) + সৎ ট্রেন্ড-সার: শেষ ৭ দিনের ভুল বনাম তার আগের ৭ দিনের ভুল।
    তারিখওয়ালা ডেটা না থাকলে সেটা সোজাসুজি বলা হয়।"""
    wrong = ea_resolve_wrong(wrong)
    diary = ea_resolve_diary(diary)
    by_day = ea_wrongs_by_day(wrong)
    if not by_day:
        return (f"{EA_NO_DATA} — ভুলের খাতায় তারিখওয়ালা কোনো এন্ট্রি "
                "পাইনি, তাই বক্ররেখা আঁকা যাচ্ছে না। মক টেস্ট দিলে "
                "প্রতিটা ভুল তারিখসহ জমে — তখন এখানে দিন ধরে গ্রাফ "
                "দেখতে পাবে।")
    end = ea_resolve_today(today)
    start = end - timedelta(days=13)
    window = [start + timedelta(days=i) for i in range(14)]
    in_window = sum(int(by_day.get(d, 0)) for d in window)
    if in_window == 0:
        last_d = max(by_day.keys())
        return ("📈 অগ্রগতি-বক্ররেখা\n"
                f"শেষ ১৪ দিনে ({ea_bn(str(start))} থেকে "
                f"{ea_bn(str(end))}) ভুলের খাতায় নতুন কোনো ভুল জমেনি। "
                f"আগের রেকর্ডে মোট {ea_bn(sum(by_day.values()))}টি "
                f"তারিখওয়ালা ভুল আছে, সবশেষ ভুলের তারিখ "
                f"{ea_bn(str(last_d))}। নতুন মক টেস্ট দিলেই কার্ভটা আবার "
                "নড়তে শুরু করবে।")

    max_c = max(int(by_day.get(d, 0)) for d in window)
    lines = ["📈 অগ্রগতি-বক্ররেখা — শেষ ১৪ দিনে দিনপ্রতি ভুল",
             "(ভুলের খাতার তারিখ গুনে বানানো; বার যত লম্বা, সেদিন ভুল "
             "তত বেশি।)"]
    for d in window:
        c = int(by_day.get(d, 0))
        bar = ""
        if c > 0 and max_c > 0:
            bar = "█" * max(1, round(c * 20 / max_c))
        lines.append(f"{ea_bn(d.strftime('%m-%d'))} │ {bar} {ea_bn(c)}টি")
    last7 = sum(int(by_day.get(d, 0)) for d in window[7:])
    prev7 = sum(int(by_day.get(d, 0)) for d in window[:7])
    if last7 < prev7:
        trend = "ভুল কমছে 📉"
    elif last7 > prev7:
        trend = "ভুল বাড়ছে 📈"
    else:
        trend = "ভুল প্রায় একই আছে"
    lines.append("")
    lines.append(f"ট্রেন্ড: শেষ ৭ দিনে {ea_bn(last7)}টি ভুল, তার আগের "
                 f"৭ দিনে {ea_bn(prev7)}টি ভুল — {trend}।")
    act_by_day = {d: n for d, n in
                  [(ea_parse_date(ds), n)
                   for ds, n in ea_progress_series(wrong=[], diary=diary)
                   ["activity_by_day"]]}
    act_total = sum(int(act_by_day.get(d, 0) or 0) for d in window)
    if act_total > 0:
        lines.append(f"এই ১৪ দিনে growth diary অনুযায়ী মোট কার্যকলাপ "
                     f"(কথা/ইন্টার‌্যাকশন): {ea_bn(act_total)} বার।")
    lines.append("মনে রেখো: ভুল কমা মানেই শেখা বাড়ছে — মক টেস্ট যত "
                 "বেশি দেবে, এই ছবিটা তত পরিষ্কার হবে।")
    return "\n".join(lines)


# =====================================================================
#  #765 প্রস্তুতি অভিক্ষেপ
# =====================================================================

def ea_projection_text(progress=None, lessons=None, campaign=None,
                       today=None, first_day=None):
    """F8 prediction_text()-এর ধাঁচে গতি-ভিত্তিক অভিক্ষেপ:
      rate      = মোট total_steps / অতিবাহিত দিন
      remaining = প্রতি বিষয়ে len(lessons) − min(total_steps, len)
    অতিবাহিত দিন: first_day প্যারামিটার থেকে (ইন্টিগ্রেটর host memory-র
    first_day বসিয়ে দেবে); না থাকলে progress-এর last_date-গুলোর পরিসর
    (সবচেয়ে পুরনো থেকে সবচেয়ে নতুন + ১ দিন) fallback; তাও না থাকলে
    বা ধাপ খুব কম হলে সংখ্যা বানানো হয় না — সেটা বলা হয়।

    campaign (ঐচ্ছিক, injectable) = {"exam_date": "YYYY-MM-DD", ...}
    থাকলে: বাকি দিন, দিনে দরকারি ধাপ, আর রায়ের লাইন —
    এই গতিতে শেষ হবে / ঘাটতি আছে (দিনে আরও X ধাপ দরকার)।"""
    head = "📈 প্রস্তুতি অভিক্ষেপ"
    progress = ea_resolve_progress(progress)
    lessons = ea_resolve_lessons(lessons)
    if not progress:
        return (f"{head}\n"
                f"{EA_NO_DATA} — পড়ার রেকর্ড (study-progress) এখনো নেই, "
                "তাই অভিক্ষেপ দেওয়ার মতো তথ্য পাইনি। কয়েকটা পড়ার "
                "সেশন হলেই গতি হিসাব করে বলতে পারব — সংখ্যা বানিয়ে "
                "বলব না।")
    today_d = ea_resolve_today(today)
    total_steps = 0
    total_sessions = 0
    for ent in progress.values():
        if isinstance(ent, dict):
            total_steps += int(ent.get("total_steps", 0) or 0)
            total_sessions += int(ent.get("sessions", 0) or 0)

    elapsed = None
    used_fallback = False
    fd = ea_parse_date(first_day)
    if fd is not None:
        elapsed = (today_d - fd).days
    else:
        dates = [ea_parse_date(ent.get("last_date"))
                 for ent in progress.values() if isinstance(ent, dict)]
        dates = [d for d in dates if d is not None]
        if dates:
            elapsed = (max(dates) - min(dates)).days + 1
            used_fallback = True
    if elapsed is None or elapsed < 1 or total_steps < 3:
        el_txt = ea_bn(elapsed) if elapsed is not None else "—"
        return (f"{head}\n"
                f"অভিক্ষেপের জন্য তথ্য এখনো কম (মোট ধাপ "
                f"{ea_bn(total_steps)}টা, সেশন {ea_bn(total_sessions)}টা, "
                f"হিসাবের সময়কাল {el_txt} দিন)। আর কয়েকদিন নিয়মিত "
                "পড়লেই গতি ধরে সংখ্যায় বলতে পারব — এখন অনুমান বানিয়ে "
                "বলব না।")

    rate = total_steps / elapsed
    remaining = 0
    known = []
    for subj, ent in progress.items():
        if subj in lessons and isinstance(ent, dict):
            total = len(lessons.get(subj) or [])
            covered = min(int(ent.get("total_steps", 0) or 0), total)
            if total - covered > 0:
                remaining += total - covered
                known.append(subj)
    lines = [head,
             f"তোমার গতি: দিনে গড়ে প্রায় {ea_fmt_num(round(rate, 1))} "
             f"ধাপ (মোট {ea_bn(total_steps)} ধাপ, "
             f"{ea_bn(elapsed)} দিনে)।"]
    if used_fallback:
        lines.append("(প্রথম দিনের রেকর্ড পাইনি — পড়ার রেকর্ডের "
                     "তারিখের পরিসর ধরে সময়কাল হিসাব করেছি।)")
    if not known:
        lines.append("যেসব বিষয়ে তুমি পড়ছ, সেগুলোর মোট পাঠের সংখ্যা "
                     "আমার জানা পাঠক্রমে নেই — তাই 'বাকি কত ধাপ' হিসাব "
                     "করা যাচ্ছে না। গতি শুধু এটুকুই বলতে পারি।")
        return "\n".join(lines)
    if remaining <= 0:
        lines.append("জানা পাঠক্রমের সব ধাপই তুমি ছুঁয়ে ফেলেছ — বাকি "
                     "নেই। এখন রিভিশন আর মক টেস্টেই জোর দাও।")
        return "\n".join(lines)

    days_needed = math.ceil(remaining / rate) if rate > 0 else 0
    lines.append(f"জানা পাঠক্রমে বাকি আছে {ea_bn(remaining)}টা ধাপ "
                 f"({', '.join(known)})। এই গতিতে শেষ হতে আনুমানিক "
                 f"{ea_bn(days_needed)} দিন লাগতে পারে।")
    lines.append("এটা শুধু অফলাইন পাঠক্রমের হিসাব — আসল সিলেবাস এর "
                 "চেয়ে বড় হলে সময়ও বেশি লাগবে।")

    exam_d = None
    if isinstance(campaign, dict):
        exam_d = ea_parse_date(campaign.get("exam_date"))
        if exam_d is None and campaign:
            lines.append("(ক্যাম্পেইনের পরীক্ষার তারিখটা পড়তে পারিনি "
                         "— তাই পরীক্ষা-ভিত্তিক রায় দিলাম না।)")
    if exam_d is None:
        lines.append("পরীক্ষার তারিখ বসিয়ে ক্যাম্পেইন চালু করলে আমি "
                     "বলতে পারব এই গতিতে পরীক্ষার আগেই শেষ হবে কিনা, "
                     "আর ঘাটতি থাকলে দিনে আরও কত ধাপ লাগবে।")
        return "\n".join(lines)

    days_left = (exam_d - today_d).days
    lines.append(f"পরীক্ষা: {ea_bn(str(exam_d))} — হাতে আছে "
                 f"{ea_bn(max(days_left, 0))} দিন।")
    if days_left <= 0:
        lines.append("রায়: পরীক্ষার দিন এসে গেছে বা পেরিয়ে গেছে — "
                     "এখন অভিক্ষেপের চেয়ে শেষ মুহূর্তের রিভিশনেই "
                     "কাজ হবে।")
    elif days_needed <= days_left:
        lines.append(f"রায়: ✅ এই গতিতে পরীক্ষার আগেই শেষ হবে — "
                     f"হাতে আরও প্রায় {ea_bn(days_left - days_needed)} "
                     "দিন বাড়তি থাকবে রিভিশনের জন্য।")
    else:
        required = remaining / days_left
        extra = required - rate
        lines.append(f"রায়: ⚠️ ঘাটতি আছে — এই গতিতে পরীক্ষার আগে শেষ "
                     f"হবে না। শেষ করতে দিনে প্রায় "
                     f"{ea_fmt_num(round(required, 1))} ধাপ লাগবে, মানে "
                     f"এখনকার গতি থেকে দিনে আরও "
                     f"{ea_fmt_num(round(extra, 1))} ধাপ দরকার।")
    return "\n".join(lines)


# =====================================================================
#  ডিসপ্যাচ হেল্পার (ইন্টিগ্রেটর handle_message-এ বসাবে;
#  বিস্তারিত INTEGRATION-ANALYSIS.md-তে)
# =====================================================================

EA_ANALYSIS_TRIGGERS = (
    "ভুলের খরচ", "ভুল খরচ", "খরচ র‍্যাঙ্কিং",
    "অগ্রগতির গ্রাফ", "অগ্রগতি বক্ররেখা", "প্রোগ্রেস কার্ভ",
    "অগ্রগতির কার্ভ",
    "অভিক্ষেপ", "শেষ হতে কত দিন", "পরীক্ষার আগে শেষ হবে",
)


def ea_analysis_handle(text, low=None):
    """Trigger মিললে সংশ্লিষ্ট রিপোর্টের টেক্সট, না মিললে None।
    দ্রষ্টব্য: #765 এখানে campaign=None দিয়ে ডাকা হয় — ক্যাম্পেইন
    (elite-campaign.json, ep_ প্যাক) থাকলে ইন্টিগ্রেটর চাইলে এই
    হ্যান্ডলারটা wrap করে campaign= পাস করতে পারে (INTEGRATION নোট)।"""
    text = str(text or "").strip()
    if not text:
        return None
    if ("ভুলের খরচ" in text or "ভুল খরচ" in text
            or "খরচ র‍্যাঙ্কিং" in text):
        return ea_wrong_cost_text()
    if ("অগ্রগতির গ্রাফ" in text or "অগ্রগতি বক্ররেখা" in text
            or "প্রোগ্রেস কার্ভ" in text or "অগ্রগতির কার্ভ" in text):
        return ea_progress_curve_text()
    if ("অভিক্ষেপ" in text or "শেষ হতে কত দিন" in text
            or "পরীক্ষার আগে শেষ হবে" in text):
        return ea_projection_text(campaign=None)
    return None


# =====================================================================
#  Desktop Sokhi v1.9.0 — ELITE TRAINING PACK (staging, paste into sokhi.py)
#  #755 ফাঁদ-চেনা অনুশীলন (trap-recognition drill)
#  #756 বিকল্প-বাদ দেওয়ার প্রশিক্ষণ (option-elimination drill)
#  #759 চাপ-সিমুলেশন (pressure simulation — host exam, tighter clock)
#
#  Conventions mirror the inlined v1.5 study pack + v1.7 mastery session:
#  - Host globals (OFFLINE_BANK, load_json, save_json, DATA) are resolved
#    at CALL time via globals().get(...), so the pack works pasted into
#    sokhi.py (host wins) and standalone in tests (params / stubs win).
#  - Every data function accepts injectable params (bank=, wrong=,
#    data_dir=) so tests never touch the real data folder.
#  - All top-level symbols are prefixed et_ / ET_.
#  - Honest wording only: the "trap" is computed from real word overlap
#    between options; nothing about a question is invented.
# =====================================================================

import re
import json
import time
import collections
from datetime import date
from pathlib import Path

_ET_BN_DIGITS_MAP = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
ET_OPT_LETTERS = ["ক", "খ", "গ", "ঘ"]

# Session file (import-time snapshot; et_session path is re-resolved at
# call time from the live DATA global — see _et_session_path()).
ET_SESSION_FILE = Path(globals().get("DATA", Path("data"))) / "elite-training-session.json"

_ET_STOP_WORDS = ("থামাও", "বাতিল", "বন্ধ করো")
_ET_TRAP_TRIGGERS = ("ফাঁদ অনুশীলন", "ফাঁদ প্রশিক্ষণ")
_ET_ELIM_TRIGGERS = ("বাদ দেওয়ার অনুশীলন", "এলিমিনেশন অনুশীলন")
_ET_PRESSURE_TRIGGERS = ("চাপ অনুশীলন", "চাপের পরীক্ষা", "প্রেশার টেস্ট")


def _bn(x):
    """Local Bangla-digit helper (mirrors the study pack's _bn())."""
    return str(x).translate(_ET_BN_DIGITS_MAP)


_NO_DATA = "এখনো ডেটা নেই"


# ------------------------------------------------------- host resolution

def _et_data_dir(data_dir=None):
    if data_dir is not None:
        return Path(data_dir)
    g = globals().get("DATA")
    return Path(g) if g is not None else Path("data")


def _et_session_path(data_dir=None):
    return _et_data_dir(data_dir) / "elite-training-session.json"


def _et_load_json(path, default):
    fn = globals().get("load_json")
    if callable(fn):
        try:
            out = fn(path, default)
            return out if out is not None else default
        except Exception:
            return default
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def _et_save_json(path, obj):
    fn = globals().get("save_json")
    if callable(fn):
        try:
            fn(path, obj)
            return
        except Exception:
            pass
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    except Exception:
        pass


def _et_delete_file(path):
    fn = globals().get("_study_delete")
    if callable(fn):
        try:
            fn(path)
            return
        except Exception:
            pass
    try:
        Path(path).unlink(missing_ok=True)
    except Exception:
        pass


def _et_resolve_bank(bank=None):
    if bank is not None:
        return bank if isinstance(bank, dict) else {}
    g = globals().get("OFFLINE_BANK")
    return g if isinstance(g, dict) else {}


def _et_resolve_wrong(wrong=None, data_dir=None):
    if wrong is not None:
        return wrong if isinstance(wrong, list) else []
    wf = globals().get("_WRONG_BOOK_FILE")
    if wf is not None:
        data = _et_load_json(wf, [])
        return data if isinstance(data, list) else []
    data = _et_load_json(_et_data_dir(data_dir) / "study-wrong-book.json", [])
    return data if isinstance(data, list) else []


def et_detect_subject(text, bank=None):
    """ব্যাংকের বিষয় / host SUBJECTS-এর কোনো নাম লেখায় থাকলে সেটা ফেরত
    দেয়; না থাকলে None।"""
    t = str(text or "")
    candidates = []
    b = _et_resolve_bank(bank)
    candidates.extend(b.keys())
    subs = globals().get("SUBJECTS")
    if isinstance(subs, (list, tuple)):
        candidates.extend(subs)
    for name in candidates:
        if name and str(name) in t:
            return str(name)
    return None


# ------------------------------------------------------- session engine

def et_load(data_dir=None):
    st = _et_load_json(_et_session_path(data_dir), None)
    if (isinstance(st, dict) and st.get("mode") in ("trap", "elim")
            and isinstance(st.get("q"), dict)):
        return st
    return None


def et_save(session, data_dir=None):
    _et_save_json(_et_session_path(data_dir), session)


def et_clear(data_dir=None):
    _et_delete_file(_et_session_path(data_dir))


def et_active(data_dir=None):
    return et_load(data_dir) is not None


# ------------------------------------------------------- answer parsing

def et_parse_option(text, q):
    """_parse_answer-এর নিজস্ব ছোট সংস্করণ: ক/খ/গ/ঘ, a-d, ১-৪/1-4,
    বা অপশনের হুবহু লেখা → index; না পারলে None।"""
    t = (text or "").strip()
    if not t:
        return None
    low = t.lower()
    low = re.sub(r"[।.,)ঃ:]+$", "", low).strip()
    if low in ("ক", "a", "1", "১"):
        return 0
    if low in ("খ", "b", "2", "২"):
        return 1
    if low in ("গ", "c", "3", "৩"):
        return 2
    if low in ("ঘ", "d", "4", "৪"):
        return 3
    m = re.match(r"^([কখগঘabcd])\s*[).]", low)
    if m:
        return {"ক": 0, "খ": 1, "গ": 2, "ঘ": 3,
                "a": 0, "b": 1, "c": 2, "d": 3}[m.group(1)]
    m = re.match(r"^([১২৩৪1234])\s*[).]", low.translate(
        str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")))
    if m:
        return int(m.group(1).translate(
            str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789"))) - 1
    for i, op in enumerate((q or {}).get("options", [])[:4]):
        if t == str(op).strip() or low == str(op).strip().lower():
            return i
    return None


# ------------------------------------------------------- question picking

def _et_valid_q(q):
    return (isinstance(q, dict) and q.get("q")
            and isinstance(q.get("options"), list)
            and len(q["options"]) == 4
            and isinstance(q.get("answer"), int)
            and 0 <= q["answer"] <= 3)


def et_pick_question(subject=None, bank=None, wrong=None):
    """(subject, question) বা None ফেরত দেয়।
    পছন্দের ক্রম: ভুলের খাতায় যে টপিক আছে, ব্যাংকের সেই টপিকের প্রশ্ন;
    না থাকলে পুরো পুল। পুলের ভিতরে তারিখ-ঘূর্ণন (host
    _exam_make_questions-এর মতো) যাতে প্রতিদিন একই প্রশ্ন না আসে।"""
    bank = _et_resolve_bank(bank)
    wrong = _et_resolve_wrong(wrong)
    wrong_topics = {str(w.get("topic") or "")
                    for w in wrong if isinstance(w, dict)}
    wrong_topics.discard("")

    if subject:
        subjects = [subject] if subject in bank else []
    else:
        subjects = sorted(bank.keys())
    pool = []        # (subject, q) — wrong-book topic মিলে যাওয়া প্রশ্ন
    full = []        # (subject, q) — সব বৈধ প্রশ্ন
    for subj in subjects:
        for q in bank.get(subj) or []:
            if _et_valid_q(q):
                full.append((subj, dict(q)))
                if str(q.get("topic") or "") in wrong_topics:
                    pool.append((subj, dict(q)))
    chosen = pool or full
    if not chosen:
        return None
    rot = date.today().toordinal() % len(chosen)
    return chosen[rot]


# ------------------------------------------------------- formatting

def _et_fmt_options(q, eliminated=None):
    eliminated = set(eliminated or [])
    lines = []
    for i, op in enumerate(q.get("options", [])[:4]):
        if i in eliminated:
            lines.append(f"{ET_OPT_LETTERS[i]}) {op}  ✂️ (বাদ দেওয়া হয়েছে)")
        else:
            lines.append(f"{ET_OPT_LETTERS[i]}) {op}")
    return "\n".join(lines)


def _et_fmt_question(session, prompt_line):
    q = session["q"]
    head = (f"বিষয়: {session.get('subject', '')} • "
            f"টপিক: {q.get('topic', 'সাধারণ')}")
    return (f"{head}\n{q['q']}\n"
            f"{_et_fmt_options(q, session.get('eliminated'))}\n"
            f"{prompt_line}")


# =====================================================================
#  #755 ফাঁদ-চেনা অনুশীলন
# =====================================================================

def _et_tokens(text):
    return set(re.findall(r"[^\s,।;:!?()\"']+", str(text or "").lower()))


def et_trap_index(q):
    """ফাঁদ = ভুল অপশনগুলোর মধ্যে যেটার লেখা সঠিক অপশনের লেখার সঙ্গে
    সবচেয়ে বেশি শব্দে মেলে (shared tokens / সঠিক লেখার token-সংখ্যা)।
    সম্পূর্ণ deterministic; সমান হলে আগের index জেতে।"""
    opts = (q or {}).get("options", [])
    correct = (q or {}).get("answer")
    if not isinstance(correct, int) or not (0 <= correct < len(opts)):
        return None
    ctoks = _et_tokens(opts[correct])
    if not ctoks:
        return None
    best, best_score = None, -1.0
    for i, op in enumerate(opts[:4]):
        if i == correct:
            continue
        score = len(ctoks & _et_tokens(op)) / len(ctoks)
        if score > best_score:
            best, best_score = i, score
    return best


def et_trap_start(subject=None, bank=None, wrong=None, data_dir=None):
    picked = et_pick_question(subject, bank=bank, wrong=wrong)
    if not picked:
        return (f"{_NO_DATA} — অফলাইন প্রশ্ন-ব্যাংকে ব্যবহারযোগ্য প্রশ্ন "
                "পাইনি, তাই ফাঁদ অনুশীলন শুরু করা গেল না। ব্যাংকে প্রশ্ন "
                "থাকলেই আবার চেষ্টা করো।")
    subj, q = picked
    trap = et_trap_index(q)
    if trap is None:
        return (f"{_NO_DATA} — এই প্রশ্নে ফাঁদ বের করা গেল না। "
                "আরেকবার চেষ্টা করো।")
    session = {"mode": "trap", "subject": subj, "q": q,
               "stage": "trap_pick", "eliminated": [],
               "trap_pick": None, "trap_idx": trap,
               "started_ts": time.time()}
    et_save(session, data_dir)
    return ("🪤 ফাঁদ-চেনা অনুশীলন শুরু! পরীক্ষায় একটা অপশন ইচ্ছে করে "
            "এমনভাবে সাজানো থাকে যাতে তাড়াহুড়োয় সেটাই সঠিক মনে হয় — "
            "সেটাই ফাঁদ।\n\n"
            + _et_fmt_question(
                session,
                "আগে বলো — কোন অপশনটা ফাঁদ? (ক/খ/গ/ঘ বা অপশনের লেখা "
                "লিখলেই হবে)"))


def _et_trap_step(text, session, data_dir=None):
    q = session["q"]
    correct = int(q["answer"])
    if session.get("stage") == "trap_pick":
        pick = et_parse_option(text, q)
        if pick is None:
            return ("বুঝতে পারিনি — ক/খ/গ/ঘ দিয়ে বলো কোন অপশনটা ফাঁদ "
                    "মনে হচ্ছে। থামাতে বলো: 'থামাও'।")
        session["trap_pick"] = pick
        trap = int(session["trap_idx"])
        correct_text = str(q["options"][correct])
        trap_text = str(q["options"][trap])
        if pick == trap:
            fb = (f"✅ ঠিক ধরেছ! {ET_OPT_LETTERS[trap]}) {trap_text} — "
                  "এটাই ছিল ফাঁদ।")
        else:
            fb = (f"তুমি বলেছিলে {ET_OPT_LETTERS[pick]}) "
                  f"{q['options'][pick]} — কিন্তু আসল ফাঁদ ছিল "
                  f"{ET_OPT_LETTERS[trap]}) {trap_text}।")
        fb += (f"\nকেন এটা লোভনীয়: সঠিক উত্তর '{correct_text}'-এর সঙ্গে "
               "এর লেখায় অনেক শব্দ মিলে যায়, তাই তাড়াহুড়োয় পড়লে "
               "চোখে এটাই সঠিক মনে হয়। ধীরে পড়লেই ফাঁদটা ধরা পড়ে।")
        session["stage"] = "answer"
        et_save(session, data_dir)
        return (fb + "\n\nএবার আসল প্রশ্নের উত্তর দাও:\n"
                + _et_fmt_question(
                    session, "উত্তরটা লেখো (ক/খ/গ/ঘ বা অপশনের লেখা)।"))
    # stage == "answer"
    pick = et_parse_option(text, q)
    if pick is None:
        return ("বুঝতে পারিনি — ক/খ/গ/ঘ দিয়ে উত্তর দাও, বা থামাতে "
                "বলো: 'থামাও'।")
    et_clear(data_dir)
    if pick == correct:
        return (f"✅ ঠিক হয়েছে! সঠিক উত্তর: {ET_OPT_LETTERS[correct]}) "
                f"{q['options'][correct]}\n"
                "ফাঁদ চিনে তারপর ঠিক উত্তর — এই দুই ধাপই আসল পরীক্ষায় "
                "কাজে লাগবে। আবার খেলতে বলো: 'ফাঁদ অনুশীলন'।")
    return (f"❌ ভুল হয়েছে। তুমি দিয়েছ: {ET_OPT_LETTERS[pick]}) "
            f"{q['options'][pick]}\n"
            f"সঠিক উত্তর: {ET_OPT_LETTERS[correct]}) "
            f"{q['options'][correct]}\n"
            "কিছু হবে না — ফাঁদ চেনার অনুশীলন মানেই ভুল করে শেখা। "
            "আবার চাইলে বলো: 'ফাঁদ অনুশীলন'।")


# =====================================================================
#  #756 বিকল্প-বাদ দেওয়ার প্রশিক্ষণ
# =====================================================================

def et_elim_start(subject=None, bank=None, wrong=None, data_dir=None):
    picked = et_pick_question(subject, bank=bank, wrong=wrong)
    if not picked:
        return (f"{_NO_DATA} — অফলাইন প্রশ্ন-ব্যাংকে ব্যবহারযোগ্য প্রশ্ন "
                "পাইনি, তাই বাদ দেওয়ার অনুশীলন শুরু করা গেল না।")
    subj, q = picked
    session = {"mode": "elim", "subject": subj, "q": q,
               "stage": "eliminate", "eliminated": [],
               "trap_pick": None, "started_ts": time.time()}
    et_save(session, data_dir)
    return ("✂️ বাদ দেওয়ার অনুশীলন শুরু! যেসব অপশন নিশ্চিতভাবে ভুল, "
            "সেগুলো আগে বাদ দিলে বাকিগুলো থেকে উত্তর বাছা সহজ হয়।\n\n"
            + _et_fmt_question(
                session,
                "একটা করে ভুল অপশন বাদ দাও — লেখো: 'বাদ ক' / 'বাদ খ' "
                "(সর্বোচ্চ ২টা বাদ দিতে পারবে)। তারপর উত্তর দাও "
                "(ক/খ/গ/ঘ বা অপশনের লেখা)।"))


def _et_parse_elim(text, q):
    """'বাদ ক' / 'বাদ দাও ক' / 'বাদ <অপশনের লেখা>' → index বা None।
    বাদ-নির্দেশ না হলে None।"""
    t = (text or "").strip()
    if not t.startswith("বাদ"):
        return None
    rest = t[len("বাদ"):].strip()
    if rest.startswith("দাও"):
        rest = rest[len("দাও"):].strip()
    if not rest:
        return None
    return et_parse_option(rest, q)


def _et_elim_step(text, session, data_dir=None):
    q = session["q"]
    correct = int(q["answer"])
    eliminated = list(session.get("eliminated") or [])

    if (text or "").strip().startswith("বাদ"):
        idx = _et_parse_elim(text, q)
        if idx is None:
            return ("কোনটা বাদ দেবে বুঝতে পারিনি — লেখো: 'বাদ ক' / "
                    "'বাদ খ' এভাবে। থামাতে বলো: 'থামাও'।")
        if idx == correct:
            et_clear(data_dir)
            return (f"😅 সঠিকটাই বাদ দিয়ে ফেললে! সঠিক উত্তর ছিল: "
                    f"{ET_OPT_LETTERS[correct]}) {q['options'][correct]}\n"
                    "শিক্ষা: যে অপশনটা সম্পর্কে সবচেয়ে কম নিশ্চিত, "
                    "সেটা বাদ দেওয়ার আগে আরেকবার ভাবো — শুধু "
                    "নিশ্চিত-ভুল অপশনই বাদ দাও। আবার চাইলে বলো: "
                    "'বাদ দেওয়ার অনুশীলন'।")
        if idx in eliminated:
            return (f"{ET_OPT_LETTERS[idx]}) অপশনটা আগেই বাদ দিয়েছ।\n"
                    + _et_fmt_question(
                        session, "আরেকটা বাদ দাও, বা উত্তর দাও।"))
        eliminated.append(idx)
        session["eliminated"] = eliminated
        et_save(session, data_dir)
        remaining = 4 - len(eliminated)
        if len(eliminated) >= 2:
            tail = ("২টা বাদ হয়ে গেছে — এর বেশি বাদ দেওয়া যাবে না। "
                    "এবার বাকিগুলো থেকে উত্তর দাও।")
        else:
            tail = ("আরেকটা বাদ দিতে পারো, বা এখনই উত্তর দিতে পারো।")
        return (f"✂️ বাদ দিলাম: {ET_OPT_LETTERS[idx]}) "
                f"{q['options'][idx]}। এখন বাকি {_bn(remaining)}টা অপশন।\n"
                + _et_fmt_question(session, tail))

    pick = et_parse_option(text, q)
    if pick is None:
        return ("বুঝতে পারিনি — বাদ দিতে লেখো 'বাদ ক', উত্তর দিতে "
                "লেখো ক/খ/গ/ঘ বা অপশনের লেখা। থামাতে বলো: 'থামাও'।")
    n_elim = len(eliminated)
    remaining = 4 - n_elim
    et_clear(data_dir)
    if pick == correct:
        fb = (f"✅ ঠিক হয়েছে! সঠিক উত্তর: {ET_OPT_LETTERS[correct]}) "
              f"{q['options'][correct]}")
    else:
        fb = (f"❌ ভুল হয়েছে। তুমি দিয়েছ: {ET_OPT_LETTERS[pick]}) "
              f"{q['options'][pick]}\nসঠিক উত্তর: "
              f"{ET_OPT_LETTERS[correct]}) {q['options'][correct]}")
    if n_elim:
        fb += (f"\nলক্ষ্য করো: তুমি {_bn(n_elim)}টা ভুল অপশন বাদ দিয়ে "
               f"৪টা থেকে {_bn(remaining)}টায় নামিয়ে এনেছিলে — তাতে "
               "অনুমান মিলে যাওয়ার সুযোগ অনেক বেড়ে গিয়েছিল। "
               "বাদ-দেওয়ার কৌশলটাই এখানে কাজ করেছে।")
    else:
        fb += ("\nএবার তুমি বাদ না দিয়েই উত্তর দিলে — পরেরবার আগে "
               "নিশ্চিত-ভুল অপশনগুলো বাদ দিয়ে দেখো, সহজ লাগবে।")
    fb += "\nআবার চাইলে বলো: 'বাদ দেওয়ার অনুশীলন'।"
    return fb


# =====================================================================
#  #759 চাপ-সিমুলেশন (সেশন নয় — host exam_start-এর জন্য অনুরোধ)
# =====================================================================

def et_pressure_request(text, low=None):
    """'চাপ অনুশীলন' / 'চাপের পরীক্ষা' / 'প্রেশার টেস্ট' থাকলে
    {"subject", "minutes", "count", "header"} ফেরত দেয়; নইলে None।
    স্তর: 'হালকা' → ৮ মিনিট, ডিফল্ট/'আসল' → ৭ মিনিট, 'কঠিন' → ৫ মিনিট
    (১০টি প্রশ্নের জন্য)। বিষয় লেখায় থাকলে সেটা, নইলে None —
    integrator তখন mock flow-এর মতো default বিষয় বসাবে।"""
    t = str(text or "")
    low = str(low) if low is not None else t.lower()
    if not (any(tr in t for tr in _ET_PRESSURE_TRIGGERS)
            or "pressure test" in low):
        return None
    if "কঠিন" in t:
        minutes, level = 5, "কঠিন"
    elif "হালকা" in t:
        minutes, level = 8, "হালকা"
    else:
        minutes, level = 7, "আসল"
    header = (f"🔥 চাপ-সিমুলেশন শুরু হচ্ছে — স্তর: {level}! "
              f"১০টি প্রশ্নের জন্য সময় মাত্র {_bn(minutes)} মিনিট "
              "(সাধারণ মক টেস্টের চেয়ে কম)। আসল পরীক্ষার হলের চাপ "
              "অনুভব করাই এই অনুশীলনের উদ্দেশ্য: সব প্রশ্নের উত্তর "
              "জানা থাকলেও সময় ব্যবস্থাপনাই এখানে আসল পরীক্ষা। "
              "ঘড়ির দিকে খেয়াল রেখে এগিয়ে যাও!\n")
    return {"subject": et_detect_subject(t), "minutes": minutes,
            "count": 10, "header": header}


# =====================================================================
#  Router — handle_message থেকে ডাকা হয় (INTEGRATION-TRAINING.md দেখো)
# =====================================================================

def et_training_step(text, session=None, data_dir=None):
    """চলমান সেশনে এক ধাপ এগোয়। সেশন না থাকলে None।"""
    session = session if session is not None else et_load(data_dir)
    if not session:
        return None
    if session.get("mode") == "trap":
        return _et_trap_step(text, session, data_dir)
    if session.get("mode") == "elim":
        return _et_elim_step(text, session, data_dir)
    et_clear(data_dir)
    return None


def et_training_handle(text, low=None, bank=None, wrong=None,
                       data_dir=None):
    """সেশন চললে সব লেখা সেখানেই যায় (থামার শব্দ ছাড়া); নইলে
    শুরু-trigger দেখে; কোনোটাই না মিললে None (fall-through)।"""
    t = str(text or "")
    if et_active(data_dir):
        if any(w in t for w in _ET_STOP_WORDS):
            et_clear(data_dir)
            return ("ঠিক আছে, অনুশীলন থামিয়ে দিলাম। আবার শুরু করতে "
                    "বলো: 'ফাঁদ অনুশীলন' বা 'বাদ দেওয়ার অনুশীলন'।")
        out = et_training_step(t, data_dir=data_dir)
        return out if out is not None else (
            "বুঝতে পারিনি — অপশনের অক্ষর (ক/খ/গ/ঘ) দিয়ে উত্তর দাও, "
            "বা থামাতে বলো: 'থামাও'।")
    if any(tr in t for tr in _ET_TRAP_TRIGGERS):
        subj = et_detect_subject(t, bank=bank)
        return et_trap_start(subj, bank=bank, wrong=wrong,
                             data_dir=data_dir)
    if any(tr in t for tr in _ET_ELIM_TRIGGERS):
        subj = et_detect_subject(t, bank=bank)
        return et_elim_start(subj, bank=bank, wrong=wrong,
                              data_dir=data_dir)
    return None


# -*- coding: utf-8 -*-
"""
elite_planning_pack.py — Desktop Sokhi v1.9.0: এলিট পরিকল্পনা প্যাক
(items #766/#662, #767, #769, #770, #781, #782, #783, #784)

এটি একটি STAGING প্যাক — কোনো sokhi.py ফাইলের অংশ নয়। ইন্টিগ্রেটর এটি
sokhi.py-তে পেস্ট করবেন (INTEGRATION-PLANNING.md দেখুন)। সব সিম্বলের
prefix ep_ / EP_ যাতে হোস্টের কোনো নামের সঙ্গে সংঘর্ষ না হয়।

House rules honoured (v1.5 study pack-এর ধাঁচে):
  * 100% free, offline-only — কোনো web / Gemini / API key নয়।
  * NEVER fabricate data — কাট-অফ, তারিখ, সার্কুলারের তথ্য বানানো হয় না।
    সার্কুলার-বিশ্লেষণে শুধু ব্যবহারকারীর পেস্ট করা লেখা থেকেই তথ্য তোলা
    হয়; যা পাওয়া যায়নি তা পরিষ্কার "পাইনি" তালিকায় যায়।
  * Host globals CALL time-এ globals().get(...) দিয়ে resolve হয়
    (OFFLINE_LESSONS, load_json, save_json, DATA, get_memory) — pasted
    অবস্থায় হোস্টের globals জেতে, টেস্টে stub বসানো যায়।
  * সব public ফাংশনে data parameter inject করা যায় (টেস্টের জন্য)।
  * Bangla digits via LOCAL _bn() helper; _NO_DATA = "এখনো ডেটা নেই"।

Verified host data shapes:
  study-progress.json = {subject: {"sessions","mock_tests","total_steps",
                        "weak"[], "last_topic","last_date"}}
  study-wrong-book.json = [{"q","options","correct","your_answer",
                            "subject","topic","date"}]
  OFFLINE_LESSONS = {subject: [{"topic","text",...}]}
  wins.json = [{"id","text","date","ts"}]
  growth-diary.json = [{"date","facts","likes","learned_notes","rules",
                        "knowledge","interactions"}]
  memory first_day: host get_memory()-এর "first_day" key (optional)।

নিজের data files (first use-এ তৈরি হয়):
  elite-campaign.json = {"post": str, "exam_date": "YYYY-MM-DD",
                         "set_date": "YYYY-MM-DD",
                         "events": [{"name","date"}],
                         "milestones_shown": [keys]}
  elite-story.json    = [{"date": "YYYY-MM-DD", "text": str}]
"""

import json
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

# ------------------------------------------------------------------ digits

_EP_BN_MAP = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
_EP_EN_MAP = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")


def _bn(x):
    """Local mirror of host _bn_num(): English digits -> Bangla digits."""
    return str(x).translate(_EP_BN_MAP)


_NO_DATA = "এখনো ডেটা নেই"

EP_WEEKDAYS_BN = ["সোমবার", "মঙ্গলবার", "বুধবার", "বৃহস্পতিবার",
                  "শুক্রবার", "শনিবার", "রবিবার"]

EP_BN_MONTHS = {
    "জানুয়ারি": 1, "জানুয়ারী": 1,
    "ফেব্রুয়ারি": 2, "ফেব্রুয়ারী": 2,
    "মার্চ": 3, "এপ্রিল": 4, "মে": 5, "জুন": 6, "জুলাই": 7,
    "আগস্ট": 8, "আগষ্ট": 8, "সেপ্টেম্বর": 9, "অক্টোবর": 10,
    "নভেম্বর": 11, "ডিসেম্বর": 12,
}

# ------------------------------------------------------------- file paths
# DATA হোস্ট global; standalone/টেস্টে না থাকলে পাশের ফোল্ডারে fallback।

try:
    EP_CAMPAIGN_FILE = DATA / "elite-campaign.json"  # noqa: F821
    EP_STORY_FILE = DATA / "elite-story.json"        # noqa: F821
except NameError:
    EP_CAMPAIGN_FILE = Path("elite-campaign.json")
    EP_STORY_FILE = Path("elite-story.json")


def _ep_data_path(filename, fallback):
    d = globals().get("DATA")
    if d is not None:
        try:
            return Path(d) / filename
        except Exception:
            pass
    return Path(fallback)


def _ep_campaign_path(path=None):
    if path is not None:
        return Path(path)
    return _ep_data_path("elite-campaign.json", EP_CAMPAIGN_FILE)


def _ep_story_path(path=None):
    if path is not None:
        return Path(path)
    return _ep_data_path("elite-story.json", EP_STORY_FILE)


# ------------------------------------------------------- global fallbacks
# হোস্টের load_json/save_json থাকলে তাই, না থাকলে local JSON IO।


def _ep_load(path, default):
    fn = globals().get("load_json")
    if callable(fn):
        try:
            return fn(path, default)
        except Exception:
            return default
    try:
        p = Path(path)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _ep_save(path, obj):
    fn = globals().get("save_json")
    if callable(fn):
        try:
            fn(path, obj)
            return True
        except Exception:
            pass
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj, ensure_ascii=False, indent=1),
                     encoding="utf-8")
        return True
    except Exception:
        return False


def _ep_resolve_lessons(lessons=None):
    if lessons is not None:
        return lessons if isinstance(lessons, dict) else {}
    g = globals().get("OFFLINE_LESSONS")
    return g if isinstance(g, dict) else {}


def _ep_resolve_progress(progress=None):
    if progress is not None:
        return progress if isinstance(progress, dict) else {}
    path = globals().get("_STUDY_PROGRESS_FILE")
    if path is None:
        d = globals().get("DATA")
        path = (Path(d) / "study-progress.json") if d is not None else None
    data = _ep_load(path, {}) if path is not None else {}
    return data if isinstance(data, dict) else {}


def _ep_resolve_wrong(wrong=None):
    if wrong is not None:
        return wrong if isinstance(wrong, list) else []
    path = globals().get("_WRONG_BOOK_FILE")
    if path is None:
        d = globals().get("DATA")
        path = (Path(d) / "study-wrong-book.json") if d is not None else None
    data = _ep_load(path, []) if path is not None else []
    return data if isinstance(data, list) else []


def _ep_resolve_wins(wins=None):
    if wins is not None:
        return wins if isinstance(wins, list) else []
    d = globals().get("DATA")
    if d is None:
        return []
    data = _ep_load(Path(d) / "wins.json", [])
    return data if isinstance(data, list) else []


def _ep_resolve_diary(diary=None):
    if diary is not None:
        return diary if isinstance(diary, list) else []
    d = globals().get("DATA")
    if d is None:
        return []
    data = _ep_load(Path(d) / "growth-diary.json", [])
    return data if isinstance(data, list) else []


def _ep_resolve_first_day(first_day=None):
    if first_day:
        return str(first_day)
    fn = globals().get("get_memory")
    if callable(fn):
        try:
            mem = fn()
            if isinstance(mem, dict) and mem.get("first_day"):
                return str(mem["first_day"])
        except Exception:
            pass
    return ""


def _ep_today(today=None):
    if isinstance(today, date):
        return today
    return date.today()


# ------------------------------------------------------------ date utils

def ep_normalize_digits(text):
    """বাংলা সংখ্যা (০-৯) -> English digits; বাকি লেখা অপরিবর্তিত।"""
    return str(text or "").translate(_EP_EN_MAP)


def ep_parse_date(text):
    """লেখা থেকে প্রথম বৈধ তারিখ -> datetime.date, না পেলে None।
    ফরম্যাট: YYYY-MM-DD, DD/MM/YYYY, আর '১২ মার্চ ২০২৭' ধরনের বাংলা
    মাসের নাম (সংখ্যা বাংলা বা English যেকোনোটি)।"""
    t = ep_normalize_digits(text)
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", t)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", t)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    month_alt = "|".join(sorted(EP_BN_MONTHS, key=len, reverse=True))
    m = re.search(r"(\d{1,2})\s*(" + month_alt + r")\s*,?\s*(\d{4})",
                  str(text or ""))
    if not m:
        m = re.search(r"(\d{1,2})\s*(" + month_alt + r")\s*,?\s*(\d{4})", t)
    if m:
        try:
            return date(int(m.group(3)), EP_BN_MONTHS[m.group(2)],
                        int(m.group(1)))
        except (ValueError, KeyError):
            pass
    return None


def ep_find_dates(text):
    """লেখায় পাওয়া সব বৈধ তারিখ (ক্রম ঠিক রেখে, duplicate ছাড়া)।"""
    t = ep_normalize_digits(text)
    found = []

    def _add(d):
        if d is not None and d not in found:
            found.append(d)

    hits = []
    for m in re.finditer(r"\d{4}-\d{1,2}-\d{1,2}", t):
        hits.append((m.start(), ep_parse_date(m.group(0))))
    for m in re.finditer(r"\d{1,2}/\d{1,2}/\d{4}", t):
        hits.append((m.start(), ep_parse_date(m.group(0))))
    month_alt = "|".join(sorted(EP_BN_MONTHS, key=len, reverse=True))
    pat = r"\d{1,2}\s*(?:" + month_alt + r")\s*,?\s*\d{4}"
    raw = str(text or "")
    for src in (raw, t):
        for m in re.finditer(pat, src):
            hits.append((m.start(), ep_parse_date(m.group(0))))
    for _, d in sorted(hits, key=lambda h: h[0]):
        _add(d)
    return found


def _ep_fmt_date(d):
    """date -> '১২ মার্চ ২০২৭ (2027-03-12)' ধরনের পাঠযোগ্য রূপ।"""
    if not isinstance(d, date):
        return str(d or "")
    # প্রচলিত বানান: map-এ মাসের প্রথম key
    names = [k for k, v in EP_BN_MONTHS.items() if v == d.month]
    name = names[0] if names else str(d.month)
    return f"{_bn(d.day)} {name} {_bn(d.year)}"


def _ep_parse_iso(s):
    if not s:
        return None
    try:
        return date.fromisoformat(str(s)[:10])
    except ValueError:
        return ep_parse_date(s)


# ------------------------------------------------------- shared analysis

def _ep_touched_topics(progress, lessons):
    """(subject, topic) সেট — যেসব lesson-topic-এর প্রমাণ progress-এ আছে:
    last_topic এবং weak[]-এর যেসব topic lesson তালিকায় আছে।
    (v1.5 coverage_text-এর একই সীমিত-প্রমাণ নিয়ম।)"""
    touched = set()
    for subj, items in (lessons or {}).items():
        topics = {str(it.get("topic")) for it in (items or [])
                  if isinstance(it, dict) and it.get("topic")}
        info = (progress or {}).get(subj) or {}
        if not isinstance(info, dict):
            continue
        lt = info.get("last_topic")
        if lt and str(lt) in topics:
            touched.add((subj, str(lt)))
        for w in info.get("weak") or []:
            if str(w) in topics:
                touched.add((subj, str(w)))
    return touched


def _ep_coverage(progress, lessons):
    """(ছোঁয়া topic সংখ্যা, মোট topic সংখ্যা) — সব বিষয় মিলিয়ে।"""
    total = sum(len(items or []) for items in (lessons or {}).values())
    return len(_ep_touched_topics(progress, lessons)), total


def _ep_weak_topics(progress, wrong, limit=5):
    """দুর্বল topic তালিকা: progress-এর weak[] আগে, তারপর wrong-book-এ
    সবচেয়ে বেশিবার ভুল হওয়া topic।"""
    out = []
    for subj in sorted((progress or {}).keys()):
        info = progress.get(subj) or {}
        if isinstance(info, dict):
            for w in info.get("weak") or []:
                if str(w) not in out:
                    out.append(str(w))
    wc = Counter(str(w.get("topic") or "সাধারণ") for w in (wrong or [])
                 if isinstance(w, dict))
    for topic, _cnt in wc.most_common():
        if topic not in out:
            out.append(topic)
    return out[:limit]


def _ep_gap_topics(progress, lessons, limit=5):
    """এখনো ছোঁয়া হয়নি এমন lesson topic (বিষয়সহ)।"""
    touched = _ep_touched_topics(progress, lessons)
    out = []
    for subj in sorted((lessons or {}).keys()):
        for it in lessons.get(subj) or []:
            if isinstance(it, dict) and it.get("topic"):
                key = (subj, str(it["topic"]))
                if key not in touched:
                    out.append(f"{subj}: {it['topic']}")
    return out[:limit]


# =====================================================================
#  #767 মাইলফলক (আগে — ক্যাম্পেইন এটা ব্যবহার করে)
# =====================================================================

EP_MILESTONE_DEFS = [
    # (key, label, kind, threshold)
    ("cov25", "সিলেবাস কভারেজ ২৫%", "coverage", 25),
    ("cov50", "সিলেবাস কভারেজ ৫০%", "coverage", 50),
    ("cov75", "সিলেবাস কভারেজ ৭৫%", "coverage", 75),
    ("cov100", "সিলেবাস কভারেজ ১০০%", "coverage", 100),
    ("mock1", "প্রথম মক টেস্ট দেওয়া", "mock", 1),
    ("mock5", "মোট ৫টি মক টেস্ট", "mock", 5),
    ("mock10", "মোট ১০টি মক টেস্ট", "mock", 10),
    ("mock20", "মোট ২০টি মক টেস্ট", "mock", 20),
    ("wrong50", "ভুলের খাতা ৫০-এর নিচে", "wrong_below", 50),
    ("wrong20", "ভুলের খাতা ২০-এর নিচে", "wrong_below", 20),
    ("wrong10", "ভুলের খাতা ১০-এর নিচে", "wrong_below", 10),
    ("wrong5", "ভুলের খাতা ৫-এর নিচে", "wrong_below", 5),
]


def ep_milestones(progress=None, lessons=None, wrong=None):
    """ডেটা থেকে হিসাব করা মাইলফলক: [{"key","label","achieved"}]।
    কভারেজ = ছোঁয়া topic / মোট lesson topic; মক = সব বিষয়ের mock_tests
    যোগফল; ভুলের খাতা ছোট হওয়া মাপা হয় তখনই, যখন অন্তত একটি মক টেস্ট
    দেওয়া হয়েছে (নইলে খালি খাতা 'অর্জন' নয়)।"""
    progress = _ep_resolve_progress(progress)
    lessons = _ep_resolve_lessons(lessons)
    wrong = _ep_resolve_wrong(wrong)
    touched, total_topics = _ep_coverage(progress, lessons)
    cov_pct = (touched * 100 // total_topics) if total_topics else 0
    mocks = 0
    for info in progress.values():
        if isinstance(info, dict):
            try:
                mocks += int(info.get("mock_tests") or 0)
            except (TypeError, ValueError):
                pass
    n_wrong = len(wrong)
    out = []
    for key, label, kind, thr in EP_MILESTONE_DEFS:
        if kind == "coverage":
            ok = total_topics > 0 and cov_pct >= thr
        elif kind == "mock":
            ok = mocks >= thr
        else:  # wrong_below
            ok = mocks > 0 and n_wrong < thr
        out.append({"key": key, "label": label, "achieved": bool(ok)})
    return out


def ep_milestones_text(progress=None, lessons=None, wrong=None):
    ms = ep_milestones(progress, lessons, wrong)
    lines = ["🏁 মাইলফলক (তোমার নিজের ডেটা থেকে হিসাব করা):"]
    for mst in ms:
        mark = "✓" if mst["achieved"] else "•"
        lines.append(f"{mark} {mst['label']}")
    return "\n".join(lines)


def ep_milestone_new(campaign, progress=None, lessons=None, wrong=None):
    """নতুন অর্জিত milestone key-গুলো — যেগুলো campaign['milestones_shown']-
    এ এখনো নেই। ইন্টিগ্রেটর চাইলে এগুলো campaign-এ persist করবেন।"""
    shown = set()
    if isinstance(campaign, dict):
        shown = {str(k) for k in (campaign.get("milestones_shown") or [])}
    return [m["key"] for m in ep_milestones(progress, lessons, wrong)
            if m["achieved"] and m["key"] not in shown]


# =====================================================================
#  #766/#662 ক্যাম্পেইন পরিকল্পক
# =====================================================================

def ep_campaign_default():
    return {"post": "", "exam_date": "", "set_date": "",
            "events": [], "milestones_shown": []}


def ep_campaign_load(path=None):
    data = _ep_load(_ep_campaign_path(path), {})
    camp = ep_campaign_default()
    if isinstance(data, dict):
        for k in camp:
            if k in data:
                camp[k] = data[k]
    if not isinstance(camp.get("events"), list):
        camp["events"] = []
    if not isinstance(camp.get("milestones_shown"), list):
        camp["milestones_shown"] = []
    return camp


def ep_campaign_save(campaign, path=None):
    return _ep_save(_ep_campaign_path(path), campaign)


def ep_campaign_exam_date(campaign):
    if isinstance(campaign, dict):
        return _ep_parse_iso(campaign.get("exam_date"))
    return None


def ep_campaign_phase(days_left):
    """>45 ভিত্তি গড়া / 22–45 মজবুত করা / 8–21 রিভিশন / ≤7 শেষ সপ্তাহ।"""
    if days_left is None:
        return ""
    if days_left > 45:
        return "ভিত্তি গড়া"
    if days_left >= 22:
        return "মজবুত করা"
    if days_left >= 8:
        return "রিভিশন"
    return "শেষ সপ্তাহ"


def ep_campaign_set_from_text(text, today=None, campaign=None, path=None):
    """সেট-কমান্ড parse করে campaign আপডেট + save করে।
    মিললে confirmation text, না মিললে None।
    প্যাটার্ন: 'ক্যাম্পেইন: <post> পরীক্ষা <date>' অথবা
    'পরীক্ষার তারিখ <date>'। তারিখ YYYY-MM-DD / DD/MM/YYYY / বাংলা
    সংখ্যা / বাংলা মাসের নাম — যেকোনোটি।"""
    raw = str(text or "").strip()
    if not raw:
        return None
    today = _ep_today(today)
    post = None
    exam = None
    m = re.match(r"\s*ক্যাম্পেইন\s*[:：]\s*(.+)$", raw)
    if m:
        rest = m.group(1).strip()
        exam = ep_parse_date(rest)
        pm = re.split(r"পরীক্ষা", rest, maxsplit=1)
        if len(pm) == 2:
            post = pm[0].strip(" :：-—") or None
    elif "পরীক্ষার তারিখ" in raw:
        exam = ep_parse_date(raw)
    else:
        return None
    if exam is None:
        return ("তারিখটা বুঝতে পারিনি। এভাবে লিখো — যেমন: "
                "'ক্যাম্পেইন: ইউনিয়ন সমাজকর্মী পরীক্ষা 2027-03-12' "
                "অথবা 'পরীক্ষার তারিখ 12/03/2027'।")
    camp = campaign if isinstance(campaign, dict) else ep_campaign_load(path)
    if post:
        camp["post"] = post
    camp["exam_date"] = exam.isoformat()
    camp["set_date"] = today.isoformat()
    if not isinstance(camp.get("events"), list):
        camp["events"] = []
    if not isinstance(camp.get("milestones_shown"), list):
        camp["milestones_shown"] = []
    ep_campaign_save(camp, path)
    days = (exam - today).days
    head = f"🎯 ক্যাম্পেইন সেট হয়েছে!"
    if camp.get("post"):
        head += f"\nপদ: {camp['post']}"
    head += f"\nপরীক্ষার তারিখ: {_ep_fmt_date(exam)}"
    if days >= 0:
        head += f"\nবাকি: {_bn(days)} দিন — বর্তমান ধাপ: {ep_campaign_phase(days)}"
    else:
        head += "\n(এই তারিখটা আজ থেকে পেছনে — ঠিক আছে কিনা দেখে নিও।)"
    return head


def ep_campaign_text(progress=None, lessons=None, wrong=None, today=None,
                     campaign=None):
    """ক্যাম্পেইনের বর্তমান অবস্থা: দিন বাকি, ধাপ, ডেটাভিত্তিক ফোকাস,
    আর মাইলফলক তালিকা। campaign না থাকলে সেট করার নির্দেশনা।"""
    today = _ep_today(today)
    camp = campaign if isinstance(campaign, dict) else ep_campaign_load()
    exam = ep_campaign_exam_date(camp)
    if exam is None:
        return ("🎯 এখনো কোনো ক্যাম্পেইন সেট করোনি — পরীক্ষার তারিখ জানলে "
                "এভাবে বলো: 'ক্যাম্পেইন: <পদের নাম> পরীক্ষা <তারিখ>' "
                "(যেমন: ক্যাম্পেইন: ইউনিয়ন সমাজকর্মী পরীক্ষা 2027-03-12)। "
                "তারিখ পেলেই দিন গুনে ধাপে ধাপে পরিকল্পনা সাজিয়ে দেব।")
    progress = _ep_resolve_progress(progress)
    lessons = _ep_resolve_lessons(lessons)
    wrong = _ep_resolve_wrong(wrong)
    days = (exam - today).days
    phase = ep_campaign_phase(days)
    lines = ["🎯 ক্যাম্পেইন পরিকল্পনা"]
    if camp.get("post"):
        lines.append(f"পদ: {camp['post']}")
    lines.append(f"পরীক্ষা: {_ep_fmt_date(exam)}")
    if days > 0:
        lines.append(f"বাকি আছে: {_bn(days)} দিন")
    elif days == 0:
        lines.append("আজই পরীক্ষা! শুভকামনা রইল।")
    else:
        lines.append(f"পরীক্ষার তারিখ {_bn(-days)} দিন আগে পেরিয়ে গেছে — "
                     "নতুন তারিখ থাকলে ক্যাম্পেইন আবার সেট করো।")
    if days >= 0:
        lines.append(f"বর্তমান ধাপ: {phase}")
        weak = _ep_weak_topics(progress, wrong)
        gaps = _ep_gap_topics(progress, lessons)
        lines.append("")
        lines.append(f"এই ধাপে ফোকাস ({phase}):")
        if phase == "ভিত্তি গড়া":
            if gaps:
                lines.append("• আগে বাকি পাঠগুলো শেষ করো: " +
                             "; ".join(gaps[:3]))
            else:
                lines.append("• সব পাঠ একবার করে ছোঁয়া হয়েছে — "
                             "এবার ধারাবাহিকভাবে এগিয়ে যাও।")
            lines.append("• প্রতিদিন অল্প অল্প করে নতুন টপিক পড়ো।")
        elif phase == "মজবুত করা":
            if weak:
                lines.append("• দুর্বল টপিক মজবুত করো: " + ", ".join(weak))
            if gaps:
                lines.append("• বাকি পাঠ শেষ করো: " + "; ".join(gaps[:2]))
            lines.append("• নিয়মিত মক টেস্ট দিয়ে দুর্বলতা যাচাই করো।")
        elif phase == "রিভিশন":
            if weak:
                lines.append("• ভুলের খাতা রিভিশন করো: " + ", ".join(weak))
            lines.append("• নতুন পড়া কমিয়ে রিভিশন আর মক টেস্টে জোর দাও।")
        else:  # শেষ সপ্তাহ
            lines.append("• 'পরীক্ষা সপ্তাহ' লিখলেই দিনভিত্তিক প্রোটোকল "
                         "সাজিয়ে দেব।")
            if weak:
                lines.append("• শেষবারের মতো চোখ বুলাও: " + ", ".join(weak))
        if not weak and not gaps and phase != "শেষ সপ্তাহ":
            lines.append(f"• ({_NO_DATA} — পড়ার রেকর্ড এলেই ফোকাস আরও "
                         "নির্দিষ্ট করে বলতে পারব।)")
    new_keys = ep_milestone_new(camp, progress, lessons, wrong)
    if new_keys:
        labels = {m["key"]: m["label"]
                  for m in ep_milestones(progress, lessons, wrong)}
        lines.append("")
        lines.append("🎉 নতুন মাইলফলক অর্জন: " +
                     ", ".join(labels.get(k, k) for k in new_keys))
    lines.append("")
    lines.append(ep_milestones_text(progress, lessons, wrong))
    return "\n".join(lines)


# =====================================================================
#  #769 সম্পদ-বণ্টন (সাপ্তাহিক সময়-ভাগ)
# =====================================================================

def ep_allocation(progress=None, wrong=None, lessons=None):
    """বিষয়ভিত্তিক সাপ্তাহিক সময়-ভাগ %: [{"subject","pct","remaining"}]।
    ভিত্তি = বাকি পাঠের অংশ; boost = ভুলের খাতায় ঐ বিষয়ের ভুলের অংশ।
    শতকরার যোগফল ঠিক ১০০ (rounding-এর ঘাটতি সবচেয়ে বড় ভাগে যোগ হয়)।"""
    progress = _ep_resolve_progress(progress)
    wrong = _ep_resolve_wrong(wrong)
    lessons = _ep_resolve_lessons(lessons)
    subjects = sorted(set(lessons.keys()) | set(progress.keys()))
    if not subjects:
        return []
    touched = _ep_touched_topics(progress, lessons)
    wrong_by_subj = Counter(str(w.get("subject") or "অজানা বিষয়")
                            for w in wrong if isinstance(w, dict))
    total_wrong = sum(wrong_by_subj.values())
    remaining = {}
    for subj in subjects:
        total = len(lessons.get(subj) or [])
        done = sum(1 for (s, _t) in touched if s == subj)
        remaining[subj] = max(0, total - done)
    total_remaining = sum(remaining.values())
    weights = {}
    for subj in subjects:
        base = (remaining[subj] / total_remaining) if total_remaining else 0.0
        boost = (wrong_by_subj.get(subj, 0) / total_wrong) \
            if total_wrong else 0.0
        weights[subj] = base + boost
    total_w = sum(weights.values())
    if total_w <= 0:
        weights = {s: 1.0 for s in subjects}
        total_w = float(len(subjects))
    raw = {s: weights[s] / total_w * 100.0 for s in subjects}
    pct = {s: int(round(v)) for s, v in raw.items()}
    diff = 100 - sum(pct.values())
    if diff != 0:
        largest = max(subjects, key=lambda s: raw[s])
        pct[largest] += diff
    return [{"subject": s, "pct": pct[s], "remaining": remaining[s]}
            for s in sorted(subjects, key=lambda s: -pct[s])]


def ep_allocation_text(progress=None, wrong=None, lessons=None):
    alloc = ep_allocation(progress, wrong, lessons)
    if not alloc:
        return (f"{_NO_DATA} — কোনো বিষয়ের পাঠ বা পড়ার রেকর্ড পাইনি, "
                "তাই সময়-ভাগ সাজাতে পারছি না।")
    lines = ["🧭 সাপ্তাহিক সম্পদ-বণ্টন (সময়-ভাগ)",
             "(তোমার নিজের তথ্য থেকে সাজানো ভাগ — বাকি পাঠ আর ভুলের "
             "খাতার ওজন অনুযায়ী।)"]
    for a in alloc:
        lines.append(f"• {a['subject']}: {_bn(a['pct'])}% — "
                     f"বই/পাঠ বাকি: {_bn(a['remaining'])}টি")
    lines.append("মোট: ১০০% — সপ্তাহের মোট পড়ার সময়কে এভাবে ভাগ করলেই "
                 "হিসাবটা মিলবে।")
    return "\n".join(lines)


# =====================================================================
#  #770 পরীক্ষা-সপ্তাহ প্রোটোকল
# =====================================================================

EP_EXAM_DAY_CHECKLIST = [
    "প্রবেশপত্র (অ্যাডমিট কার্ড) আর দরকারি কাগজপত্র আগের রাতেই ব্যাগে রাখো",
    "কলম, পেন্সিল, ঘড়ি — যা যা লাগে গুছিয়ে রাখো",
    "পরীক্ষার কেন্দ্রে পৌঁছানোর পথ ও সময় আগেই হিসাব করে রাখো — হাতে বাড়তি সময় নিয়ে বের হও",
    "আগের রাতে তাড়াতাড়ি ঘুমাও; পরীক্ষার দিন হালকা খাবার খেয়ে বের হও",
    "মোবাইল ফোন কেন্দ্রের নিয়ম অনুযায়ী রাখো",
]


def ep_exam_week_text(campaign=None, wrong=None, progress=None, today=None,
                      force=False):
    """পরীক্ষা ৭ দিনের মধ্যে হলে (বা force=True হলে) দিনভিত্তিক পরিকল্পনা:
    প্রথম দিনগুলোতে ভুলের খাতার শীর্ষ টপিক রিভিশন, আগের দিন হালকা রিভিশন
    + বিশ্রাম, পরীক্ষার দিনের সাধারণ চেকলিস্ট। তারিখ না থাকলে সেট করতে বলে।"""
    today = _ep_today(today)
    camp = campaign if isinstance(campaign, dict) else ep_campaign_load()
    exam = ep_campaign_exam_date(camp)
    if exam is None:
        return ("📅 পরীক্ষা-সপ্তাহ প্রোটোকল সাজাতে আগে পরীক্ষার তারিখ লাগবে। "
                "এভাবে সেট করো: 'ক্যাম্পেইন: <পদের নাম> পরীক্ষা <তারিখ>' "
                "অথবা 'পরীক্ষার তারিখ 12/03/2027'।")
    days = (exam - today).days
    if days < 0:
        return ("📅 ক্যাম্পেইনের পরীক্ষার তারিখ পেরিয়ে গেছে "
                f"({_ep_fmt_date(exam)})। নতুন তারিখ থাকলে ক্যাম্পেইন "
                "আবার সেট করো।")
    if days > 7 and not force:
        return (f"📅 পরীক্ষা এখনো {_bn(days)} দিন বাকি — পরীক্ষা-সপ্তাহ "
                "প্রোটোকল শুরু হবে শেষ ৭ দিনে। এখনকার ধাপ: "
                f"{ep_campaign_phase(days)}। 'ক্যাম্পেইন' লিখলে পুরো "
                "পরিকল্পনা দেখতে পাবে।")
    wrong = _ep_resolve_wrong(wrong)
    progress = _ep_resolve_progress(progress)
    topics = _ep_weak_topics(progress, wrong, limit=10)
    lines = ["📅 পরীক্ষা-সপ্তাহ প্রোটোকল",
             f"পরীক্ষা: {_ep_fmt_date(exam)} — বাকি {_bn(days)} দিন"]
    if camp.get("post"):
        lines.append(f"পদ: {camp['post']}")
    topic_i = 0
    for i in range(days):
        d = today + timedelta(days=i)
        label = f"• {_ep_fmt_date(d)} ({EP_WEEKDAYS_BN[d.weekday()]}): "
        if d == exam - timedelta(days=1) and days >= 1:
            lines.append(label + "হালকা রিভিশন — শুধু নোট আর ভুলের খাতায় "
                                 "চোখ বুলাও; তাড়াতাড়ি ঘুমাও, বিশ্রাম নাও।")
        elif topics:
            take = topics[topic_i:topic_i + 2]
            topic_i += len(take)
            if take:
                lines.append(label + "রিভিশন: " + ", ".join(take))
            else:
                lines.append(label + "সার্বিক রিভিশন — ভুলের খাতা আর "
                                     "নিজের নোট আবার দেখো।")
        else:
            lines.append(label + "সার্বিক রিভিশন — নিজের নোট আর পড়া "
                                 "অংশগুলো আবার দেখো।")
    lines.append(f"• {_ep_fmt_date(exam)} ({EP_WEEKDAYS_BN[exam.weekday()]}): "
                 "পরীক্ষার দিন 🎯")
    lines.append("")
    lines.append("পরীক্ষার দিনের চেকলিস্ট (সাধারণ):")
    for item in EP_EXAM_DAY_CHECKLIST:
        lines.append(f"• {item}")
    return "\n".join(lines)


# =====================================================================
#  #783 তারিখ-সংঘাত সতর্কতা + ইভেন্ট যোগ/তালিকা
# =====================================================================

def ep_conflicts(campaign):
    """campaign-এর dated items (পরীক্ষা + events) থেকে সংঘাতের তালিকা:
    একই তারিখে একাধিক item, আর পরীক্ষার আগের ২ দিনের মধ্যে event।"""
    camp = campaign if isinstance(campaign, dict) else ep_campaign_load()
    exam = ep_campaign_exam_date(camp)
    items = []
    if exam is not None:
        items.append(("পরীক্ষা" + (f" ({camp['post']})"
                                   if camp.get("post") else ""), exam))
    for ev in camp.get("events") or []:
        if isinstance(ev, dict):
            d = _ep_parse_iso(ev.get("date")) or ep_parse_date(ev.get("date"))
            if d is not None:
                items.append((str(ev.get("name") or "ইভেন্ট"), d))
    warnings = []
    by_date = {}
    for name, d in items:
        by_date.setdefault(d, []).append(name)
    for d in sorted(by_date):
        if len(by_date[d]) > 1:
            warnings.append(f"⚠️ {_ep_fmt_date(d)} — একই দিনে একাধিক: " +
                            ", ".join(by_date[d]))
    if exam is not None:
        for ev in camp.get("events") or []:
            if not isinstance(ev, dict):
                continue
            d = _ep_parse_iso(ev.get("date")) or ep_parse_date(ev.get("date"))
            if d is None:
                continue
            gap = (exam - d).days
            if 0 < gap <= 2:
                warnings.append(
                    f"⚠️ '{ev.get('name')}' পরীক্ষার ঠিক আগে "
                    f"({_ep_fmt_date(d)} — পরীক্ষার {_bn(gap)} দিন আগে)। "
                    "ঐ সময়টা রিভিশনে রাখা ভালো।")
    return warnings


def ep_conflicts_text(campaign=None):
    camp = campaign if isinstance(campaign, dict) else ep_campaign_load()
    exam = ep_campaign_exam_date(camp)
    events = [ev for ev in (camp.get("events") or [])
              if isinstance(ev, dict)]
    if exam is None and not events:
        return (f"{_NO_DATA} — ক্যাম্পেইনে কোনো তারিখ বা ইভেন্ট নেই। "
                "পরীক্ষার তারিখ সেট করো ('ক্যাম্পেইন: ... পরীক্ষা "
                "<তারিখ>'), আর ইভেন্ট যোগ করো: 'ইভেন্ট যোগ: <নাম> <তারিখ>'।")
    lines = ["🗓️ তারিখের তালিকা:"]
    if exam is not None:
        lines.append(f"• পরীক্ষা: {_ep_fmt_date(exam)}")
    for ev in events:
        d = _ep_parse_iso(ev.get("date")) or ep_parse_date(ev.get("date"))
        lines.append(f"• {ev.get('name')}: "
                     f"{_ep_fmt_date(d) if d else ev.get('date')}")
    warns = ep_conflicts(camp)
    lines.append("")
    if warns:
        lines.append("তারিখ-সংঘাত সতর্কতা:")
        lines.extend(warns)
    else:
        lines.append("✓ কোনো তারিখ-সংঘাত পাইনি।")
    return "\n".join(lines)


def ep_event_add_from_text(text, campaign=None, path=None, today=None):
    """'ইভেন্ট যোগ: <নাম> <তারিখ>' — campaign['events']-এ যোগ করে save।
    মিললে confirmation, তারিখ না মিললে নির্দেশনা, প্যাটার্ন না মিললে None।"""
    raw = str(text or "").strip()
    m = re.match(r"\s*ইভেন্ট যোগ\s*[:：]?\s*(.+)$", raw)
    if not m:
        return None
    rest = m.group(1).strip()
    d = ep_parse_date(rest)
    if d is None:
        return ("ইভেন্টের তারিখটা বুঝতে পারিনি। এভাবে লিখো: "
                "'ইভেন্ট যোগ: মেডিকেল চেকআপ 10/03/2027'")
    name = rest
    for pat in (r"\d{4}-\d{1,2}-\d{1,2}", r"\d{1,2}/\d{1,2}/\d{4}"):
        name = re.sub(pat, "", ep_normalize_digits(name))
    month_alt = "|".join(sorted(EP_BN_MONTHS, key=len, reverse=True))
    name = re.sub(r"\d{1,2}\s*(?:" + month_alt + r")\s*,?\s*\d{4}", "", name)
    name = name.strip(" :：-—") or "ইভেন্ট"
    camp = campaign if isinstance(campaign, dict) else ep_campaign_load(path)
    if not isinstance(camp.get("events"), list):
        camp["events"] = []
    camp["events"].append({"name": name, "date": d.isoformat()})
    ep_campaign_save(camp, path)
    out = f"🗓️ ইভেন্ট যোগ হয়েছে: {name} — {_ep_fmt_date(d)}"
    warns = ep_conflicts(camp)
    if warns:
        out += "\n" + "\n".join(warns)
    return out


def ep_event_list_text(campaign=None):
    return ep_conflicts_text(campaign)


# =====================================================================
#  #781 নিজের গল্পের ফ্রেম
# =====================================================================

EP_STORY_FRAME = [
    ("শিরোনাম", "তোমার যাত্রার একটা ছোট শিরোনাম দাও — যেমন: "
                 "'একটা চাকরির অপেক্ষায়'।"),
    ("১. শুরু", "কোথা থেকে শুরু করেছিলে? তখন তোমার অবস্থা, স্বপ্ন আর "
                "ভয়গুলো কেমন ছিল?"),
    ("২. কঠিন সময়", "সবচেয়ে কঠিন সময় কোনটা গেছে? কী তোমাকে থামিয়ে "
                      "দিতে চেয়েছিল?"),
    ("৩. ঘুরে দাঁড়ানো", "কীভাবে আবার উঠে দাঁড়ালে? কার বা কিসের সাহায্য "
                          "পেয়েছিলে?"),
    ("৪. এখন", "এখন তুমি কোথায় আছ? পড়ায় কতদূর এগিয়েছ, কী শিখেছ?"),
    ("৫. লক্ষ্য", "সামনের লক্ষ্য কী? পৌঁছালে নিজেকে কী বলবে?"),
]


def ep_story_load(path=None):
    data = _ep_load(_ep_story_path(path), [])
    return data if isinstance(data, list) else []


def ep_story_save(body, path=None, today=None):
    """গল্পের draft elite-story.json-এ append করে। সফল হলে True।"""
    body = str(body or "").strip()
    if not body:
        return False
    items = ep_story_load(path)
    items.append({"date": _ep_today(today).isoformat(), "text": body})
    return _ep_save(_ep_story_path(path), items[-200:])


def ep_story_text(diary=None, wins=None, progress=None, first_day=None):
    """যাত্রার তথ্য শুধু ডেটা থেকে (শুরুর তারিখ, সেশন/ধাপ, জয়, diary
    দিন) + লেখার ফ্রেম (শিরোনাম + ৫টি অংশের prompt)।"""
    diary = _ep_resolve_diary(diary)
    wins = _ep_resolve_wins(wins)
    progress = _ep_resolve_progress(progress)
    first_day = _ep_resolve_first_day(first_day)
    sessions = 0
    steps = 0
    for info in progress.values():
        if isinstance(info, dict):
            try:
                sessions += int(info.get("sessions") or 0)
                steps += int(info.get("total_steps") or 0)
            except (TypeError, ValueError):
                pass
    lines = ["📖 নিজের গল্পের ফ্রেম"]
    facts = []
    if first_day:
        fd = _ep_parse_iso(first_day)
        facts.append(f"শুরুর তারিখ: "
                     f"{_ep_fmt_date(fd) if fd else first_day}")
    if sessions or steps:
        facts.append(f"মোট পড়ার সেশন: {_bn(sessions)}টি, "
                     f"মোট ধাপ: {_bn(steps)}টি")
    if wins:
        facts.append(f"জয়ের সংখ্যা: {_bn(len(wins))}টি")
    if diary:
        facts.append(f"ডায়েরি লিখেছ: {_bn(len(diary))} দিন")
    if facts:
        lines.append("")
        lines.append("তোমার যাত্রার তথ্য (ডেটা থেকে):")
        for f in facts:
            lines.append(f"• {f}")
        recent = [w for w in wins if isinstance(w, dict)
                  and w.get("text")][-3:]
        if recent:
            lines.append("সর্বশেষ জয়গুলো:")
            for w in recent:
                lines.append(f"• {w['text']}")
    else:
        lines.append(f"({_NO_DATA} — পড়া/জয়ের রেকর্ড এলেই এখানে তোমার "
                     "যাত্রার তথ্য জমবে।)")
    lines.append("")
    lines.append("✍️ লেখার ফ্রেম — এই ৫টি অংশে নিজের গল্পটা সাজাও:")
    for title, prompt in EP_STORY_FRAME:
        lines.append(f"{title}: {prompt}")
    lines.append("")
    lines.append("লিখে ফেললে এভাবে পাঠাও: 'গল্প লিখলাম: <তোমার লেখা>' — "
                 "আমি সংরক্ষণ করে রাখব। 'আমার গল্প দেখাও' বললে শেষ লেখাটা "
                 "দেখতে পাবে।")
    return "\n".join(lines)


def ep_story_show_text(diary=None, wins=None, progress=None, first_day=None,
                       path=None):
    """ফ্রেম + তথ্য + সর্বশেষ সংরক্ষিত draft।"""
    out = ep_story_text(diary, wins, progress, first_day)
    drafts = ep_story_load(path)
    if drafts:
        last = drafts[-1]
        out += (f"\n\n📝 তোমার সর্বশেষ লেখা "
                f"({_ep_fmt_date(_ep_parse_iso(last.get('date')))}):\n"
                f"{last.get('text', '')}")
    else:
        out += "\n\n(এখনো কোনো গল্প সংরক্ষণ করোনি।)"
    return out


# =====================================================================
#  #782 সার্কুলার গভীর-বিশ্লেষণ (শুধু পেস্ট করা লেখা থেকে)
# =====================================================================

def ep_circular_parse(text):
    """ব্যবহারকারীর পেস্ট করা সার্কুলার লেখা থেকে যা আছে শুধু তাই তোলে।
    কিছুই বানানো হয় না — না পেলে None/খালি। ফেরত dict:
    dates[], deadline, deadline_guessed, age, education[], posts[],
    fee, total_posts।"""
    raw = str(text or "")
    norm = ep_normalize_digits(raw)
    dates = ep_find_dates(raw)
    result = {"dates": [d.isoformat() for d in dates],
              "deadline": None, "deadline_guessed": False,
              "age": None, "education": [], "posts": [],
              "fee": None, "total_posts": None}
    # --- deadline: 'শেষ তারিখ'/'আবেদনের শেষ'-এর কাছের তারিখ, নইলে শেষ তারিখ
    deadline = None
    for kw in ("শেষ তারিখ", "আবেদনের শেষ", "আবেদন শেষ", "শেষ সময়"):
        idx = norm.find(kw)
        if idx >= 0:
            near = ep_parse_date(norm[idx:idx + 80])
            if near is not None:
                deadline = near
                break
    if deadline is None and dates:
        deadline = dates[-1]
        result["deadline_guessed"] = True
    if deadline is not None:
        result["deadline"] = deadline.isoformat()
    # --- age: 'বয়স'-এর আশেপাশের সংখ্যা
    m = re.search(r"বয়স[^0-9]{0,40}?(\d{1,2})\s*(?:থেকে|-)\s*(\d{1,2})",
                  norm)
    if m:
        result["age"] = f"{m.group(1)} থেকে {m.group(2)} বছর"
    else:
        m = re.search(r"বয়স[^0-9]{0,40}?(\d{1,2})", norm)
        if m:
            result["age"] = f"{m.group(1)} বছর"
    # --- fee: 'ফি'-এর আশেপাশের সংখ্যা
    m = re.search(r"ফি[^0-9]{0,40}?(\d+)", norm)
    if m:
        result["fee"] = m.group(1)
    # --- total posts: 'শূন্য পদ'/'পদ সংখ্যা'-এর আশেপাশের সংখ্যা
    for kw in ("শূন্য পদ", "পদ সংখ্যা", "পদসংখ্যা"):
        idx = norm.find(kw)
        if idx >= 0:
            seg = norm[max(0, idx - 30):idx + 60]
            nums = re.findall(r"\d+", seg)
            if nums:
                result["total_posts"] = nums[-1]
                break
    # --- line-based: শিক্ষাগত যোগ্যতা (+ পরের লাইন), পদের নাম
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    for i, ln in enumerate(lines):
        if "শিক্ষাগত যোগ্যতা" in ln:
            entry = ln
            if i + 1 < len(lines):
                entry += " " + lines[i + 1]
            result["education"].append(entry)
        if "পদের নাম" in ln or ln.startswith("পদ:") or "পদ :" in ln:
            name = re.sub(r"^.*?পদের নাম\s*[:：]?\s*", "", ln).strip()
            name = re.sub(r"^পদ\s*[:：]\s*", "", name).strip()
            if name:
                result["posts"].append(name)
    return result


def ep_circular_text(text, today=None):
    """'যা পেলাম' checklist + 'যা পাইনি — নিজে খুঁজে নিও' + deadline
    পর্যন্ত দিন। পাওয়া তথ্য শুধু পেস্ট করা লেখা থেকেই।"""
    today = _ep_today(today)
    p = ep_circular_parse(text)
    found = []
    missing = []
    if p["deadline"]:
        d = _ep_parse_iso(p["deadline"])
        label = f"আবেদনের শেষ তারিখ: {_ep_fmt_date(d)}"
        if p["deadline_guessed"]:
            label += (" (অনুমান — লেখায় 'শেষ তারিখ' স্পষ্ট লিখা পাইনি; "
                      "পাওয়া তারিখগুলোর শেষটা ধরেছি, যাচাই করে নিও)")
        found.append(label)
        if d is not None:
            left = (d - today).days
            if left >= 0:
                found.append(f"শেষ তারিখ পর্যন্ত বাকি: {_bn(left)} দিন")
            else:
                found.append(f"⚠️ এই তারিখ {_bn(-left)} দিন আগে পেরিয়ে "
                             "গেছে — বিজ্ঞপ্তিটা এখনো চালু আছে কিনা যাচাই করো।")
    else:
        missing.append("আবেদনের শেষ তারিখ")
    if p["age"]:
        found.append(f"বয়স: {_bn(p['age'])}")
    else:
        missing.append("বয়সসীমা")
    if p["fee"]:
        found.append(f"আবেদন ফি: {_bn(p['fee'])} (লেখায় 'ফি'-এর পাশে "
                     "পাওয়া সংখ্যা)")
    else:
        missing.append("আবেদন ফি")
    if p["total_posts"]:
        found.append(f"শূন্য পদ: {_bn(p['total_posts'])}টি "
                     "(লেখায় পাওয়া সংখ্যা)")
    else:
        missing.append("শূন্য পদের সংখ্যা")
    for post in p["posts"]:
        found.append(f"পদের নাম: {post}")
    if not p["posts"]:
        missing.append("পদের নাম")
    for edu in p["education"]:
        found.append(f"শিক্ষাগত যোগ্যতা: {edu}")
    if not p["education"]:
        missing.append("শিক্ষাগত যোগ্যতা")
    lines = ["🔎 সার্কুলার বিশ্লেষণ — শুধু তোমার পাঠানো লেখা থেকে যা পেলাম"]
    if found:
        lines.append("")
        lines.append("যা পেলাম:")
        for f in found:
            lines.append(f"✓ {f}")
    else:
        lines.append("লেখাটা থেকে কোনো তারিখ, বয়স, ফি বা পদের তথ্য "
                     "বের করতে পারিনি।")
    if missing:
        lines.append("")
        lines.append("যা পাইনি — নিজে খুঁজে নিও:")
        for mitem in missing:
            lines.append(f"• {mitem}")
    lines.append("")
    lines.append("মনে রেখো: আমি লেখার বাইরে কিছু যোগ করিনি — অফিসিয়াল "
                 "বিজ্ঞপ্তির সঙ্গে মিলিয়ে নিও।")
    return "\n".join(lines)


def ep_is_circular(text):
    t = str(text or "")
    if "সার্কুলার বিশ্লেষণ" in t:
        return True
    return len(t) > 300 and "বিজ্ঞপ্তি" in t and "আবেদন" in t


# =====================================================================
#  #784 উৎস-যাচাই মিনি-পাঠ (static lesson)
# =====================================================================

def ep_verify_lesson_text():
    return (
        "🧐 উৎস-যাচাই মিনি-পাঠ — কোনো খবর/দাবি বিশ্বাস করার আগে ৫ ধাপ\n"
        "\n"
        "১. উৎস কে? — খবরটা কে বলছে? পরিচিত সরকারি দপ্তর/প্রতিষ্ঠান, "
        "নাকি অচেনা পেজ/আইডি? অচেনা উৎস মানেই সন্দেহ দিয়ে শুরু।\n"
        "২. তারিখ দেখো — পুরনো খবর নতুন করে ছড়ানো খুব সাধারণ ফাঁদ। "
        "মূল পোস্ট/বিজ্ঞপ্তির তারিখ যাচাই করো।\n"
        "৩. দ্বিতীয় উৎস — একই খবর আরেকটি নির্ভরযোগ্য জায়গায় আছে "
        "কিনা খোঁজো। একটাই জায়গায় থাকলে থামো।\n"
        "৪. অফিসিয়াল সাইট/নোটিশ — চাকরির খবর হলে সংশ্লিষ্ট দপ্তরের "
        "অফিসিয়াল ওয়েবসাইটের নোটিশ বোর্ডে বিজ্ঞপ্তিটা আছে কিনা মিলাও।\n"
        "৫. সন্দেহ হলে শেয়ার নয় — যাচাই না করে কোনো খবর ফরওয়ার্ড "
        "করবে না; ভুল খবর ছড়ানোও একটা ক্ষতি।\n"
        "\n"
        "উদাহরণ (নমুনা): ধরো, একটি ফেসবুক পেজে লেখা এল — 'অমুক দপ্তরে "
        "৫০০ লোক নেবে, আজই শেষ তারিখ!' — কোথায় কোন ধাপ লাগবে?\n"
        "• ধাপ ১: পেজটা অফিসিয়াল কিনা দেখো (অচেনা হলে সন্দেহ)।\n"
        "• ধাপ ২: পোস্টের তারিখ — পুরনো বিজ্ঞপ্তি ঘুরছে কিনা।\n"
        "• ধাপ ৩: খবরটি অন্য নির্ভরযোগ্য মাধ্যমে আছে কিনা।\n"
        "• ধাপ ৪: দপ্তরের অফিসিয়াল সাইটে বিজ্ঞপ্তিটি খুঁজে 'শেষ তারিখ' "
        "মিলাও — পেজের দাবি নয়, নোটিশের তারিখই আসল।\n"
        "• ধাপ ৫: মিল না পেলে — শেয়ার/আবেদন কোনোটাই নয়, আগে যাচাই।\n"
        "(এটি একটি পাঠ — উদাহরণের দাবিটি কাল্পনিক নমুনা, কোনো আসল "
        "বিজ্ঞপ্তি নয়।)"
    )


# =====================================================================
#  Router — ep_planning_handle(text, low) -> str | None
# =====================================================================

def ep_planning_handle(text, low=None):
    """Planning pack-এর সব trigger route করে; না মিললে None (fall-through)।"""
    text = str(text or "").strip()
    if not text:
        return None
    # --- #781 গল্প: draft save আগে (view কমান্ডের সঙ্গে গুলিয়ে না যায়)
    for prefix in ("গল্প লিখলাম:", "গল্প লিখলামঃ", "আমার গল্প:",
                   "আমার গল্পঃ"):
        if text.startswith(prefix):
            body = text[len(prefix):].strip()
            if not body:
                return ("লেখাটা খালি পেয়েছি — 'গল্প লিখলাম:'-এর পরে "
                        "তোমার লেখাটা দাও।")
            if ep_story_save(body):
                return ("📖 তোমার গল্পটা সংরক্ষণ করে রাখলাম। "
                        "'আমার গল্প দেখাও' বললে আবার দেখতে পাবে।")
            return "গল্পটা সংরক্ষণ করতে সমস্যা হয়েছে — আবার চেষ্টা করো।"
    if "আমার গল্প দেখাও" in text or "আমার গল্প" in text:
        return ep_story_show_text()
    if "গল্পের ফ্রেম" in text or "নিজের গল্প" in text:
        return ep_story_text()
    # --- #782 সার্কুলার (লম্বা পেস্ট আগে ধরতে হয়)
    if ep_is_circular(text):
        body = text.replace("সার্কুলার বিশ্লেষণ", "", 1).strip(" :：")
        return ep_circular_text(body if body else text)
    # --- #784 উৎস-যাচাই পাঠ
    if "উৎস যাচাই" in text or "উৎস-যাচাই" in text or \
            "তথ্য যাচাই" in text:
        return ep_verify_lesson_text()
    # --- #766 ক্যাম্পেইন সেট (view-এর আগে)
    if text.startswith("ক্যাম্পেইন:") or text.startswith("ক্যাম্পেইনঃ") \
            or "পরীক্ষার তারিখ" in text:
        out = ep_campaign_set_from_text(text)
        if out is not None:
            return out
    # --- #783 ইভেন্ট যোগ / তালিকা
    if text.startswith("ইভেন্ট যোগ"):
        out = ep_event_add_from_text(text)
        if out is not None:
            return out
    if "ইভেন্ট তালিকা" in text or "আমার ইভেন্ট" in text:
        return ep_event_list_text()
    if "তারিখ সংঘাত" in text or "তারিখ-সংঘাত" in text:
        return ep_conflicts_text()
    # --- #770 পরীক্ষা-সপ্তাহ প্রোটোকল
    if "পরীক্ষা-সপ্তাহ" in text or "পরীক্ষার সপ্তাহ" in text or \
            "পরীক্ষা সপ্তাহ" in text:
        return ep_exam_week_text()
    # --- #769 সম্পদ-বণ্টন
    if "সম্পদ বণ্টন" in text or "সম্পদ-বণ্টন" in text or \
            "সময় বণ্টন" in text or "সময়-বণ্টন" in text:
        return ep_allocation_text()
    # --- #767 মাইলফলক
    if "মাইলফলক" in text:
        return ep_milestones_text()
    # --- #766 ক্যাম্পেইন view (সবশেষে — সেট কমান্ড আগে ধরা হয়েছে)
    if "ক্যাম্পেইন" in text:
        return ep_campaign_text()
    return None


# -*- coding: utf-8 -*-
"""
elite_engine_pack.py — Desktop Sokhi v1.9.0: ELITE ENGINE-READY প্যাক
=====================================================================
Items: #754, #757, #760, #761, #762, #768, #771, #776, #778, #779, #780
(বিল্ড-অর্ডারে "১০টি" বলা হলেও তালিকায় আসলে ১১টি আইটেম গোনা যায়;
এই প্যাকে ১১টিরই প্যানেল আছে, কোনোটাই বাদ দেওয়া হয়নি।)

এই প্যাকের কাজ ENGINE বানানো: command surface, panel, data-intake
guidance, আর যেখানে বলা হয়েছে সেখানে storage। আসল বিশ্লেষণের জন্য
যে বাইরের তথ্য লাগবে (কোনো বোর্ডের বিগত প্রশ্নপত্র, কাট-অফ নম্বর,
বোর্ডের আচরণের তথ্য) সেটা মালিক পরে দেবেন — ততদিন প্রতিটি প্যানেলে
সৎ empty state থাকে এবং এই লাইনটি থাকেই:

    "আসল তথ্য দিলে এখানে বিশ্লেষণ আসবে।"

বাঁধাই করা নিয়ম (binding):
  * কোনো পরিসংখ্যান, কাট-অফ, প্রশ্নের ডেটা বা বোর্ডের আচরণ
    বানিয়ে বলা হয় না — কখনো না।
  * যেসব সংখ্যা দেখানো হয় সেগুলো শুধু ব্যবহারকারীর নিজের ফাইল/
    ব্যাংক গুনে পাওয়া (study-progress.json, study-wrong-book.json,
    OFFLINE_BANK) এবং সেগুলো "নিজস্ব তথ্য" বলে লেবেল করা থাকে।
  * #760-র আভাসগুলো প্রতিটিই "আভাস মাত্র" লেবেলসহ আসে — এগুলো
    নিজের ভুলের খাতার প্যাটার্ন-অনুমান, নিশ্চিত কারণ নয়।
  * সাধারণ পরামর্শ যেখানে আছে সেখানে "সাধারণ পরামর্শ" /
    "সাধারণ পর্যবেক্ষণ-পরামর্শ" লেবেল দেওয়া আছে।

Conventions (v1.5 study pack-এর মতো):
  * সব symbol-এর prefix ee_ / EE_ — host namespace-এ সংঘর্ষ নেই।
  * Host globals (load_json, save_json, DATA, OFFLINE_BANK,
    _STUDY_PROGRESS_FILE, _WRONG_BOOK_FILE) call time-এ
    globals().get(...) দিয়ে resolve করা হয় — paste করলে host-এর
    গুলোই জেতে, test-এ stub/inject করা যায়।
  * প্রতিটি text function-এ injectable parameter আছে (bank=,
    wrong=, progress=, data_dir=) — None হলে host থেকে resolve।
  * 100% ফ্রি, offline-only: কোনো network / API key লাগে না।

Verified data shapes (app/sokhi.py):
  study-progress.json:
    {subject: {sessions, mock_tests, total_steps, weak[],
               last_topic, last_date}}
  study-wrong-book.json:
    [{q, options, correct(TEXT), your_answer(TEXT), subject,
      topic, date}]
  OFFLINE_BANK:
    {subject: [{q, options, answer(int), topic}]}

নতুন data files (DATA ফোল্ডারে, প্রথম save-এ তৈরি হয়):
  elite-planb.json      — #768: {"text": str, "updated": iso str}
  elite-protocols.json  — EE_PROTO_FILE; keys: EE_PROTO_KEY_* দেখো
                          (#771 / #778 / #780-এর frame এক ফাইলে)।
"""

import json
import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path

# ------------------------------------------------------------------ constants
EE_BN_DIGITS_MAP = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
EE_NO_DATA = "এখনো ডেটা নেই"

# সৎ empty-state লাইন — প্রতিটি engine panel-এ অবশ্যই থাকবে।
EE_ENGINE_LINE = "আসল তথ্য দিলে এখানে বিশ্লেষণ আসবে।"

EE_PLANB_FILENAME = "elite-planb.json"
EE_PROTO_FILENAME = "elite-protocols.json"
# protocols ফাইলের নাম (DATA / EE_PROTO_FILE পথে resolve হয়)।
EE_PROTO_FILE = EE_PROTO_FILENAME
EE_PROTO_KEY_RESULT_DAY = "771_result_day"
EE_PROTO_KEY_MENTALITY = "778_mentality"
EE_PROTO_KEY_WAITING = "780_waiting"

# item: (নম্বর, শিরোনাম) — status overview এই তালিকা থেকেই বানানো হয়।
EE_ITEMS = [
    ("754", "প্রশ্নকর্তার উদ্দেশ্য-বিশ্লেষণ"),
    ("757", "প্রশ্নের ভাষা-বিশ্লেষণ"),
    ("760", "দুর্বলতার মূল-কারণ বিশ্লেষণ"),
    ("761", "নম্বর-ফাঁক বিশ্লেষণ"),
    ("762", "অধ্যায়-মূল্য (ROI) বিশ্লেষণ"),
    ("768", "সংকট-পরিকল্পনা (প্ল্যান বি)"),
    ("771", "ফল-দিবস প্রোটোকল"),
    ("776", "বোর্ডের ভাষা পড়া"),
    ("778", "বিজয়ী-মানসিকতা শৃঙ্খলা"),
    ("779", "চাপে শীতলতা প্রশিক্ষণ"),
    ("780", "দীর্ঘ-অপেক্ষা ব্যবস্থাপনা"),
]


def ee_bn(x):
    """Local mirror of host _bn_num(): English digits -> Bangla digits."""
    return str(x).translate(EE_BN_DIGITS_MAP)


# ------------------------------------------------------- global fallbacks
# Helpers deliberately look names up in globals() at CALL time, so
# (a) the pack works when pasted into sokhi.py (host globals win), and
# (b) tests can stub module globals or pass data directly.


def ee_load_via_host(path, default):
    fn = globals().get("load_json")
    if callable(fn) and path is not None:
        try:
            return fn(path, default)
        except Exception:
            pass
    # Standalone fallback (tests without host stubs): plain JSON read.
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def ee_save_via_host(path, obj):
    fn = globals().get("save_json")
    if callable(fn) and path is not None:
        try:
            fn(path, obj)
            return True
        except Exception:
            pass
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj, ensure_ascii=False, indent=2),
                     encoding="utf-8")
        return True
    except Exception:
        return False


def ee_resolve_bank(bank=None):
    if bank is not None:
        return bank if isinstance(bank, dict) else {}
    g = globals().get("OFFLINE_BANK")
    return g if isinstance(g, dict) else {}


def ee_resolve_progress(progress=None):
    if progress is not None:
        return progress if isinstance(progress, dict) else {}
    path = globals().get("_STUDY_PROGRESS_FILE")
    data = ee_load_via_host(path, {})
    return data if isinstance(data, dict) else {}


def ee_resolve_wrong(wrong=None):
    if wrong is not None:
        return wrong if isinstance(wrong, list) else []
    path = globals().get("_WRONG_BOOK_FILE")
    data = ee_load_via_host(path, [])
    return data if isinstance(data, list) else []


def ee_resolve_data_dir(data_dir=None):
    if data_dir is not None:
        return Path(data_dir)
    g = globals().get("DATA")
    if g is not None:
        return Path(g)
    return Path("data")


def ee_planb_path(data_dir=None):
    return ee_resolve_data_dir(data_dir) / EE_PLANB_FILENAME


def ee_proto_path(data_dir=None):
    return ee_resolve_data_dir(data_dir) / EE_PROTO_FILE


def ee_now_iso():
    return datetime.now().isoformat(timespec="seconds")


def ee_wrong_by_topic(wrong):
    c = Counter()
    for w in wrong or []:
        if isinstance(w, dict):
            c[str(w.get("topic") or "সাধারণ")] += 1
    return c


def ee_wrong_by_date(wrong):
    c = Counter()
    for w in wrong or []:
        if isinstance(w, dict) and w.get("date"):
            c[str(w.get("date"))] += 1
    return c


def ee_wrong_by_question(wrong):
    c = Counter()
    for w in wrong or []:
        if isinstance(w, dict) and str(w.get("q") or "").strip():
            c[str(w.get("q")).strip()] += 1
    return c


def ee_header(no, title, emoji="🧩"):
    return f"{emoji} #{ee_bn(no)} {title}"


def ee_engine_footer():
    return f"ইঞ্জিন অবস্থা: {EE_ENGINE_LINE}"


# =====================================================================
#  #754 প্রশ্নকর্তার উদ্দেশ্য-বিশ্লেষণ — ENGINE (বিগত প্রশ্নপত্র লাগবে)
# =====================================================================

def ee_panel_754(bank=None, wrong=None, progress=None, data_dir=None):
    """কোন বোর্ড/পদ প্রশ্নকর্তা কী চায় — সেটা জানতে ঐ বোর্ডের বিগত
    প্রশ্নপত্র লাগবে, যা এখনো দেওয়া হয়নি। এই প্যানেল শুধু বলে:
    কী দিতে হবে, তথ্য এলে কী কী হিসাব হবে, আর নিজের OFFLINE_BANK-এ
    এখন কী context আছে (শুধু গোনা সংখ্যা, বাইরের কিছু নয়)।"""
    bank = ee_resolve_bank(bank)
    lines = [
        ee_header("754", "প্রশ্নকর্তার উদ্দেশ্য-বিশ্লেষণ", "🎯"),
        "",
        "কী তথ্য লাগবে (তুমি দিলে বিশ্লেষণ শুরু হবে):",
        "• কোন বোর্ড/পদের বিগত প্রশ্নের তালিকা বা ছবি — কোন বোর্ড, "
        "কোন পদ, কোন সালের প্রশ্ন, সেটা লিখে দিলে ভালো হয়।",
        "• প্রশ্নগুলো লেখা (টেক্সট) আকারে দিলে হিসাব সবচেয়ে নির্ভুল "
        "হবে; ছবি দিলেও চলবে, তখন পড়ে নিতে হবে।",
        "",
        "তথ্য এলে যা যা হিসাব হবে:",
        "• টপিক ফ্রিকোয়েন্সি — কোন টপিক থেকে কতবার প্রশ্ন এসেছে",
        "• পুনরাবৃত্ত প্রশ্ন — হুবহু বা প্রায়-হুবহু ফিরে আসা প্রশ্নের তালিকা",
        "• কোন টপিকে প্রশ্নকর্তা বারবার ফিরে যান — তার ধরন",
        "",
    ]
    total_q = sum(len(v or []) for v in bank.values())
    if bank and total_q:
        lines.append("নিজস্ব তথ্য — এখন অফলাইন প্রশ্ন-ব্যাংকে যা আছে "
                     "(এটা নিজের ব্যাংকের হিসাব, বোর্ডের তথ্য নয়):")
        for subj in sorted(bank.keys()):
            lines.append(f"• {subj}: {ee_bn(len(bank[subj] or []))}টি প্রশ্ন")
        lines.append(f"মোট: {ee_bn(total_q)}টি প্রশ্ন")
    else:
        lines.append(f"নিজস্ব তথ্য: {EE_NO_DATA} — অফলাইন প্রশ্ন-ব্যাংকেও "
                     "এখনো কোনো প্রশ্ন পাইনি।")
    lines.append("")
    lines.append(ee_engine_footer())
    return "\n".join(lines)


# =====================================================================
#  #757 প্রশ্নের ভাষা-বিশ্লেষণ — ENGINE (বিগত প্রশ্নের করপাস লাগবে)
# =====================================================================

def ee_panel_757(bank=None, wrong=None, progress=None, data_dir=None):
    """প্রশ্নের ভাষার ফাঁদ শেখানোর ইঞ্জিন। আসল করপাস এলে ঐ করপাসের
    ভাষা ধরেই শেখানো হবে; তার আগে শুধু সাধারণ পরামর্শের preview —
    লেবেলসহ, কোনো বোর্ডের নামে চালানো হয়নি।"""
    lines = [
        ee_header("757", "প্রশ্নের ভাষা-বিশ্লেষণ", "🔤"),
        "",
        "কী তথ্য লাগবে:",
        "• বিগত প্রশ্নের করপাস — কোনো বোর্ড/পদের পুরনো প্রশ্নের "
        "তালিকা বা ছবি। করপাস এলে সেখানকার আসল বাক্য ধরেই ভাষার "
        "ধরন শেখানো হবে।",
        "",
        "তথ্য এলে যা শেখানো হবে:",
        "• নেতিবাচক শব্দের ফাঁদ চেনা ও দাগ দেওয়ার অভ্যাস",
        "• পরম শব্দ (সবসময়/কখনোই) দেখলে সতর্ক হওয়ার ধরন",
        "• লম্বা বাক্যের প্রশ্নে আসল জিজ্ঞাসা আলাদা করা",
        "",
        "সাধারণ পরামর্শ (preview — এটা কোনো বোর্ডের ডেটা নয়):",
        "• শব্দের ফাঁদ: 'সঠিক নয়', 'ব্যতীত' ধরনের নেতিবাচক শব্দ "
        "থাকলে প্রশ্নটা উল্টো অর্থে পড়তে হয় — তাড়াহুড়োয় এই "
        "শব্দটা মিস গেলেই জানা উত্তরও ভুল হয়।",
        "• 'কোনটি ভুল', 'প্রযোজ্য নয়', 'ছাড়া' — এই ধরনের শব্দ "
        "দেখলেই আগে দাগ দিয়ে নাও, তারপর উত্তর ভাবো।",
        "• বিকল্পে 'সবগুলোই সঠিক' থাকলে প্রতিটি বিকল্প আলাদা করে "
        "যাচাই না করে সেটা বেছে নিও না।",
        "",
        ee_engine_footer(),
    ]
    return "\n".join(lines)


# =====================================================================
#  #760 দুর্বলতার মূল-কারণ — আংশিক বাস্তব (নিজের ভুলের খাতা থেকে)
# =====================================================================

def ee_rootcause_text(wrong=None, progress=None):
    """নিজের study-wrong-book.json থেকেই প্যাটার্ন-আভাস বের করে।
    প্রতিটি আভাসই "আভাস মাত্র" — নিশ্চিত কারণ দাবি করা হয় না, আর
    পাশে সমর্থনকারী গোনা সংখ্যা দেখানো হয়:
      (a) একই টপিকে ভুল >=৩  -> ধারণার ঘাটতির আভাস
      (b) ১-করে ভুল >=৫ টপিকে ছড়ানো -> অসাবধানতা/তাড়াহুড়ার আভাস
      (c) একই তারিখে ভুল >=৫ -> সেই দিনের চাপ/সময়ের আভাস
      (d) একই প্রশ্নে ভুল >=২ -> ঐ প্রশ্নটা আবার পড়া দরকার
    progress প্যারামিটার signature-এর জন্য রাখা (ভবিষ্যতে সেশন-
    context যোগের জায়গা); বর্তমান আভাসগুলো শুধু wrong-book থেকেই।"""
    wrong = ee_resolve_wrong(wrong)
    lines = [
        ee_header("760", "দুর্বলতার মূল-কারণ বিশ্লেষণ", "🩺"),
        "(শুধু তোমার নিজের ভুলের খাতা গুনে বলছি — এগুলো নিশ্চিত "
        "কারণ নয়, আভাস মাত্র।)",
    ]
    if not wrong:
        lines.append("")
        lines.append(f"{EE_NO_DATA} — ভুলের খাতা এখনো খালি। মক টেস্টে "
                     "ভুল জমলেই এখানে প্যাটার্ন-আভাস দেখা যাবে।")
        lines.append("")
        lines.append(ee_engine_footer())
        return "\n".join(lines)

    lines.append("")
    lines.append(f"নিজস্ব তথ্য: মোট ভুল জমেছে {ee_bn(len(wrong))}টি।")
    found = []

    topic_counts = ee_wrong_by_topic(wrong)
    for topic, cnt in topic_counts.most_common():
        if cnt >= 3:
            found.append(
                f"• আভাস মাত্র — ধারণার ঘাটতির আভাস: '{topic}' টপিকে "
                f"{ee_bn(cnt)}বার ভুল হয়েছে (একই টপিকে ৩ বার বা বেশি)। "
                "একই জায়গায় বারবার আটকালে সাধারণত ধারণাটাই পরিষ্কার "
                "হয়নি — ঐ টপিক গোড়া থেকে আবার পড়া দরকার হতে পারে।")

    if len(topic_counts) >= 5 and max(topic_counts.values()) == 1:
        found.append(
            f"• আভাস মাত্র — ছড়ানো ভুল = অসাবধানতা/তাড়াহুড়ার আভাস: "
            f"{ee_bn(len(topic_counts))}টি আলাদা টপিকে ১টি করে ভুল, "
            "কোনো টপিকেই দ্বিতীয় ভুল নেই। ধারণা ঠিক থাকলেও তাড়াহুড়ো "
            "বা মনোযোগ সরে গেলে এমন ছড়ানো ভুল হয়।")

    date_counts = ee_wrong_by_date(wrong)
    for dstr, cnt in date_counts.most_common():
        if cnt >= 5:
            found.append(
                f"• আভাস মাত্র — সেই দিনের চাপ/সময়ের আভাস: {dstr} "
                f"তারিখে একদিনেই {ee_bn(cnt)}টি ভুল জমেছে। ঐ দিন "
                "হয়তো সময়ের চাপ, ক্লান্তি বা তাড়াহুড়ো ছিল।")

    q_counts = ee_wrong_by_question(wrong)
    for qtext, cnt in q_counts.most_common():
        if cnt >= 2:
            short = qtext if len(qtext) <= 60 else qtext[:60] + "…"
            found.append(
                f"• আভাস মাত্র — এই প্রশ্নটা বিশেষভাবে আবার পড়া দরকার: "
                f"\"{short}\" — একই প্রশ্নে {ee_bn(cnt)}বার ভুল হয়েছে।")

    lines.append("")
    if found:
        lines.append("পাওয়া আভাসগুলো:")
        lines.extend(found)
    else:
        lines.append("এখনো স্পষ্ট কোনো প্যাটার্নের আভাস পাইনি — আরও "
                     "কিছু ভুল জমলে আভাস পরিষ্কার হবে।")
    lines.append("")
    lines.append(ee_engine_footer())
    return "\n".join(lines)


def ee_panel_760(bank=None, wrong=None, progress=None, data_dir=None):
    return ee_rootcause_text(wrong=wrong, progress=progress)


# =====================================================================
#  #761 নম্বর-ফাঁক বিশ্লেষণ — ENGINE (কাট-অফের তথ্য লাগবে)
# =====================================================================

def ee_panel_761(bank=None, wrong=None, progress=None, data_dir=None):
    """লক্ষ্য/কাট-অফ থেকে নিজের নম্বরের ফাঁক হিসাবের ইঞ্জিন।
    কাট-অফের কোনো সংখ্যা বানানো হয় না; নিজের যে সংখ্যা ফাইলে
    আছে শুধু সেগুলোই "নিজস্ব তথ্য" লেবেলে দেখানো হয়।"""
    progress = ee_resolve_progress(progress)
    wrong = ee_resolve_wrong(wrong)
    total_mock = 0
    for info in progress.values():
        if isinstance(info, dict):
            try:
                total_mock += int(info.get("mock_tests") or 0)
            except Exception:
                pass
    lines = [
        ee_header("761", "নম্বর-ফাঁক বিশ্লেষণ", "📏"),
        "",
        "নিজস্ব তথ্য (তোমার নিজের রেকর্ড থেকে গোনা):",
        f"• মোট মক টেস্ট সংখ্যা: {ee_bn(total_mock)}টি",
        f"• ভুলের মোট সংখ্যা: {ee_bn(len(wrong))}টি",
    ]
    if not progress and not wrong:
        lines.append(f"• ({EE_NO_DATA} — পড়ার রেকর্ড বা ভুলের খাতায় "
                     "এখনো কিছু জমেনি।)")
    lines += [
        "",
        "কাট-অফ অংশ:",
        "• কাট-অফের তথ্য দিলে ফাঁক হিসাব হবে — কোন পদ/বোর্ডের "
        "কাট-অফ, কোন সালের, আর তোমার লক্ষ্য নম্বর কত, এই তিনটা "
        "দিলেই নিজের বর্তমান অবস্থান থেকে ফাঁকটা হিসাব করা যাবে।",
        "• ততদিন কোনো কাট-অফ সংখ্যা আমি বানিয়ে বলব না।",
        "",
        ee_engine_footer(),
    ]
    return "\n".join(lines)


# =====================================================================
#  #762 অধ্যায়-মূল্য (ROI) — ENGINE (টপিকের ওজন লাগবে)
# =====================================================================

def ee_panel_762(bank=None, wrong=None, progress=None, data_dir=None):
    """কোন অধ্যায় পড়লে কত নম্বর ওঠে (ROI) — তার জন্য বিগত
    প্রশ্নপত্রের টপিকভিত্তিক ওজন লাগবে। অন্তর্বর্তী ব্যক্তিগত
    সংকেত হিসেবে শুধু নিজের ভুল-by-topic হিসাব দেখানো হয়,
    স্পষ্ট লেবেলসহ: এটা বোর্ডের ওজন নয়।"""
    wrong = ee_resolve_wrong(wrong)
    lines = [
        ee_header("762", "অধ্যায়-মূল্য (ROI) বিশ্লেষণ", "⚖️"),
        "",
        "কী তথ্য লাগবে:",
        "• বিগত প্রশ্নপত্রের টপিকভিত্তিক ওজন — কোন টপিক থেকে "
        "কতগুলো প্রশ্ন এসেছে, সেই তালিকা বা ছবি। ওজন এলে পড়ার "
        "সময়ের সঙ্গে মিলিয়ে অধ্যায়-মূল্য (ROI) সাজানো যাবে।",
        "",
    ]
    if wrong:
        lines.append("অন্তর্বর্তী ব্যক্তিগত সংকেত — নিজের ভুল টপিক "
                     "অনুযায়ী (শীর্ষ ১০):")
        for topic, cnt in ee_wrong_by_topic(wrong).most_common(10):
            lines.append(f"• {topic} — {ee_bn(cnt)}বার ভুল")
        lines.append("(লেবেল: এটা নিজের ভুলের হিসাব, বোর্ডের ওজন নয় "
                     "— শুধু নিজের দুর্বল জায়গা বোঝার জন্য।)")
    else:
        lines.append(f"নিজস্ব তথ্য: {EE_NO_DATA} — ভুলের খাতা খালি, "
                     "তাই ব্যক্তিগত সংকেতও এখনো নেই।")
    lines.append("")
    lines.append(ee_engine_footer())
    return "\n".join(lines)


# =====================================================================
#  #768 সংকট-পরিকল্পনা (প্ল্যান বি) — REAL storage engine
#  File: DATA / elite-planb.json  ->  {"text", "updated"}
# =====================================================================

def ee_planb_load(data_dir=None):
    data = ee_load_via_host(ee_planb_path(data_dir), {})
    return data if isinstance(data, dict) else {}


def ee_planb_save(plan_text, data_dir=None):
    """প্ল্যান বি সেভ/আপডেট করে confirmation text ফেরত দেয়।"""
    plan_text = str(plan_text or "").strip()
    if not plan_text:
        return ee_panel_768(data_dir=data_dir)
    rec = {"text": plan_text, "updated": ee_now_iso()}
    ee_save_via_host(ee_planb_path(data_dir), rec)
    return ("✅ প্ল্যান বি সেভ হয়েছে।\n"
            f"• লেখা: {plan_text}\n"
            f"• আপডেট: {ee_bn(rec['updated'])}\n"
            "বদলাতে চাইলে আবার 'প্ল্যান বি: <নতুন লেখা>' বললেই হবে।")


def ee_panel_768(bank=None, wrong=None, progress=None, data_dir=None):
    rec = ee_planb_load(data_dir)
    lines = [
        ee_header("768", "সংকট-পরিকল্পনা (প্ল্যান বি)", "🛟"),
        "",
    ]
    if rec.get("text"):
        lines.append("তোমার সেভ করা প্ল্যান বি:")
        lines.append(f"• {rec.get('text')}")
        if rec.get("updated"):
            lines.append(f"• শেষ আপডেট: {ee_bn(rec.get('updated'))}")
    else:
        lines.append(f"{EE_NO_DATA} — এখনো কোনো প্ল্যান বি সেভ করা নেই।")
    lines += [
        "",
        "প্ল্যান বি-তে যা যা থাকা ভালো (পূরণ করার কাঠামো):",
        "• বিকল্প পরীক্ষা/পদ: এই পরীক্ষা না হলে কোন পরীক্ষা/পদে যাবে — ___",
        "• অসুস্থ হলে করণীয়: পরীক্ষার আগে/দিনে অসুস্থ হলে কী করবে — ___",
        "• জরুরি যোগাযোগ: বিপদে কার সঙ্গে যোগাযোগ করবে, নম্বর কোথায় — ___",
        "• টাকা/কাগজপত্রের বিকল্প ব্যবস্থা: — ___",
        "",
        "সেভ করতে বলো: 'প্ল্যান বি: <তোমার লেখা>' — যেমন:",
        "'প্ল্যান বি: মূল পরীক্ষা মিস হলে পরের সার্কুলারের পদে আবেদন, "
        "অসুস্থ হলে আগের দিনই ডাক্তার দেখানো'",
        "",
        ee_engine_footer(),
    ]
    return "\n".join(lines)


# =====================================================================
#  Protocols storage — DATA / elite-protocols.json (EE_PROTO_FILE)
#  একটাই ফাইল, keys: #771 result-day, #778 mentality, #780 waiting
# =====================================================================

def ee_proto_load(data_dir=None):
    data = ee_load_via_host(ee_proto_path(data_dir), {})
    return data if isinstance(data, dict) else {}


def ee_proto_get(key, data_dir=None):
    rec = ee_proto_load(data_dir).get(key)
    return rec if isinstance(rec, dict) else {}


def ee_proto_save(key, value_text, data_dir=None):
    data = ee_proto_load(data_dir)
    data[key] = {"text": str(value_text or "").strip(),
                 "updated": ee_now_iso()}
    ee_save_via_host(ee_proto_path(data_dir), data)
    return data[key]


def ee_proto_save_reply(label, key, value_text, data_dir=None):
    rec = ee_proto_save(key, value_text, data_dir=data_dir)
    return (f"✅ {label} সেভ হয়েছে।\n"
            f"• লেখা: {rec['text']}\n"
            f"• আপডেট: {ee_bn(rec['updated'])}")


def ee_proto_saved_lines(key, data_dir=None):
    rec = ee_proto_get(key, data_dir)
    if rec.get("text"):
        return [f"সেভ করা লেখা: {rec.get('text')}",
                f"(শেষ আপডেট: {ee_bn(rec.get('updated'))})"]
    return [f"সেভ করা লেখা: {EE_NO_DATA}"]


# =====================================================================
#  #771 ফল-দিবস প্রোটোকল — ENGINE (ফলাফলের তথ্য এলে সক্রিয়)
# =====================================================================

def ee_panel_771(bank=None, wrong=None, progress=None, data_dir=None):
    lines = [
        ee_header("771", "ফল-দিবস প্রোটোকল", "📋"),
        "",
        "ফলাফলের দিনের কাঠামো (যা যা লাগবে তার তালিকা-খালি ঘর):",
        "☐ ফলাফল দেখার ওয়েবসাইট/নোটিশ বোর্ড: ___",
        "☐ রোল / রেজিস্ট্রেশন নম্বর রাখার জায়গা: ___",
        "☐ লাগবে এমন কাগজ (প্রবেশপত্র, আইডি ইত্যাদি): ___",
        "☐ ফলাফল পেলে প্রথমে যাকে জানাবে: ___",
        "☐ ফলাফল প্রত্যাশামতো না হলে পরের ধাপ (প্ল্যান বি দেখো): ___",
        "",
    ]
    lines += ee_proto_saved_lines(EE_PROTO_KEY_RESULT_DAY, data_dir)
    lines += [
        "নিজেরটা লিখে রাখতে বলো: 'ফলদিবস প্রোটোকল: <তোমার লেখা>'",
        "",
        "ফলাফলের তারিখ/তথ্য দিলে সক্রিয় হবে — তারিখ এলেই এই "
        "প্রোটোকল ধরে ধাপে ধাপে এগোনো যাবে।",
        ee_engine_footer(),
    ]
    return "\n".join(lines)


# =====================================================================
#  #776 বোর্ডের ভাষা পড়া — ENGINE (ভাইভা অভিজ্ঞতা/বোর্ডের তথ্য লাগবে)
# =====================================================================

def ee_panel_776(bank=None, wrong=None, progress=None, data_dir=None):
    lines = [
        ee_header("776", "বোর্ডের ভাষা পড়া", "🗣️"),
        "",
        "কী তথ্য লাগবে:",
        "• ভাইভা অভিজ্ঞতা/বোর্ডের তথ্য — কোন বোর্ডে, কী ধরনের প্রশ্ন "
        "হয়েছিল, নিজের বা পরিচিতের আসল অভিজ্ঞতার বর্ণনা। সেই "
        "অভিজ্ঞতা জমলেই বোর্ডভিত্তিক প্রস্তুতি সাজানো যাবে; কোনো "
        "বোর্ড আসলে কী করে তা আমি বানিয়ে বলব না।",
        "",
        "সাধারণ পর্যবেক্ষণ-পরামর্শ (সাধারণ — কোনো নির্দিষ্ট বোর্ডের "
        "তথ্য নয়):",
        "• প্রশ্ন পুরোটা শুনে শেষ হতে দাও, মাঝখানে থামিয়ে উত্তর "
        "শুরু করো না — এটা প্রায় সব জায়গাতেই ভালো অভ্যাস।",
        "• না জানলে সরাসরি, ভদ্রভাবে বলা সাধারণত নিরাপদ — আন্দাজে "
        "লম্বা উত্তর বানানো ঝুঁকিপূর্ণ হতে পারে।",
        "• বোর্ডের প্রশ্নের সুর (কঠোর/বন্ধুসুলভ) দেখে নিজের গতি "
        "মেলাও — এটা পর্যবেক্ষণের সাধারণ কৌশল।",
        "",
        ee_engine_footer(),
    ]
    return "\n".join(lines)


# =====================================================================
#  #778 বিজয়ী-মানসিকতা শৃঙ্খলা — ENGINE (routine frame, protocols file)
# =====================================================================

def ee_panel_778(bank=None, wrong=None, progress=None, data_dir=None):
    lines = [
        ee_header("778", "বিজয়ী-মানসিকতা শৃঙ্খলা", "🏆"),
        "",
        "প্রতিদিনের মানসিকতা-রুটিনের কাঠামো (ঘরগুলো তুমি পূরণ করবে):",
        "• সকাল: ___ (জেগে প্রথম ১০ মিনিটে কী ভাববে/করবে)",
        "• পড়ার আগে: ___ (পড়া শুরুর আগের ছোট্ট আচার)",
        "• রাতে: ___ (ঘুমানোর আগে দিনের হিসাব/আগামী দিনের ভাবনা)",
        "",
    ]
    lines += ee_proto_saved_lines(EE_PROTO_KEY_MENTALITY, data_dir)
    lines += [
        "নিজের রুটিন সেভ করতে বলো: 'মানসিকতা রুটিন: <তোমার লেখা>' "
        "— পরে 'মানসিকতা' বললেই সেভ করাটা দেখা যাবে।",
        "",
        ee_engine_footer(),
    ]
    return "\n".join(lines)


# =====================================================================
#  #779 চাপে শীতলতা প্রশিক্ষণ — ENGINE (আছে এমনটার দিকে নির্দেশ)
# =====================================================================

def ee_panel_779(bank=None, wrong=None, progress=None, data_dir=None):
    lines = [
        ee_header("779", "চাপে শীতলতা প্রশিক্ষণ", "🧊"),
        "",
        "ইতিমধ্যে যা আছে (শুধু নির্দেশ — এই প্যাক সেটার ওপর "
        "নির্ভর করে না):",
        f"• #{ee_bn(759)} চাপ-অনুকরণ (pressure sim) — ট্রেনিং প্যাকে "
        "সময়ের চাপে অনুশীলনের ব্যবস্থা আছে; 'চাপ' অনুশীলন চাইলে "
        "সেটা ব্যবহার করো।",
        "",
        "ব্যক্তিগত প্রশিক্ষণের জন্য যা লাগবে:",
        "• নিজের চাপের রেকর্ড জমলে ব্যক্তিগত প্রশিক্ষণ হবে — কোন "
        "পরিস্থিতিতে চাপ বাড়ে, মক টেস্টে সময়ের চাপে কোথায় ভুল "
        "বাড়ে, সেই রেকর্ড জমলেই সেটা ধরে অনুশীলন সাজানো যাবে।",
        "• ততদিন সাধারণ নিয়ম: পরীক্ষার হলে আটকে গেলে প্রশ্নটা "
        "ছেড়ে এগিয়ে যাওয়া, শেষে সময় থাকলে ফিরে আসা।",
        "",
        ee_engine_footer(),
    ]
    return "\n".join(lines)


# =====================================================================
#  #780 দীর্ঘ-অপেক্ষা ব্যবস্থাপনা — ENGINE (waiting frame, protocols)
# =====================================================================

def ee_panel_780(bank=None, wrong=None, progress=None, data_dir=None):
    lines = [
        ee_header("780", "দীর্ঘ-অপেক্ষা ব্যবস্থাপনা", "⏳"),
        "",
        "ফলাফলের অপেক্ষায় প্রতিদিনের ছক কাঠামো (খালি ছক — তুমি "
        "পূরণ করবে):",
        "• প্রতিদিনের হালকা পড়া/রিভিশন: ___",
        "• পরের পরীক্ষার প্রস্তুতির অংশ: ___",
        "• বিশ্রাম/পরিবারের সময়: ___",
        "• সপ্তাহে একদিন নিজের অগ্রগতি দেখা: ___",
        "• মন খারাপ হলে করণীয়: ___",
        "",
    ]
    lines += ee_proto_saved_lines(EE_PROTO_KEY_WAITING, data_dir)
    lines += [
        "নিজের ছক সেভ করতে বলো: 'অপেক্ষা ছক: <তোমার লেখা>'",
        "",
        ee_engine_footer(),
    ]
    return "\n".join(lines)


# =====================================================================
#  Overview — ইঞ্জিন অবস্থা
# =====================================================================

def ee_engine_status_text(bank=None, wrong=None, progress=None,
                          data_dir=None):
    """সব engine item-এর এক-লাইনের অবস্থা: কী লাগবে / কী তৈরি।
    কোনো সংখ্যা বানানো হয় না — অবস্থা শুধু নিজের ফাইলে কী আছে
    তার ওপর ভিত্তি করে।"""
    wrong_r = ee_resolve_wrong(wrong)
    planb = ee_planb_load(data_dir)
    proto = ee_proto_load(data_dir)
    status = {
        "754": "কী লাগবে: কোনো বোর্ড/পদের বিগত প্রশ্নপত্র; ইঞ্জিন তৈরি",
        "757": "কী লাগবে: বিগত প্রশ্নের করপাস; সাধারণ preview তৈরি",
        "760": ("কী তৈরি: নিজের ভুলের খাতা থেকে আভাস-বিশ্লেষণ চালু"
                if wrong_r else
                "কী লাগবে: ভুলের খাতায় ভুল জমা; আভাস-ইঞ্জিন তৈরি"),
        "761": "কী লাগবে: কাট-অফের তথ্য ও লক্ষ্য নম্বর; নিজস্ব সংখ্যা তৈরি",
        "762": "কী লাগবে: টপিকভিত্তিক ওজন; নিজের ভুলের হিসাব তৈরি",
        "768": ("কী তৈরি: প্ল্যান বি সেভ আছে"
                if planb.get("text") else
                "কী তৈরি: storage ও কাঠামো তৈরি, প্ল্যান লেখা বাকি"),
        "771": ("কী তৈরি: প্রোটোকল সেভ আছে"
                if (proto.get(EE_PROTO_KEY_RESULT_DAY) or {}).get("text")
                else "কী লাগবে: ফলাফলের তারিখ/তথ্য; কাঠামো তৈরি"),
        "776": "কী লাগবে: ভাইভা অভিজ্ঞতা/বোর্ডের তথ্য; সাধারণ preview তৈরি",
        "778": ("কী তৈরি: মানসিকতা রুটিন সেভ আছে"
                if (proto.get(EE_PROTO_KEY_MENTALITY) or {}).get("text")
                else "কী তৈরি: রুটিনের কাঠামো তৈরি, পূরণ বাকি"),
        "779": "কী লাগবে: নিজের চাপের রেকর্ড; #759 pressure sim-এর নির্দেশ তৈরি",
        "780": ("কী তৈরি: অপেক্ষার ছক সেভ আছে"
                if (proto.get(EE_PROTO_KEY_WAITING) or {}).get("text")
                else "কী তৈরি: অপেক্ষার ছকের কাঠামো তৈরি, পূরণ বাকি"),
    }
    lines = ["🔧 ইঞ্জিন অবস্থা — এলিট ইঞ্জিন প্যাক",
             "(কোনটা তৈরি, কোনটার জন্য কী তথ্য লাগবে — এক লাইনে)"]
    for no, title in EE_ITEMS:
        lines.append(f"• #{ee_bn(no)} {title} — {status[no]}")
    lines.append("")
    lines.append(ee_engine_footer())
    return "\n".join(lines)


# =====================================================================
#  Routing — ee_engine_handle(text, low)
# =====================================================================
# Routing choices (documented in INTEGRATION-ENGINE.md too):
#  * Save-commands (colon form) are checked BEFORE show-panels, so
#    "প্ল্যান বি: ..." never falls into the show panel.
#  * #776 "বোর্ডের ভাষা" is checked BEFORE #757 "ভাষা বিশ্লেষণ",
#    so the board phrase can never be stolen by the language panel.
#  * #760 guard: bare "মূল কারণ" alone does NOT route (it would
#    steal unrelated chat like "এই ঘটনার মূল কারণ কী"). It routes
#    only with a study-context word (ভুল/পড়া/দুর্বলতা) in the same
#    message, OR the exact phrase "মূল কারণ বিশ্লেষণ". The English-
#    style phrase "রুট কজ" routes on its own — it is a technical
#    term that does not occur in unrelated chat.
#  * Study pack's "ভুল বিশ্লেষণ" is NOT a trigger here (distinct
#    phrase, belongs to study_pack_handle) — no stealing.
#  * "ROI" is matched as a whole word on `low`, so words containing
#    "roi" (e.g. "android") never trigger #762.
#  * #779 deliberately does NOT trigger on bare "চাপ" (pressure sim
#    in the training pack owns that) — only on "শীতলতা".

_EE_PLANB_SAVE_RE = re.compile(r"প্ল্যান\s*বি\s*[:：]\s*(.+)$", re.S)
_EE_MENTALITY_SAVE_RE = re.compile(r"মানসিকতা\s*রুটিন\s*[:：]\s*(.+)$", re.S)
_EE_RESULT_SAVE_RE = re.compile(
    r"(?:ফলদিবস\s*প্রোটোকল|ফল-দিবস\s*প্রোটোকল|ফলের\s*দিনের\s*প্রোটোকল)"
    r"\s*[:：]\s*(.+)$", re.S)
_EE_WAITING_SAVE_RE = re.compile(r"অপেক্ষা\s*ছক\s*[:：]\s*(.+)$", re.S)
_EE_ROOTCAUSE_CONTEXT = ("ভুল", "পড়া", "দুর্বলতা")


def ee_engine_handle(text, low=None, bank=None, wrong=None, progress=None,
                     data_dir=None):
    """Trigger মিললে সংশ্লিষ্ট panel/save-reply, না মিললে None।
    low: host-এর lowercase রূপ (না দিলে text থেকেই বানানো হয়)।"""
    text = str(text or "").strip()
    if not text:
        return None
    low = str(low if low is not None else text).lower()

    # --- save commands first (colon form)
    m = _EE_PLANB_SAVE_RE.search(text)
    if m and m.group(1).strip():
        return ee_planb_save(m.group(1), data_dir=data_dir)
    m = _EE_MENTALITY_SAVE_RE.search(text)
    if m and m.group(1).strip():
        return ee_proto_save_reply("মানসিকতা রুটিন",
                                   EE_PROTO_KEY_MENTALITY,
                                   m.group(1), data_dir=data_dir)
    m = _EE_RESULT_SAVE_RE.search(text)
    if m and m.group(1).strip():
        return ee_proto_save_reply("ফলদিবস প্রোটোকল",
                                   EE_PROTO_KEY_RESULT_DAY,
                                   m.group(1), data_dir=data_dir)
    m = _EE_WAITING_SAVE_RE.search(text)
    if m and m.group(1).strip():
        return ee_proto_save_reply("অপেক্ষা ছক",
                                   EE_PROTO_KEY_WAITING,
                                   m.group(1), data_dir=data_dir)

    # --- overview
    if "ইঞ্জিন অবস্থা" in text:
        return ee_engine_status_text(bank=bank, wrong=wrong,
                                     progress=progress, data_dir=data_dir)

    # --- #768 plan B show ("প্ল্যান বি দেখাও" / bare "প্ল্যান বি")
    if "প্ল্যান বি" in text:
        return ee_panel_768(data_dir=data_dir)

    # --- #776 before #757 (board phrase must not be stolen)
    if "বোর্ডের ভাষা" in text:
        return ee_panel_776()

    # --- #754
    if "প্রশ্নকর্তা" in text:
        return ee_panel_754(bank=bank)

    # --- #757
    if "ভাষা বিশ্লেষণ" in text or "প্রশ্নের ভাষা" in text:
        return ee_panel_757()

    # --- #760 root cause (guarded, see routing notes above)
    if ("মূল কারণ বিশ্লেষণ" in text or "রুট কজ" in text
            or ("মূল কারণ" in text
                and any(w in text for w in _EE_ROOTCAUSE_CONTEXT))
            or "দুর্বলতার মূল" in text):
        return ee_rootcause_text(wrong=wrong, progress=progress)

    # --- #761
    if ("নম্বর ফাঁক" in text or "নম্বর-ফাঁক" in text
            or "কাট অফ" in text or "কাট-অফ" in text
            or "কাটঅফ" in text):
        return ee_panel_761(wrong=wrong, progress=progress)

    # --- #762
    if ("অধ্যায়ের মূল্য" in text or "অধ্যায়-মূল্য" in text
            or "অধ্যায় মূল্য" in text or re.search(r"\broi\b", low)):
        return ee_panel_762(wrong=wrong)

    # --- #771 result day
    if ("ফলের দিন" in text or "ফল-দিবস" in text or "ফল দিবস" in text
            or "ফলদিবস" in text):
        return ee_panel_771(data_dir=data_dir)

    # --- #778 mentality (show; save handled above)
    if "মানসিকতা" in text:
        return ee_panel_778(data_dir=data_dir)

    # --- #779 calm under pressure (never bare "চাপ")
    if "শীতলতা" in text:
        return ee_panel_779()

    # --- #780 waiting management
    if ("অপেক্ষা ব্যবস্থাপনা" in text or "দীর্ঘ অপেক্ষা" in text
            or "অপেক্ষা ছক" in text):
        return ee_panel_780(data_dir=data_dir)

    return None


# -*- coding: utf-8 -*-
"""
study_sweep_pack.py — Desktop Sokhi v1.9.0: Study FOUNDATION Sweep Pack
=========================================================================
Self-contained snippet for integration into sokhi.py. Coordinator:
paste this whole file at top level in sokhi.py AFTER the v1.5 study
pack (i.e. after `study_pack_handle`) and wire the dispatch block
described in INTEGRATION-SWEEP.md. Do NOT edit sokhi.py from here.

Features (সবই শুধু নিজের আসল ডেটা থেকে — কিছু বানানো হয় না):
  #667 es_revision_due_text()   ভুলে-যাওয়ার বক্র — পুনরাবৃত্তি সূচি
  #703 es_pocket_summary_text() পকেট সার (এক-পাতা সার)
  #716 es_confusion_pairs_text() বিভ্রান্তিকর জোড়া সতর্কতা
  #729 es_dual_start() /
       es_sweep_handle()        দ্বৈত মূল্যায়ন (দুই-ধাপ সেশন)
  #753 es_courage_text()        হলের দরজায় সাহস-বার্তা
  es_handle(text, low)          ঐচ্ছিক ডিসপ্যাচ হেল্পার

House rules honoured (v1.5 study pack conventions mirrored):
  * 100% free, offline-only — reads ONLY OFFLINE_BANK, OFFLINE_LESSONS,
    study-progress.json, study-wrong-book.json, wins.json. No web/Gemini.
  * Host globals are looked up via globals().get(...) AT CALL TIME, so
    the pack works pasted into sokhi.py (host globals win) and tests
    can stub module attributes or inject data via parameters.
  * Every public function accepts injected data (bank=, lessons=,
    progress=, wrong=, wins=, ...) — production passes nothing.
  * Bangla digits via a LOCAL es_bn() helper (mirror of host _bn_num);
    _bn / _NO_DATA aliases kept for v1.5-pack style compatibility.
  * All pack symbols are prefixed es_ / ES_.

Verified data shapes:
  OFFLINE_BANK    = {subject: [{q, options[4], answer int, topic}]}
  OFFLINE_LESSONS = {subject: [{topic, text, check_q,
                                check_answers[], alt}]}
  study-progress.json  = {subject: {sessions, mock_tests, total_steps,
                                    weak[], last_topic, last_date}}
  study-wrong-book.json = [{q, options, correct (TEXT),
                            your_answer (TEXT), subject, topic, date}]
  wins.json = [{id, text, date, ts}]

New file introduced by #729 (the ONLY write in this pack):
  DATA / "elite-sweep-session.json" — dual-evaluation session /
  last dual result. See INTEGRATION-SWEEP.md.
"""

import json
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

# ------------------------------------------------------------------ digits

ES_BN_DIGITS_MAP = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
ES_EN_DIGITS_MAP = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")


def es_bn(x):
    """Local mirror of host _bn_num(): English digits -> Bangla digits."""
    return str(x).translate(ES_BN_DIGITS_MAP)


def es_en_digits(s):
    """বাংলা সংখ্যা -> ইংরেজি সংখ্যা (পার্স করার জন্য)।"""
    return str(s or "").translate(ES_EN_DIGITS_MAP)


# v1.5-pack style aliases (the study pack used these exact names).
_bn = es_bn
ES_NO_DATA = "এখনো ডেটা নেই"
_NO_DATA = ES_NO_DATA

ES_OPT_LETTERS = ["ক", "খ", "গ", "ঘ"]

# #667: ভুলের সংখ্যা -> পরের রিভিশনের ব্যবধান (দিন)
ES_REVISION_LADDER = [1, 3, 7, 15]

ES_SESSION_FILENAME = "elite-sweep-session.json"

# ------------------------------------------------------- global fallbacks
# These helpers deliberately look names up in globals() at CALL time, so
# (a) the pack works when pasted into sokhi.py (host globals win), and
# (b) tests can stub study_sweep_pack.OFFLINE_BANK etc. or pass data
# directly.


def es_data_dir():
    """Host DATA (pathlib.Path) via globals; fallback Path('data')."""
    g = globals().get("DATA")
    if g is not None:
        try:
            return Path(g)
        except Exception:
            pass
    return Path("data")


def es_load_json(path, default):
    """Host load_json(path, default) থাকলে সেটা, নইলে local json read."""
    fn = globals().get("load_json")
    if callable(fn):
        try:
            return fn(path, default)
        except Exception:
            return default
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def es_save_json(path, obj):
    """Host save_json(path, obj) থাকলে সেটা, নইলে local json write."""
    fn = globals().get("save_json")
    if callable(fn):
        try:
            fn(path, obj)
            return True
        except Exception:
            pass
    try:
        p = Path(path)
        if p.parent and str(p.parent) not in ("", "."):
            p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj, ensure_ascii=False, indent=2),
                     encoding="utf-8")
        return True
    except Exception:
        return False


def es_resolve_bank(bank=None):
    if bank is not None:
        return bank if isinstance(bank, dict) else {}
    g = globals().get("OFFLINE_BANK")
    return g if isinstance(g, dict) else {}


def es_resolve_lessons(lessons=None):
    if lessons is not None:
        return lessons if isinstance(lessons, dict) else {}
    g = globals().get("OFFLINE_LESSONS")
    return g if isinstance(g, dict) else {}


def es_resolve_progress(progress=None):
    if progress is not None:
        return progress if isinstance(progress, dict) else {}
    path = globals().get("_STUDY_PROGRESS_FILE")
    if path is None:
        path = es_data_dir() / "study-progress.json"
    data = es_load_json(path, {})
    return data if isinstance(data, dict) else {}


def es_resolve_wrong(wrong=None):
    if wrong is not None:
        return wrong if isinstance(wrong, list) else []
    path = globals().get("_WRONG_BOOK_FILE")
    if path is None:
        path = es_data_dir() / "study-wrong-book.json"
    data = es_load_json(path, [])
    return data if isinstance(data, list) else []


def es_resolve_wins(wins=None):
    if wins is not None:
        return wins if isinstance(wins, list) else []
    data = es_load_json(es_data_dir() / "wins.json", [])
    return data if isinstance(data, list) else []


def es_resolve_first_day(first_day=None):
    """first_day প্যারামিটার > host get_memory()['first_day'] > None."""
    if first_day:
        return str(first_day)
    fn = globals().get("get_memory")
    if callable(fn):
        try:
            mem = fn()
            if isinstance(mem, dict) and mem.get("first_day"):
                return str(mem.get("first_day"))
        except Exception:
            pass
    return None


# ------------------------------------------------------------- date utils


def es_parse_date(value):
    """'YYYY-MM-DD' str / date / datetime -> date, না পারলে None।"""
    if value is None:
        return None
    if isinstance(value, date):
        try:
            return value.date()  # datetime হলে শুধু তারিখ অংশ
        except Exception:
            return value
    s = es_en_digits(str(value).strip())[:10]
    try:
        y, m, d = (int(x) for x in s.split("-"))
        return date(y, m, d)
    except Exception:
        return None


def es_fmt_date(d):
    """date -> বাংলা সংখ্যায় 'YYYY-MM-DD'।"""
    return es_bn(str(d)) if d else "—"


def es_coerce_today(today=None):
    if today is None:
        return date.today()
    parsed = es_parse_date(today)
    return parsed if parsed is not None else date.today()


# =====================================================================
#  #667 ভুলে-যাওয়ার বক্র — পুনরাবৃত্তি সূচি
# =====================================================================


def es_revision_interval(wrong_count):
    """ভুলের সংখ্যা n -> রিভিশন ব্যবধান (দিন): ladder [1, 3, 7, 15],
    index = min(n-1, 3)। n=1→১ দিন, n=2→৩ দিন, n=3→৭ দিন, n>=4→১৫ দিন।"""
    try:
        n = int(wrong_count)
    except Exception:
        n = 1
    if n < 1:
        n = 1
    return ES_REVISION_LADDER[min(n - 1, len(ES_REVISION_LADDER) - 1)]


def es_revision_schedule(wrong=None):
    """Wrong-book থেকে টপিকভিত্তিক সূচি:
    [{subject, topic, count, last_date (date), interval, due (date)}]।
    তারিখ পড়া যায় না এমন এন্ট্রি বাদ (সূচি বানানো যায় না)।"""
    wrong = es_resolve_wrong(wrong)
    agg = {}
    for w in wrong or []:
        if not isinstance(w, dict):
            continue
        d = es_parse_date(w.get("date"))
        if d is None:
            continue
        key = (str(w.get("subject") or "অজানা বিষয়"),
               str(w.get("topic") or "সাধারণ"))
        ent = agg.get(key)
        if ent is None:
            ent = {"subject": key[0], "topic": key[1], "count": 0,
                   "last_date": d}
            agg[key] = ent
        ent["count"] += 1
        if d > ent["last_date"]:
            ent["last_date"] = d
    out = []
    for ent in agg.values():
        interval = es_revision_interval(ent["count"])
        ent = dict(ent)
        ent["interval"] = interval
        ent["due"] = ent["last_date"] + timedelta(days=interval)
        out.append(ent)
    return out


def es_revision_due_text(wrong=None, today=None):
    """ভুলে-যাওয়ার বক্র অনুযায়ী টপিকভিত্তিক রিভিশন সূচি:
    মেয়াদ-পেরোনো আগে (দেরি বেশি যার, সে আগে), তারপর আজকের, তারপর
    আগামী ৩ দিনের। সবই ভুলের খাতার আসল তারিখ/গণনা থেকে।"""
    wrong = es_resolve_wrong(wrong)
    today_d = es_coerce_today(today)
    schedule = es_revision_schedule(wrong=wrong)
    if not schedule:
        return (f"{ES_NO_DATA} — ভুলের খাতা খালি, তাই পুনরাবৃত্তি সূচি "
                "বানানোর কিছু নেই। মক টেস্টে ভুল জমলেই প্রতিটা টপিকের "
                "রিভিশনের তারিখ এখানে সাজিয়ে দেব।")

    overdue, due_today, upcoming, later = [], [], [], []
    for ent in schedule:
        delta = (ent["due"] - today_d).days
        if delta < 0:
            overdue.append((ent, -delta))
        elif delta == 0:
            due_today.append(ent)
        elif delta <= 3:
            upcoming.append(ent)
        else:
            later.append(ent)
    overdue.sort(key=lambda x: (-x[1], -x[0]["count"], x[0]["topic"]))
    due_today.sort(key=lambda e: (-e["count"], e["topic"]))
    upcoming.sort(key=lambda e: (e["due"], -e["count"], e["topic"]))

    lines = ["🧠 ভুলে-যাওয়ার বক্র — পুনরাবৃত্তি সূচি",
             "নিয়ম: ১ বার ভুল → পরের দিন, ২ বার → ৩ দিন পর, "
             "৩ বার → ৭ দিন পর, ৪ বার বা বেশি → ১৫ দিন পর আবার ঝালাই।"]

    def _row(ent):
        return (f"• {ent['subject']} / {ent['topic']} — "
                f"{es_bn(ent['count'])}বার ভুল, শেষ ভুল "
                f"{es_fmt_date(ent['last_date'])}, "
                f"রিভিশন {es_fmt_date(ent['due'])}")

    if overdue:
        lines.append("")
        lines.append("🔴 মেয়াদ পেরিয়েছে (আগে এগুলো ধরো):")
        for ent, late in overdue:
            lines.append(_row(ent) + f" — {es_bn(late)} দিন দেরি")
    if due_today:
        lines.append("")
        lines.append("🟡 আজই রিভিশন দেওয়ার কথা:")
        for ent in due_today:
            lines.append(_row(ent))
    if upcoming:
        lines.append("")
        lines.append("🟢 আগামী ৩ দিনে আসছে:")
        for ent in upcoming:
            lines.append(_row(ent))
    if later:
        lines.append("")
        lines.append(f"আরও {es_bn(len(later))}টি টপিকের রিভিশন "
                     "৩ দিনের পরে আসছে — সময় হলে আবার দেখে নিও।")
    if not overdue and not due_today and not upcoming:
        lines.append("")
        lines.append("আপাতত মেয়াদ-পেরোনো বা কাছাকাছি কোনো রিভিশন নেই — "
                     "ভালো চলছে!")
    return "\n".join(lines)


# =====================================================================
#  #703 পকেট সার (শেষ মুহূর্তের এক-পাতা সার)
# =====================================================================


def es_pocket_summary_text(progress=None, wrong=None, lessons=None):
    """এক-পাতা সার: দুর্বল টপিক (শীর্ষ ৫), বিষয়ভিত্তিক শেষ টপিক+সেশন,
    এখনো ছোঁয়া-হয়নি পাঠের টপিক, আর ডেটা থেকেই বানানো আজকের ৩ করণীয়।
    প্রতিটা অংশে আলাদা empty state — ডেটা না থাকলে কিছু বানানো হয় না।"""
    progress = es_resolve_progress(progress)
    wrong = es_resolve_wrong(wrong)
    lessons = es_resolve_lessons(lessons)

    lines = ["📌 পকেট সার — পরীক্ষার আগের সকালে চোখ বুলানোর জন্য"]

    # --- দুর্বল টপিক (শীর্ষ ৫, ভুলের গণনা ধরে)
    pair_counts = Counter()
    for w in wrong or []:
        if isinstance(w, dict):
            pair_counts[(str(w.get("subject") or "অজানা বিষয়"),
                         str(w.get("topic") or "সাধারণ"))] += 1
    lines.append("")
    lines.append("দুর্বল টপিক (বেশি ভুল যেখানে):")
    if pair_counts:
        for (subj, topic), cnt in pair_counts.most_common(5):
            lines.append(f"• {subj} / {topic} — {es_bn(cnt)}বার ভুল")
    else:
        lines.append(f"• {ES_NO_DATA} — ভুলের খাতায় এখনো কিছু জমেনি।")

    # --- বিষয়ভিত্তিক অবস্থা
    lines.append("")
    lines.append("বিষয়ভিত্তিক অবস্থা:")
    if progress:
        for subj in sorted(progress.keys()):
            ent = progress.get(subj) or {}
            if not isinstance(ent, dict):
                ent = {}
            sessions = int(ent.get("sessions", 0) or 0)
            mocks = int(ent.get("mock_tests", 0) or 0)
            last_topic = str(ent.get("last_topic") or "").strip() or "—"
            lines.append(f"• {subj}: শেষ টপিক {last_topic}, "
                         f"সেশন {es_bn(sessions)}টি, "
                         f"মক টেস্ট {es_bn(mocks)}টি")
    else:
        lines.append(f"• {ES_NO_DATA} — পড়ার রেকর্ড এখনো তৈরি হয়নি।")

    # --- বাকি বড় টপিক: পাঠের টপিক যা progress weak/last-এ নেই,
    #     ভুলের খাতাতেও নেই (মানে কোনো রেকর্ডেই ছোঁয়া হয়নি)
    wrong_topics = {}
    for w in wrong or []:
        if isinstance(w, dict):
            wrong_topics.setdefault(
                str(w.get("subject") or ""), set()).add(
                    str(w.get("topic") or ""))
    uncovered = []
    for subj in sorted(lessons.keys()):
        ent = progress.get(subj) or {}
        if not isinstance(ent, dict):
            ent = {}
        touched = set(str(x) for x in (ent.get("weak", []) or []))
        lt = str(ent.get("last_topic") or "").strip()
        if lt:
            touched.add(lt)
        touched |= wrong_topics.get(subj, set())
        for step in lessons.get(subj) or []:
            if isinstance(step, dict):
                t = str(step.get("topic") or "").strip()
                if t and t not in touched:
                    uncovered.append((subj, t))
    lines.append("")
    lines.append("এখনো ছোঁয়া হয়নি এমন পাঠের টপিক:")
    if uncovered:
        for subj, t in uncovered[:10]:
            lines.append(f"• {subj} / {t}")
        if len(uncovered) > 10:
            lines.append(f"• …আরও {es_bn(len(uncovered) - 10)}টি")
    else:
        lines.append("• ছোঁয়া-হয়নি এমন টপিকের রেকর্ড নেই — "
                     "হয় সব ছোঁয়া হয়েছে, নয়তো পাঠের তালিকা খালি।")

    # --- আজকের জন্য ৩টি করণীয় (শুধু ডেটা থেকে)
    todos = []
    if pair_counts:
        (subj, topic), cnt = pair_counts.most_common(1)[0]
        todos.append(f"সবচেয়ে বেশি ভুলের টপিকটা আগে ঝালাও: "
                     f"{subj} / {topic} ({es_bn(cnt)}বার ভুল)।")
    if uncovered:
        subj, t = uncovered[0]
        todos.append(f"ছোঁয়া-হয়নি এমন একটা নতুন টপিক ধরো: {subj} / {t}।")
    total_mocks = 0
    least = None  # (sessions+mocks, subject)
    for subj, ent in (progress or {}).items():
        if not isinstance(ent, dict):
            continue
        act = int(ent.get("sessions", 0) or 0) + \
            int(ent.get("mock_tests", 0) or 0)
        total_mocks += int(ent.get("mock_tests", 0) or 0)
        if least is None or act < least[0]:
            least = (act, subj)
    if total_mocks == 0 and progress:
        todos.append("আজ অন্তত একটা মক টেস্ট দাও — ভুলের খাতায় যা জমবে, "
                     "কালকের পড়া সেখান থেকেই সাজাব।")
    elif least is not None:
        todos.append(f"সবচেয়ে কম পড়া বিষয়টা একবার দেখো: {least[1]} "
                     f"(মোট সেশন+টেস্ট {es_bn(least[0])}টি)।")
    lines.append("")
    lines.append("আজকের জন্য:")
    if todos:
        marks = ["১", "২", "৩"]
        for i, todo in enumerate(todos[:3]):
            lines.append(f"{marks[i]}. {todo}")
    else:
        lines.append("• পড়া শুরু করলেই এখানে আজকের করণীয় সাজিয়ে দেব।")
    return "\n".join(lines)


# =====================================================================
#  #716 বিভ্রান্তিকর জোড়া সতর্কতা
# =====================================================================


def es_confusion_pairs_text(wrong=None):
    """একই বিষয়ের দুটি আলাদা টপিক একই তারিখে (একই বসায়) ভুল হলে
    সেগুলোকে 'একসাথে গুলিয়ে ফেলার ঝোঁক' জোড়া হিসেবে দেখায়; পাশাপাশি
    ৩+ বার ভুল হওয়া টপিকগুলোকে 'বারবার ভুলের টপিক' হিসেবে চিহ্নিত করে।"""
    wrong = es_resolve_wrong(wrong)
    valid = [w for w in (wrong or []) if isinstance(w, dict)]
    if not valid:
        return (f"{ES_NO_DATA} — ভুলের খাতা খালি। মক টেস্টে ভুল জমলেই "
                "কোন টপিকগুলো একসাথে গুলিয়ে ফেলছ, এখানে ধরা পড়বে।")

    # (date, subject) -> topics set;  pair -> {count, dates}
    by_sitting = {}
    topic_counts = Counter()
    for w in valid:
        subj = str(w.get("subject") or "অজানা বিষয়")
        topic = str(w.get("topic") or "সাধারণ")
        topic_counts[(subj, topic)] += 1
        d = str(w.get("date") or "").strip()
        if d:
            by_sitting.setdefault((d, subj), set()).add(topic)

    pair_info = {}
    for (d, subj), topics in by_sitting.items():
        ordered = sorted(topics)
        for i in range(len(ordered)):
            for j in range(i + 1, len(ordered)):
                key = (subj, ordered[i], ordered[j])
                info = pair_info.setdefault(key, {"count": 0, "dates": []})
                info["count"] += 1
                if d not in info["dates"]:
                    info["dates"].append(d)

    repeats = [(k, c) for k, c in topic_counts.most_common() if c >= 3]

    if not pair_info and not repeats:
        return ("🔀 বিভ্রান্তিকর জোড়া সতর্কতা\n"
                f"ভুলের খাতায় মোট {es_bn(len(valid))}টি ভুল আছে, কিন্তু "
                "একই দিনে একই বিষয়ের দুটো টপিক একসাথে ভুল হওয়ার মতো "
                "জোড়া, কিংবা ৩ বার বা বেশি ভুল হওয়া কোনো টপিক — "
                "এখনো কোনোটাই ধরা পড়েনি। আরও মক টেস্ট দিলে ছবিটা "
                "পরিষ্কার হবে।")

    lines = ["🔀 বিভ্রান্তিকর জোড়া সতর্কতা"]
    if pair_info:
        lines.append("")
        lines.append("একসাথে গুলিয়ে ফেলার ঝোঁক আছে যেসব জোড়ায় "
                     "(একই দিনে, একই বিষয়ে দুটো টপিকেই ভুল):")
        ranked = sorted(pair_info.items(),
                        key=lambda kv: (-kv[1]["count"], kv[0]))
        for (subj, t1, t2), info in ranked:
            dates = ", ".join(es_bn(d) for d in sorted(info["dates"]))
            lines.append(f"• {subj}: {t1} × {t2} — "
                         f"{es_bn(info['count'])}বার একসাথে ভুল "
                         f"(তারিখ: {dates})")
        lines.append("পরামর্শ: এই জোড়া দুটো পাশাপাশি রেখে পার্থক্যটা "
                     "একবার পড়ে নাও — গুলিয়ে ফেলা কমে যাবে।")
    if repeats:
        lines.append("")
        lines.append("বারবার ভুলের টপিক (৩ বার বা বেশি):")
        for (subj, topic), cnt in repeats:
            lines.append(f"• {subj} / {topic} — {es_bn(cnt)}বার ভুল")
    lines.append("")
    lines.append(f"হিসাবটা ভুলের খাতার মোট {es_bn(len(valid))}টি "
                 "এন্ট্রি গুনে করা।")
    return "\n".join(lines)


# =====================================================================
#  #729 দ্বৈত মূল্যায়ন (দুই-ধাপ) — সেশন মেশিন
#  ফাইল: DATA / "elite-sweep-session.json"
#  সক্রিয় সেশন: {"stage": "await_reveal"|"await_grade", "subject",
#                 "questions": [{q, options, answer, topic}],
#                 "date", "phase1": None|int}
#  শেষ হলে ফাইলে শুধু শেষ ফল: {"subject", "phase1", "date"}
# =====================================================================


def es_session_file():
    return es_data_dir() / ES_SESSION_FILENAME


def es_load_session():
    data = es_load_json(es_session_file(), None)
    return data if isinstance(data, dict) else None


def es_save_session(st):
    try:
        d = es_data_dir()
        d.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return es_save_json(es_session_file(), st)


def es_clear_session():
    try:
        es_session_file().unlink(missing_ok=True)
    except Exception:
        pass


def es_dual_active():
    st = es_load_session()
    return bool(st and st.get("stage") in ("await_reveal", "await_grade")
                and st.get("questions"))


def es_dual_last():
    """শেষ সম্পন্ন দ্বৈত মূল্যায়নের ফল {subject, phase1, date} বা None।"""
    st = es_load_session()
    if st and not st.get("stage") and "phase1" in st:
        return st
    return None


def es_subject_in_text(text, bank=None, lessons=None):
    bank = es_resolve_bank(bank)
    lessons = es_resolve_lessons(lessons)
    raw = str(text or "")
    for subj in list(bank.keys()) + [s for s in lessons.keys()
                                     if s not in bank]:
        if subj and subj in raw:
            return subj
    fn = globals().get("_detect_subject")
    if callable(fn):
        try:
            return fn(raw)
        except Exception:
            return None
    return None


def es_dual_pick_questions(subject, bank=None, today=None):
    """বিষয়ের ব্যাংক-প্রশ্ন থেকে সর্বোচ্চ ৫টি; তারিখ ধরে rotate করা,
    যাতে প্রতিদিন ভিন্ন সেট আসে। ৪-অপশন + int answer-ওয়ালা প্রশ্নই নেয়।"""
    bank = es_resolve_bank(bank)
    qs = [q for q in (bank.get(subject) or [])
          if isinstance(q, dict)
          and isinstance(q.get("options"), list)
          and len(q.get("options") or []) == 4
          and isinstance(q.get("answer"), int)
          and str(q.get("q") or "").strip()]
    if len(qs) < 3:
        return []
    today_d = es_coerce_today(today)
    offset = today_d.toordinal() % len(qs)
    rotated = qs[offset:] + qs[:offset]
    return [{"q": str(q.get("q") or ""), "options": list(q["options"]),
             "answer": int(q["answer"]),
             "topic": str(q.get("topic") or "সাধারণ")}
            for q in rotated[:5]]


def es_dual_format_questions(st):
    lines = []
    for i, q in enumerate(st.get("questions") or [], 1):
        lines.append("")
        lines.append(f"প্রশ্ন {es_bn(i)}: {q['q']}")
        for j, op in enumerate(q.get("options") or []):
            if j < len(ES_OPT_LETTERS):
                lines.append(f"{ES_OPT_LETTERS[j]}) {op}")
    return "\n".join(lines)


def es_dual_start(subject, bank=None, today=None):
    """Phase 1 শুরু: সময় ছাড়া ৫টি প্রশ্ন, উত্তর লুকানো।
    ব্যাংকে ৩টির কম ব্যবহারযোগ্য প্রশ্ন থাকলে সৎ বার্তা (সেশন খোলে না)।"""
    subject = str(subject or "").strip()
    if not subject:
        return ("কোন বিষয়ের দ্বৈত মূল্যায়ন দেবে? বিষয়ের নামসহ বলো — "
                "যেমন: 'দ্বৈত মূল্যায়ন গণিত'।")
    bank = es_resolve_bank(bank)
    raw_n = len([q for q in (bank.get(subject) or [])
                 if isinstance(q, dict)])
    qs = es_dual_pick_questions(subject, bank=bank, today=today)
    if not qs:
        if raw_n == 0:
            return (f"{ES_NO_DATA} — '{subject}' বিষয়ের কোনো প্রশ্ন "
                    "অফলাইন ব্যাংকে পাইনি, তাই দ্বৈত মূল্যায়ন শুরু করা "
                    "যাচ্ছে না।")
        return (f"'{subject}' বিষয়ে ব্যবহারযোগ্য প্রশ্ন মাত্র "
                f"{es_bn(raw_n)}টি আছে — দ্বৈত মূল্যায়নের জন্য কমপক্ষে "
                "৩টি লাগে। আরো প্রশ্ন জমলে আবার চেষ্টা করো।")
    today_d = es_coerce_today(today)
    st = {"stage": "await_reveal", "subject": subject, "questions": qs,
          "date": str(today_d), "phase1": None}
    es_save_session(st)
    lines = [f"⚖️ দ্বৈত মূল্যায়ন — {subject} (ধাপ ১: সময় ছাড়া)",
             f"মোট {es_bn(len(qs))}টি প্রশ্ন। ঘড়ির দিকে তাকিও না — "
             "ধীরে ভেবে নিজে নিজে উত্তরগুলো মনে মনে ঠিক করো। "
             "উত্তর এখন দেখাব না।"]
    lines.append(es_dual_format_questions(st))
    lines.append("")
    lines.append("হয়ে গেলে লিখো: 'উত্তর দেখাও' — তখন উত্তর মিলিয়ে "
                 "নিজেই নম্বর দেবে। থামাতে লিখো: 'থামাও'।")
    return "\n".join(lines)


def es_dual_reveal(st):
    """উত্তর প্রকাশ + নিজে-গ্রেড করার অনুরোধ; stage -> await_grade।"""
    lines = [f"⚖️ দ্বৈত মূল্যায়ন — {st.get('subject', '')} : উত্তর"]
    for i, q in enumerate(st.get("questions") or [], 1):
        ans = int(q.get("answer", 0) or 0)
        opts = q.get("options") or []
        letter = ES_OPT_LETTERS[ans] if 0 <= ans < len(ES_OPT_LETTERS) \
            else es_bn(ans + 1)
        atext = opts[ans] if 0 <= ans < len(opts) else ""
        lines.append(f"প্রশ্ন {es_bn(i)}: সঠিক উত্তর {letter}) {atext}")
    total = len(st.get("questions") or [])
    lines.append("")
    lines.append(f"এবার সত্যি করে নিজে হিসাব করো — {es_bn(total)}টির "
                 "মধ্যে কয়টা ঠিক হলো লিখো (যেমন ৩)।")
    st["stage"] = "await_grade"
    es_save_session(st)
    return "\n".join(lines)


def es_parse_grade(text, total):
    """লেখা থেকে গ্রেড সংখ্যা (বাংলা/ইংরেজি সংখ্যা) বের করে;
    0..total-এর মধ্যে না হলে None।"""
    m = re.search(r"\d+", es_en_digits(str(text or "")))
    if not m:
        return None
    try:
        n = int(m.group(0))
    except Exception:
        return None
    if 0 <= n <= int(total):
        return n
    return None


def es_dual_grade(text, st):
    """Phase 1 স্কোর রেকর্ড করে, ফাইলে শেষ ফল রাখে, Phase 2 নির্দেশ দেয়।"""
    total = len(st.get("questions") or [])
    score = es_parse_grade(text, total)
    if score is None:
        return (f"স্কোরটা সংখ্যায় লিখো — ০ থেকে {es_bn(total)}-এর মধ্যে "
                "কয়টা ঠিক হলো (যেমন ৩)।")
    result = {"subject": st.get("subject", ""), "phase1": score,
              "date": str(date.today())}
    es_save_session(result)
    lines = [f"✅ ধাপ ১ শেষ! সময় ছাড়া পেয়েছ {es_bn(score)}/"
             f"{es_bn(total)} — নোট করে রাখলাম।",
             "",
             "এবার ধাপ ২: সময় ধরে একই বিষয়ের মক টেস্ট দাও — "
             "'মক টেস্ট' লিখলেই শুরু হবে।",
             f"তুলনা: ধাপ ১-এ (চাপ ছাড়া) তোমার স্কোর "
             f"{es_bn(score)}/{es_bn(total)}। ধাপ ২-তে সময়ের চাপে কত "
             "পাও, মিলিয়ে দেখলেই বুঝবে — জ্ঞান কম, নাকি সময়ের চাপেই "
             "নম্বর কমে।"]
    return "\n".join(lines)


def es_sweep_handle(text, low=None):
    """#729 সেশন রাউটার (mastery pattern-এর মতো): সক্রিয় দ্বৈত
    মূল্যায়ন সেশন থাকলেই শুধু কাজ করে; সেশন-ইনপুট না হলে None,
    যাতে অন্য হ্যান্ডলার চলতে পারে।"""
    text = str(text or "").strip()
    if not text:
        return None
    st = es_load_session()
    if not (st and st.get("stage") in ("await_reveal", "await_grade")
            and st.get("questions")):
        return None
    if "থামাও" in text or "দ্বৈত মূল্যায়ন বন্ধ" in text:
        es_clear_session()
        return ("দ্বৈত মূল্যায়ন থামিয়ে দিলাম। আবার চাইলে বলো: "
                "'দ্বৈত মূল্যায়ন <বিষয়>'।")
    if st.get("stage") == "await_reveal":
        if "উত্তর দেখাও" in text:
            return es_dual_reveal(st)
        return None
    # stage == await_grade
    if re.search(r"\d", es_en_digits(text)):
        return es_dual_grade(text, st)
    return None


# =====================================================================
#  #753 হলের দরজায় সাহস-বার্তা
# =====================================================================


def es_courage_text(wins=None, progress=None, first_day=None, today=None):
    """~১ মিনিটে পড়া যায় এমন শান্ত সাহস-বার্তা — শুধু আসল রেকর্ড
    থেকে: মোট সেশন/মক, প্রস্তুতির দিন, সর্বশেষ জয়, সবচেয়ে বেশি
    পড়া বিষয়। ডেটা না থাকলে সৎ লাইনসহ সাধারণ শান্ত ফ্রেম।"""
    wins = es_resolve_wins(wins)
    progress = es_resolve_progress(progress)
    first_day = es_resolve_first_day(first_day)
    today_d = es_coerce_today(today)

    total_sessions = 0
    total_mocks = 0
    best_subject = None
    best_activity = 0
    for subj, ent in (progress or {}).items():
        if not isinstance(ent, dict):
            continue
        s = int(ent.get("sessions", 0) or 0)
        m = int(ent.get("mock_tests", 0) or 0)
        total_sessions += s
        total_mocks += m
        if s + m > best_activity:
            best_activity = s + m
            best_subject = str(subj)

    days = None
    fd = es_parse_date(first_day)
    if fd is not None:
        days = (today_d - fd).days + 1
        if days < 1:
            days = 1

    latest_win = None
    for w in reversed(wins or []):
        if isinstance(w, dict) and str(w.get("text") or "").strip():
            latest_win = str(w.get("text")).strip()
            break

    has_data = bool(total_sessions or total_mocks or latest_win
                    or best_subject)
    lines = ["🌿 হলের দরজায় দাঁড়িয়ে — এক মিনিট শুনে যাও।",
             "",
             "প্রথমে শ্বাস নাও। লম্বা করে শ্বাস নাও, ধীরে ছাড়ো। "
             "আরেকবার। মাথাটা ঠান্ডা রাখো — তাড়াহুড়োর কিছু নেই।"]
    if has_data:
        lines.append("")
        lines.append("এবার মনে করো, তুমি যা পড়েছ:")
        facts = []
        if days:
            facts.append(f"তুমি প্রস্তুতি নিচ্ছ {es_bn(days)} দিন ধরে")
        if total_sessions or total_mocks:
            facts.append(f"মোট {es_bn(total_sessions)}টি পড়ার সেশন আর "
                         f"{es_bn(total_mocks)}টি মক টেস্ট দিয়েছ")
        if best_subject:
            facts.append(f"সবচেয়ে বেশি পড়েছ {best_subject}")
        if latest_win:
            facts.append(f"তোমার সর্বশেষ জয়: “{latest_win}”")
        for f in facts:
            lines.append(f"• {f}।")
        lines.append("এই পরিশ্রমটা সত্যি — কেউ তোমার কাছ থেকে এটা "
                     "কেড়ে নিতে পারবে না।")
    else:
        lines.append("")
        lines.append("এখনো রেকর্ড কম, তবু তুমি আজ এখানে এসেছ — "
                     "এটাই সবচেয়ে বড় প্রমাণ যে তুমি হাল ছাড়োনি। "
                     "যতটুকু পড়েছ, ঠান্ডা মাথায় ততটুকুই ভালো করে লিখো।")
    lines.append("")
    lines.append("আজ শুধু নিজের সেরা চেষ্টাটা দাও। জানা প্রশ্নটা আগে, "
                 "কঠিনটা পরে। একটা প্রশ্নে আটকে থাকবে না। "
                 "তুমি পারবে — ধীরে, শান্তভাবে, একটা একটা করে। "
                 "আমি আছি তোমার সঙ্গে।")
    return "\n".join(lines)


# =====================================================================
#  ডিসপ্যাচ হেল্পার (ইন্টিগ্রেটর INTEGRATION-SWEEP.md অনুযায়ী বসাবে)
# =====================================================================

ES_TRIGGERS = (
    "রিভিশন কবে", "পুনরাবৃত্তি সূচি", "ভুলে যাওয়ার",
    "পকেট সার",
    "বিভ্রান্তিকর জোড়া", "গুলিয়ে ফেলি",
    "দ্বৈত মূল্যায়ন",
    "সাহস বার্তা", "হলে যাওয়ার আগে", "পরীক্ষার আগে বলো",
)


def es_handle(text, low=None):
    """Trigger মিললে সংশ্লিষ্ট টেক্সট, না মিললে None।
    সক্রিয় দ্বৈত-মূল্যায়ন সেশন থাকলে সেশন-রাউট সবার আগে (session
    precedence) — তবে সেশন-ইনপুট না হলে বাকি trigger-ও চলতে পারে।"""
    text = str(text or "").strip()
    if not text:
        return None
    # #729 session routing — সবার আগে
    if es_dual_active():
        _s = es_sweep_handle(text, low)
        if _s:
            return _s
    if "দ্বৈত মূল্যায়ন" in text:
        subj = es_subject_in_text(text)
        if not subj:
            return ("কোন বিষয়ের দ্বৈত মূল্যায়ন দেবে? বিষয়ের নামসহ "
                    "বলো — যেমন: 'দ্বৈত মূল্যায়ন গণিত'।")
        return es_dual_start(subj)
    if ("রিভিশন কবে" in text or "পুনরাবৃত্তি সূচি" in text
            or "ভুলে যাওয়ার" in text or "রিভিশন সূচি" in text):
        return es_revision_due_text()
    if "পকেট সার" in text:
        return es_pocket_summary_text()
    if ("বিভ্রান্তিকর জোড়া" in text or "বিভ্রান্তিকর" in text
            or "গুলিয়ে ফেলি" in text or "গুলিয়ে ফেলছি" in text):
        return es_confusion_pairs_text()
    if ("সাহস বার্তা" in text or "হলে যাওয়ার আগে" in text
            or "হলের দরজায়" in text or "পরীক্ষার আগে বলো" in text):
        return es_courage_text()
    return None


# -*- coding: utf-8 -*-
"""
jobprep_pack.py — Desktop Sokhi: চাকরি-প্রস্তুতি জ্ঞান প্যাক (Wave-4, v1.6 features)

১০০% ফ্রি ও অফলাইন: কোনো নেটওয়ার্ক, API key বা বাইরের ফাইল লাগে না।
এটি STUDY content — কোনো sokhi.py ফাইলের অংশ নয়; ইন্টিগ্রেশন পদ্ধতি
INTEGRATION-JOBPREP.md-তে দেওয়া আছে।

নির্ভুলতার নিয়ম (binding):
- শুধু সুপ্রতিষ্ঠিত, স্থিতিশীল তথ্য রাখা হয়েছে।
- যেসব মান প্রতি বছর/বাজেটে বদলায় (ভাতার হার, টোল, ভাড়া, প্রকল্পের খরচ)
  সেখানে সংখ্যার বদলে যাচাই-নোট দেওয়া হয়েছে।
- বর্তমান পদাধিকারীদের (মন্ত্রী/সচিব/মহাপরিচালক) কোনো নাম রাখা হয়নি।
- যেসব তথ্য নিয়ে পাঠ্যপুস্তকে মতভেদ আছে বা নিশ্চিত হওয়া যায়নি,
  সেগুলো বাদ দেওয়া হয়েছে (তালিকা INTEGRATION-JOBPREP.md ও রিপোর্টে)।

প্রতিটি প্যাকের header-এ এই সতর্কবার্তা থাকতেই হবে:
    "সাধারণ জ্ঞানের স্থিতিশীল তথ্য; পরিবর্তনশীল তথ্য পরীক্ষার আগে যাচাই করতে হবে"
"""

import re

DISCLAIMER = ("সাধারণ জ্ঞানের স্থিতিশীল তথ্য; পরিবর্তনশীল তথ্য "
              "পরীক্ষার আগে যাচাই করতে হবে।")
VERIFY_NOTE = "হার প্রতি বাজেটে বদলাতে পারে — সর্বশেষ তথ্য যাচাই করে নিও।"

# =====================================================================
# Pack 1 — #787 + #789 : সমাজসেবা ও সমাজকর্ম
# =====================================================================

PACK_SOCIAL_SERVICE = {
    "id": "social_service",
    "refs": "#787, #789",
    "title": "সমাজসেবা ও সমাজকর্ম প্যাক",
    "header": DISCLAIMER,
    "entries": [
        {
            "topic": "সমাজসেবা অধিদপ্তর পরিচিতি",
            "keywords": ["সমাজসেবা অধিদপ্তর", "dss", "অধিদপ্তর", "সমাজকল্যাণ মন্ত্রণালয়"],
            "text": (
                "সমাজসেবা অধিদপ্তর (Department of Social Services) সমাজকল্যাণ "
                "মন্ত্রণালয়ের অধীন একটি সরকারি অধিদপ্তর। এর কাজ সমাজের পিছিয়ে পড়া, "
                "দরিদ্র, এতিম, প্রতিবন্ধী, বয়স্ক ও অসহায় মানুষের কল্যাণে বিভিন্ন "
                "সেবা ও ভাতা কর্মসূচি মাঠপর্যায়ে বাস্তবায়ন করা। সদর দপ্তর থেকে "
                "জেলা ও উপজেলা সমাজসেবা কার্যালয়ের মাধ্যমে এবং মাঠপর্যায়ে ইউনিয়ন "
                "সমাজকর্মীদের দিয়ে এই সেবা পৌঁছে দেওয়া হয়।"
            ),
        },
        {
            "topic": "সমাজসেবা অধিদপ্তরের প্রধান কাজ",
            "keywords": ["অধিদপ্তরের কাজ", "কার্যাবলি", "প্রধান কাজ"],
            "text": (
                "সমাজসেবা অধিদপ্তরের প্রধান কাজগুলো হলো:\n"
                "• সামাজিক নিরাপত্তা ভাতা (বয়স্ক, বিধবা, প্রতিবন্ধী প্রভৃতি) বিতরণে সহায়তা\n"
                "• এতিম শিশুদের লালন-পালন ও সরকারি শিশু পরিবার/এতিমখানা পরিচালনায় সহায়তা\n"
                "• প্রতিবন্ধী ব্যক্তিদের জরিপ, পরিচয়পত্র ও পুনর্বাসনে সহায়তা\n"
                "• দরিদ্র ও অসহায় মানুষের জন্য ক্ষুদ্রঋণ ও পুনর্বাসনমূলক কার্যক্রম\n"
                "• স্বেচ্ছাসেবী সমাজকল্যাণ সংগঠনের নিবন্ধন ও তদারকিতে সহায়তা\n"
                "• ভবঘুরে, ভিক্ষুক পুনর্বাসন ও অসহায় রোগীদের সহায়তার মতো কল্যাণমূলক কাজ\n"
                "• হাসপাতাল সমাজসেবা কার্যক্রমের মাধ্যমে গরিব রোগীদের সহায়তা"
            ),
        },
        {
            "topic": "সমাজকর্মের সংজ্ঞা",
            "keywords": ["সমাজকর্ম", "সংজ্ঞা", "social work", "কাকে বলে"],
            "text": (
                "পাঠ্যপুস্তকে সাধারণভাবে বলা হয়: সমাজকর্ম হলো একটি পেশাদার সেবা ও "
                "প্রায়োগিক বিজ্ঞান, যার মাধ্যমে বৈজ্ঞানিক জ্ঞান ও পদ্ধতি ব্যবহার করে "
                "ব্যক্তি, দল ও সমষ্টিকে তাদের সমস্যা নিজেরাই সমাধান করতে এবং পরিবেশের "
                "সঙ্গে খাপ খাইয়ে চলতে সক্ষম করে তোলা হয়।\n"
                "সহজ কথায়: সমাজকর্ম মানুষকে 'সাহায্য নেওয়ার' বদলে 'নিজে সমস্যা মোকাবিলা "
                "করতে পারা' শেখায় — যাতে সে আত্মনির্ভরশীল হতে পারে।\n"
                "সমাজসেবা আর সমাজকর্ম এক নয়: সমাজসেবা হলো কল্যাণমূলক সেবা দেওয়া, "
                "আর সমাজকর্ম হলো প্রশিক্ষিত পেশাদার পদ্ধতিতে সেই সেবা দেওয়ার বিজ্ঞান।"
            ),
        },
        {
            "topic": "সমাজকর্মের পদ্ধতি",
            "keywords": ["পদ্ধতি", "ব্যক্তি সমাজকর্ম", "দল সমাজকর্ম", "সমষ্টি", "case work", "group work"],
            "text": (
                "সমাজকর্মের প্রধান (মৌলিক) পদ্ধতি তিনটি:\n"
                "১. ব্যক্তি সমাজকর্ম (Case Work) — একজন ব্যক্তি বা পরিবারের সমস্যা "
                "একের পর এক ধাপে বুঝে সমাধানে সাহায্য করা।\n"
                "২. দল সমাজকর্ম (Group Work) — দলগত কার্যক্রমের মাধ্যমে সদস্যদের "
                "আচরণ, দক্ষতা ও সামাজিক সম্পর্কের উন্নতি করা।\n"
                "৩. সমষ্টি সমাজকর্ম / সমষ্টি সংগঠন (Community Organization) — পুরো "
                "এলাকা বা সম্প্রদায়কে সংগঠিত করে যৌথ সমস্যার সমাধান করা।\n"
                "সহায়ক পদ্ধতি: সমাজকর্ম প্রশাসন (সেবা-প্রতিষ্ঠান পরিচালনা), সমাজকর্ম "
                "গবেষণা (তথ্য সংগ্রহ ও বিশ্লেষণ) এবং সামাজিক কার্যক্রম (Social Action)।"
            ),
        },
        {
            "topic": "সমাজকর্মের মূল্যবোধ ও নীতি",
            "keywords": ["মূল্যবোধ", "নীতি", "গোপনীয়তা", "আত্মনির্ণয়", "মানবমর্যাদা"],
            "text": (
                "সমাজকর্মের মূল মূল্যবোধ ও নীতি:\n"
                "• মানবমর্যাদা: প্রতিটি মানুষের জন্মগত মর্যাদা ও মূল্য স্বীকার করা\n"
                "• গোপনীয়তা: সেবাগ্রহীতার ব্যক্তিগত তথ্য গোপন রাখা\n"
                "• আত্মনির্ণয়ের অধিকার: সেবাগ্রহীতাকে নিজের সিদ্ধান্ত নিজে নিতে দেওয়া\n"
                "• গ্রহণযোগ্যতা: সেবাগ্রহীতাকে সে যেমন, তেমনভাবে গ্রহণ করা\n"
                "• বিচার না করা: দোষারোপ বা রায় না দিয়ে সমস্যাটা বোঝা\n"
                "• ব্যক্তিকরণ: প্রতিটি মানুষের সমস্যাকে আলাদাভাবে দেখা\n"
                "• সমতা: ধর্ম, বর্ণ, লিঙ্গ নির্বিশেষে সমান সেবা দেওয়া"
            ),
        },
        {
            "topic": "সমাজসেবা ও সমাজকর্মের পার্থক্য",
            "keywords": ["পার্থক্য", "তফাত"],
            "text": (
                "• সমাজসেবা: দান-খয়রাত বা কল্যাণের উদ্দেশ্যে দেওয়া যেকোনো সেবা; "
                "যেকেউ দিতে পারে, পেশাদার প্রশিক্ষণ বাধ্যতামূলক নয়।\n"
                "• সমাজকর্ম: প্রশিক্ষিত পেশাদার কর্মীর দেওয়া বৈজ্ঞানিক পদ্ধতিনির্ভর সেবা; "
                "লক্ষ্য শুধু তাৎক্ষণিক সাহায্য নয়, সেবাগ্রহীতাকে আত্মনির্ভরশীল করা।\n"
                "মনে রাখার কৌশল: সেবা = সাহায্য দেওয়া; কর্ম = পদ্ধতি মেনে সাহায্য করে "
                "মানুষকে নিজের পায়ে দাঁড় করানো।"
            ),
        },
        {
            "topic": "ইউনিয়ন সমাজকর্মীর কাজের ক্ষেত্র",
            "keywords": ["ইউনিয়ন সমাজকর্মী", "মাঠপর্যায়", "কাজের ক্ষেত্র", "দায়িত্ব"],
            "text": (
                "ইউনিয়ন সমাজকর্মী হলেন সমাজসেবা অধিদপ্তরের মাঠপর্যায়ের (ইউনিয়ন পর্যায়ের) "
                "কর্মী। সাধারণভাবে তাঁর কাজের ক্ষেত্র:\n"
                "• এলাকার দরিদ্র, বয়স্ক, বিধবা, প্রতিবন্ধী ও এতিমদের তথ্য সংগ্রহ ও জরিপ\n"
                "• ভাতা পাওয়ার যোগ্য ব্যক্তি বাছাই ও তালিকা তৈরিতে সহায়তা, তথ্য যাচাই\n"
                "• ভাতা বিতরণ ও সুবিধাভোগীদের খোঁজখবর রাখা\n"
                "• প্রতিবন্ধী ব্যক্তি শনাক্তকরণ ও সেবার সঙ্গে যুক্ত করা\n"
                "• স্বেচ্ছাসেবী সংগঠন ও স্থানীয় কল্যাণমূলক কার্যক্রমে সহায়তা\n"
                "• ঊর্ধ্বতন কার্যালয়ে (উপজেলা সমাজসেবা অফিস) প্রতিবেদন পাঠানো\n"
                "• ইউনিয়ন পরিষদ ও স্থানীয় জনগণের সঙ্গে সমন্বয় করে কাজ করা"
            ),
        },
    ],
}

# =====================================================================
# Pack 2 — #788 : সামাজিক নিরাপত্তা কর্মসূচি
# =====================================================================

PACK_SOCIAL_SAFETY = {
    "id": "social_safety",
    "refs": "#788",
    "title": "সামাজিক নিরাপত্তা কর্মসূচি প্যাক",
    "header": DISCLAIMER,
    "entries": [
        {
            "topic": "সামাজিক নিরাপত্তা কর্মসূচি পরিচিতি",
            "keywords": ["সামাজিক নিরাপত্তা", "safety net", "কর্মসূচি", "ভাতা তালিকা"],
            "text": (
                "সামাজিক নিরাপত্তা কর্মসূচি হলো সরকারের সেই ব্যবস্থা, যার মাধ্যমে দরিদ্র, "
                "বয়স্ক, বিধবা, প্রতিবন্ধী ও অসহায় নাগরিকদের নিয়মিত আর্থিক সহায়তা ও "
                "সুরক্ষা দেওয়া হয়। সমাজসেবা অধিদপ্তরের মাধ্যমে পরিচালিত প্রধান ভাতাগুলো:\n"
                "• বয়স্ক ভাতা\n"
                "• বিধবা ও স্বামী-নিগৃহীতা মহিলা ভাতা\n"
                "• প্রতিবন্ধী ব্যক্তিদের ভাতা/আর্থিক সহায়তা\n"
                "• বীর মুক্তিযোদ্ধা সম্মানী ভাতা (মুক্তিযুদ্ধ বিষয়ক মন্ত্রণালয়ের কর্মসূচি, "
                "মাঠপর্যায়ে বিতরণে স্থানীয় প্রশাসন ও সমাজসেবা কার্যালয় জড়িত থাকে)\n"
                f"সব ভাতার ক্ষেত্রে মনে রেখো: {VERIFY_NOTE}"
            ),
        },
        {
            "topic": "বয়স্ক ভাতা",
            "keywords": ["বয়স্ক", "old age", "প্রবীণ"],
            "text": (
                "উদ্দেশ্য: আয়ের উৎসহীন বা দরিদ্র প্রবীণ নাগরিকদের জীবনযাত্রায় নিয়মিত "
                "আর্থিক সহায়তা দেওয়া।\n"
                "যোগ্যতা (সাধারণভাবে): সরকার নির্ধারিত বয়সসীমা পূর্ণ করা দরিদ্র প্রবীণ "
                "ব্যক্তি; সাধারণত পুরুষ ও মহিলার জন্য আলাদা বয়সসীমা নির্ধারণ করা থাকে এবং "
                "দরিদ্রতা ও অসহায়ত্বকে অগ্রাধিকার দেওয়া হয়। বয়সসীমা ও শর্ত সরকারি "
                "নীতিমালায় নির্ধারিত হয় — পরীক্ষার আগে সর্বশেষ নীতিমালা যাচাই করে নিও।\n"
                f"ভাতার হার: {VERIFY_NOTE}"
            ),
        },
        {
            "topic": "বিধবা ও স্বামী-নিগৃহীতা মহিলা ভাতা",
            "keywords": ["বিধবা", "স্বামী নিগৃহীতা", "স্বামী-নিগৃহীতা", "widow"],
            "text": (
                "উদ্দেশ্য: স্বামী মারা গেছেন এমন বিধবা নারী এবং স্বামীর দ্বারা পরিত্যক্ত/নিগৃহীত "
                "দরিদ্র নারীদের আর্থিক নিরাপত্তা দেওয়া।\n"
                "যোগ্যতা (সাধারণভাবে): দরিদ্র বিধবা বা স্বামী-নিগৃহীতা নারী; আয়ের অবস্থা, "
                "বয়স ও পরিবারের অবস্থা যাচাই করে স্থানীয়ভাবে বাছাই করা হয়। সঠিক শর্ত "
                "সরকারি নীতিমালা অনুযায়ী নির্ধারিত হয়।\n"
                f"ভাতার হার: {VERIFY_NOTE}"
            ),
        },
        {
            "topic": "প্রতিবন্ধী ভাতা",
            "keywords": ["প্রতিবন্ধী", "disability", "প্রতিবন্ধী ভাতা"],
            "text": (
                "উদ্দেশ্য: প্রতিবন্ধী ব্যক্তিদের জীবনযাত্রা, চিকিৎসা ও দৈনন্দিন ব্যয়ে আর্থিক "
                "সহায়তা দেওয়া এবং তাঁদের সমাজের মূলধারায় যুক্ত করা।\n"
                "যোগ্যতা (সাধারণভাবে): প্রতিবন্ধী হিসেবে শনাক্ত/নিবন্ধিত ও পরিচয়পত্রধারী "
                "দরিদ্র ব্যক্তি; প্রতিবন্ধিতার ধরন ও মাত্রা এবং পরিবারের আর্থিক অবস্থা "
                "বিবেচনা করা হয়। এছাড়া প্রতিবন্ধী শিক্ষার্থীদের জন্য শিক্ষা উপবৃত্তির "
                "ব্যবস্থাও সামাজিক নিরাপত্তা কার্যক্রমের অংশ।\n"
                f"ভাতার হার: {VERIFY_NOTE}"
            ),
        },
        {
            "topic": "মুক্তিযোদ্ধা সম্মানী ভাতা",
            "keywords": ["মুক্তিযোদ্ধা", "সম্মানী", "freedom fighter"],
            "text": (
                "উদ্দেশ্য: মহান মুক্তিযুদ্ধে অবদানের স্বীকৃতি হিসেবে বীর মুক্তিযোদ্ধাদের "
                "মাসিক সম্মানী ভাতা দেওয়া।\n"
                "যোগ্যতা (সাধারণভাবে): সরকারিভাবে তালিকাভুক্ত/স্বীকৃত বীর মুক্তিযোদ্ধা; "
                "মুক্তিযোদ্ধা মারা গেলে নির্ধারিত নিয়মে তাঁর পরিবারের সদস্যরা সুবিধা পেতে "
                "পারেন। এই কর্মসূচি মুক্তিযুদ্ধ বিষয়ক মন্ত্রণালয়ের অধীনে পরিচালিত হয়।\n"
                f"সম্মানীর হার: {VERIFY_NOTE}"
            ),
        },
        {
            "topic": "ভাতা নির্বাচন ও বিতরণ প্রক্রিয়া",
            "keywords": ["নির্বাচন", "বিতরণ", "প্রক্রিয়া", "কীভাবে পাওয়া যায়", "আবেদন"],
            "text": (
                "সাধারণ প্রক্রিয়া (ধাপে ধাপে):\n"
                "১. আবেদন/তথ্য সংগ্রহ: ইউনিয়ন পর্যায়ে ইউনিয়ন সমাজকর্মী ও ইউনিয়ন পরিষদের "
                "মাধ্যমে সম্ভাব্য সুবিধাভোগীর তথ্য সংগ্রহ করা হয়।\n"
                "২. যাচাই-বাছাই: ওয়ার্ড/ইউনিয়ন পর্যায়ের কমিটি আবেদন যাচাই করে যোগ্যদের "
                "তালিকা তৈরি করে।\n"
                "৩. অনুমোদন: উপজেলা পর্যায়ে তালিকা চূড়ান্ত অনুমোদন পায়।\n"
                "৪. পরিশোধ: বর্তমানে ভাতা সাধারণত ব্যাংক হিসাব বা মোবাইল আর্থিক সেবার "
                "মাধ্যমে সরাসরি সুবিধাভোগীর কাছে পৌঁছে দেওয়া হয় — এতে মধ্যস্থতাকারীর "
                "হয়রানি কমে।\n"
                "৫. অভিযোগ ও সংশোধন: ভুল তালিকা বা বাদ পড়া নিয়ে স্থানীয় সমাজসেবা "
                "কার্যালয়ে অভিযোগ করা যায়।\n"
                f"নোট: {VERIFY_NOTE}"
            ),
        },
    ],
}

# =====================================================================
# Pack 3 — #796 : ইউনিয়ন পরিষদ
# =====================================================================

PACK_UNION_PARISHAD = {
    "id": "union_parishad",
    "refs": "#796",
    "title": "ইউনিয়ন পরিষদ প্যাক",
    "header": DISCLAIMER,
    "entries": [
        {
            "topic": "ইউনিয়ন পরিষদ পরিচিতি ও গঠন",
            "keywords": ["ইউনিয়ন পরিষদ", "গঠন", "union parishad", "স্থানীয় সরকার"],
            "text": (
                "ইউনিয়ন পরিষদ হলো বাংলাদেশের স্থানীয় সরকার ব্যবস্থার সবচেয়ে নিচের "
                "(গ্রাম পর্যায়ের) নির্বাচিত প্রতিষ্ঠান। একটি ইউনিয়ন সাধারণত কয়েকটি গ্রাম "
                "নিয়ে গঠিত হয় এবং পুরো ইউনিয়নকে ৯টি ওয়ার্ডে ভাগ করা হয়।\n"
                "গঠন: ১ জন চেয়ারম্যান + ৯ জন সাধারণ সদস্য (প্রতি ওয়ার্ডে ১ জন) + "
                "৩ জন সংরক্ষিত মহিলা সদস্য = মোট ১৩ জন নির্বাচিত জনপ্রতিনিধি।\n"
                "পরিষদের মেয়াদ ৫ বছর। ইউনিয়ন পরিষদ স্থানীয় সরকার (ইউনিয়ন পরিষদ) "
                "আইন অনুযায়ী পরিচালিত হয়।"
            ),
        },
        {
            "topic": "চেয়ারম্যানের ভূমিকা",
            "keywords": ["চেয়ারম্যান", "chairman"],
            "text": (
                "চেয়ারম্যান ইউনিয়ন পরিষদের প্রধান। তিনি পুরো ইউনিয়নের ভোটারদের সরাসরি "
                "ভোটে নির্বাচিত হন। তাঁর প্রধান কাজ: পরিষদের সভায় সভাপতিত্ব করা, পরিষদের "
                "কার্যক্রম তদারকি করা, ইউনিয়নের উন্নয়ন পরিকল্পনা বাস্তবায়নে নেতৃত্ব দেওয়া "
                "এবং সরকারি বিভিন্ন কার্যক্রমে স্থানীয় সমন্বয় করা।"
            ),
        },
        {
            "topic": "সদস্য ও সংরক্ষিত মহিলা আসন",
            "keywords": ["সদস্য", "ওয়ার্ড", "সংরক্ষিত", "মহিলা আসন", "মেম্বার"],
            "text": (
                "• সাধারণ সদস্য: ইউনিয়নের ৯টি ওয়ার্ডের প্রতিটি থেকে ১ জন করে মোট ৯ জন "
                "সদস্য সরাসরি ভোটে নির্বাচিত হন।\n"
                "• সংরক্ষিত মহিলা সদস্য: মোট ৩টি সংরক্ষিত মহিলা আসন থাকে; প্রতিটি মহিলা "
                "সদস্য পরপর ৩টি ওয়ার্ড নিয়ে গঠিত এলাকা থেকে নির্বাচিত হন।\n"
                "• সব সদস্যই চেয়ারম্যানের মতো ৫ বছরের জন্য নির্বাচিত হন।"
            ),
        },
        {
            "topic": "ইউনিয়ন পরিষদের প্রধান কাজ",
            "keywords": ["কাজ", "কার্যাবলি", "দায়িত্ব", "functions"],
            "text": (
                "ইউনিয়ন পরিষদের প্রধান কাজগুলো:\n"
                "• জন্ম ও মৃত্যু নিবন্ধন; নাগরিক সনদ, চারিত্রিক সনদ প্রভৃতি দেওয়া\n"
                "• গ্রামের রাস্তাঘাট, সেতু-কালভার্ট, পানি নিষ্কাশন ও স্যানিটেশনে কাজ করা\n"
                "• আইনশৃঙ্খলা রক্ষায় সহায়তা ও গ্রাম পুলিশ (চৌকিদার-দফাদার) তদারকি\n"
                "• গ্রাম আদালতের মাধ্যমে ছোটখাটো দেওয়ানি ও ফৌজদারি বিরোধ নিষ্পত্তি\n"
                "• স্থানীয় সালিশ ও বিরোধ মীমাংসায় ভূমিকা রাখা\n"
                "• সরকারি ভাতা ও ত্রাণ বিতরণে সুবিধাভোগী বাছাইয়ে সহায়তা\n"
                "• কৃষি, শিক্ষা, স্বাস্থ্য, বৃক্ষরোপণ ও দুর্যোগ ব্যবস্থাপনায় স্থানীয় উদ্যোগ\n"
                "• ইউনিয়ন ডিজিটাল সেন্টারের মাধ্যমে নাগরিক সেবা পৌঁছে দেওয়া"
            ),
        },
        {
            "topic": "ইউনিয়ন পরিষদের কমিটি ও ওয়ার্ড সভা",
            "keywords": ["কমিটি", "স্থায়ী কমিটি", "ওয়ার্ড সভা"],
            "text": (
                "আইন অনুযায়ী ইউনিয়ন পরিষদে বিভিন্ন বিষয়ে স্থায়ী কমিটি গঠন করা হয় — "
                "যেমন অর্থ ও নিরীক্ষা, শিক্ষা, স্বাস্থ্য ও পরিবার পরিকল্পনা, কৃষি-মৎস্য-"
                "পশুসম্পদ, আইনশৃঙ্খলা, নারী ও শিশু উন্নয়ন প্রভৃতি বিষয়ের কমিটি। এসব কমিটি "
                "নিজ নিজ বিষয়ে পরিকল্পনা ও তদারকি করে।\n"
                "এছাড়া প্রতি ওয়ার্ডে ওয়ার্ড সভা অনুষ্ঠিত হয়, যেখানে ওয়ার্ডের বাসিন্দারা "
                "উন্নয়ন অগ্রাধিকার ও সমস্যা নিয়ে সরাসরি মত দিতে পারেন — এটি তৃণমূল "
                "অংশগ্রহণ নিশ্চিত করার ব্যবস্থা।\n"
                "নোট: কমিটির হালনাগাদ তালিকা ও গঠন সর্বশেষ আইন/বিধি অনুযায়ী যাচাই করা যায়।"
            ),
        },
        {
            "topic": "গ্রাম আদালত",
            "keywords": ["গ্রাম আদালত", "village court", "বিচার", "সালিশ"],
            "text": (
                "গ্রাম আদালত হলো ইউনিয়ন পর্যায়ে ছোটখাটো বিরোধ নিষ্পত্তির স্থানীয় বিচার "
                "ব্যবস্থা। চেয়ারম্যানের নেতৃত্বে উভয় পক্ষের মনোনীত সদস্যদের নিয়ে প্যানেল "
                "গঠিত হয়। জমি, পাওনা, ছোটখাটো মারামারি জাতীয় নির্ধারিত সীমার মধ্যের দেওয়ানি "
                "ও ফৌজদারি বিরোধ এখানে দ্রুত ও কম খরচে নিষ্পত্তি করা হয়, যাতে গ্রামের মানুষকে "
                "সামান্য বিষয়ে দূরের আদালতে যেতে না হয়।"
            ),
        },
    ],
}

# =====================================================================
# Pack 4 — #836 : কুড়িগ্রাম জেলা
# (শুধু নিশ্চিত স্থিতিশীল তথ্য; বাদ দেওয়া তথ্যের তালিকা রিপোর্টে আছে)
# =====================================================================

PACK_KURIGRAM = {
    "id": "kurigram",
    "refs": "#836",
    "title": "কুড়িগ্রাম জেলা প্যাক",
    "header": DISCLAIMER,
    "entries": [
        {
            "topic": "কুড়িগ্রাম জেলা পরিচিতি",
            "keywords": ["কুড়িগ্রাম", "জেলা", "প্রতিষ্ঠা", "kurigram"],
            "text": (
                "কুড়িগ্রাম বাংলাদেশের উত্তরাঞ্চলের একটি সীমান্তবর্তী জেলা, রংপুর বিভাগের "
                "অন্তর্গত। জেলাটি ১৯৮৪ সালে প্রতিষ্ঠিত হয় (এর আগে এটি রংপুর জেলার একটি "
                "মহকুমা ছিল)। নদী ও চরাঞ্চলের জন্য জেলাটি পরিচিত; বন্যা ও নদীভাঙন এখানকার "
                "মানুষের জীবনের পরিচিত চ্যালেঞ্জ। জেলা সদর কুড়িগ্রাম শহর ধরলা নদীর তীরে "
                "অবস্থিত।"
            ),
        },
        {
            "topic": "কুড়িগ্রামের উপজেলা",
            "keywords": ["উপজেলা", "থানা", "৯টি"],
            "text": (
                "কুড়িগ্রাম জেলায় মোট ৯টি উপজেলা:\n"
                "১. কুড়িগ্রাম সদর\n"
                "২. নাগেশ্বরী\n"
                "৩. ভুরুঙ্গামারী\n"
                "৪. ফুলবাড়ী\n"
                "৫. রাজারহাট\n"
                "৬. উলিপুর\n"
                "৭. চিলমারী\n"
                "৮. রৌমারী\n"
                "৯. রাজিবপুর\n"
                "মনে রাখার সূত্র: সদর-নাগেশ্বরী-ভুরুঙ্গামারী-ফুলবাড়ী-রাজারহাট, "
                "উলিপুর-চিলমারী-রৌমারী-রাজিবপুর — মোট ৯।"
            ),
        },
        {
            "topic": "কুড়িগ্রামের প্রধান নদী",
            "keywords": ["নদী", "ধরলা", "তিস্তা", "ব্রহ্মপুত্র", "দুধকুমার"],
            "text": (
                "কুড়িগ্রামের প্রধান নদীগুলো:\n"
                "• ব্রহ্মপুত্র — জেলার পূর্ব দিক দিয়ে প্রবাহিত বৃহৎ নদী\n"
                "• ধরলা — জেলা সদরের পাশ দিয়ে প্রবাহিত; তিস্তার শাখা হিসেবে পরিচিত ধারা "
                "শেষে ব্রহ্মপুত্রে মিশেছে\n"
                "• তিস্তা — জেলার পশ্চিম অংশ ছুঁয়ে যাওয়া বড় নদী\n"
                "• দুধকুমার — উত্তরাঞ্চল দিয়ে প্রবাহিত আরেকটি গুরুত্বপূর্ণ নদী\n"
                "এই নদীগুলোর চরাঞ্চলে বহু মানুষের বসবাস; চরের কৃষি ও জীবনযাত্রা জেলার "
                "পরিচিত বৈশিষ্ট্য।"
            ),
        },
        {
            "topic": "চিলমারী বন্দর",
            "keywords": ["চিলমারী", "বন্দর", "নদী বন্দর", "ঐতিহ্য"],
            "text": (
                "চিলমারী কুড়িগ্রামের ঐতিহ্যবাহী নদী বন্দর এলাকা — ব্রহ্মপুত্র নদের তীরে "
                "অবস্থিত এই উপজেলা বহু পুরনো সময় থেকে নৌ-বাণিজ্যের কেন্দ্র হিসেবে পরিচিত। "
                "চিলমারীর ঘাট থেকে চরাঞ্চল ও নদীপথে যাতায়াতের ঐতিহ্য দীর্ঘদিনের; এখানকার "
                "নদী বন্দরকে ঘিরে বহু লোককথা ও ইতিহাস জড়িত। রৌমারী-রাজিবপুরের চরাঞ্চলের "
                "সঙ্গে মূল ভূখণ্ডের যোগাযোগেও এই নদীপথ গুরুত্বপূর্ণ।"
            ),
        },
        {
            "topic": "ধরলা সেতু",
            "keywords": ["ধরলা সেতু", "সেতু", "bridge"],
            "text": (
                "ধরলা সেতু কুড়িগ্রাম সদরের কাছে ধরলা নদীর ওপর নির্মিত সেতু, যা জেলা সদরকে "
                "নদীর অপর পাড়ের এলাকা ও পার্শ্ববর্তী জেলার সঙ্গে সড়কপথে যুক্ত করেছে। "
                "সেতুটি চালু হওয়ার আগে এই পথে ফেরি/নৌকা ছিল প্রধান ভরসা; সেতুর ফলে সদরের "
                "সঙ্গে যোগাযোগ অনেক সহজ হয়েছে। (সেতুর সঠিক দৈর্ঘ্য ও নির্মাণব্যয় জাতীয় "
                "সংখ্যা এই প্যাকে রাখা হয়নি — দরকার হলে সরকারি সূত্রে যাচাই করে নিও।)"
            ),
        },
        {
            "topic": "কুড়িগ্রামের অবস্থান ও বিভাগ",
            "keywords": ["রংপুর বিভাগ", "অবস্থান", "সীমান্ত", "ভৌগোলিক"],
            "text": (
                "• বিভাগ: রংপুর\n"
                "• অবস্থান: দেশের সর্ব-উত্তরের জেলাগুলোর একটি; তিন দিকেই ভারতীয় সীমান্ত "
                "ঘেরা জেলা হিসেবে পরিচিত\n"
                "• প্রতিবেশী জেলা: লালমনিরহাট, রংপুর, গাইবান্ধা ও জামালপুরের সঙ্গে স্থলসীমা "
                "রয়েছে (নদীপথেও যোগাযোগ)।\n"
                "• বৈশিষ্ট্য: ব্রহ্মপুত্র অববাহিকার বিস্তীর্ণ চরাঞ্চল, কৃষিনির্ভর অর্থনীতি, "
                "ভুট্টা-ধান-পাট চাষের জন্য পরিচিত এলাকা।"
            ),
        },
    ],
}

# =====================================================================
# Pack 5 — #946 : সংক্ষেপণ ভান্ডার (abbreviations)
# =====================================================================

def _abbr(topic, full, bn):
    return {"topic": topic, "keywords": [topic.lower(), full.lower()],
            "text": f"{topic} = {full}\nবাংলায়: {bn}"}

PACK_ABBREVIATIONS = {
    "id": "abbreviations",
    "refs": "#946",
    "title": "সংক্ষেপণ ভান্ডার (Abbreviations)",
    "header": DISCLAIMER,
    "entries": [
        _abbr("UN", "United Nations", "জাতিসংঘ"),
        _abbr("WHO", "World Health Organization", "বিশ্ব স্বাস্থ্য সংস্থা"),
        _abbr("UNESCO", "United Nations Educational, Scientific and Cultural Organization", "জাতিসংঘের শিক্ষা, বিজ্ঞান ও সংস্কৃতি সংস্থা"),
        _abbr("UNICEF", "United Nations Children's Fund", "জাতিসংঘ শিশু তহবিল"),
        _abbr("FAO", "Food and Agriculture Organization", "খাদ্য ও কৃষি সংস্থা"),
        _abbr("ILO", "International Labour Organization", "আন্তর্জাতিক শ্রম সংস্থা"),
        _abbr("IMF", "International Monetary Fund", "আন্তর্জাতিক মুদ্রা তহবিল"),
        _abbr("SAARC", "South Asian Association for Regional Cooperation", "দক্ষিণ এশীয় আঞ্চলিক সহযোগিতা সংস্থা (সার্ক)"),
        _abbr("BIMSTEC", "Bay of Bengal Initiative for Multi-Sectoral Technical and Economic Cooperation", "বঙ্গোপসাগরীয় বহুখাতভিত্তিক কারিগরি ও অর্থনৈতিক সহযোগিতা উদ্যোগ"),
        _abbr("ASEAN", "Association of Southeast Asian Nations", "দক্ষিণ-পূর্ব এশীয় দেশগুলোর সংস্থা"),
        _abbr("OIC", "Organisation of Islamic Cooperation", "ইসলামি সহযোগিতা সংস্থা"),
        _abbr("EU", "European Union", "ইউরোপীয় ইউনিয়ন"),
        _abbr("GDP", "Gross Domestic Product", "মোট দেশজ উৎপাদন"),
        _abbr("GNP", "Gross National Product", "মোট জাতীয় উৎপাদন"),
        _abbr("HSC", "Higher Secondary Certificate", "উচ্চ মাধ্যমিক সার্টিফিকেট"),
        _abbr("SSC", "Secondary School Certificate", "মাধ্যমিক স্কুল সার্টিফিকেট"),
        _abbr("BCS", "Bangladesh Civil Service", "বাংলাদেশ সিভিল সার্ভিস"),
        _abbr("PSC", "Public Service Commission", "সরকারি কর্ম কমিশন"),
        _abbr("NID", "National Identification (Number/Card)", "জাতীয় পরিচয়পত্র/নম্বর"),
        _abbr("TIN", "Taxpayer Identification Number", "করদাতা শনাক্তকরণ নম্বর"),
        _abbr("VAT", "Value Added Tax", "মূল্য সংযোজন কর (মূসক)"),
        _abbr("DSS", "Department of Social Services", "সমাজসেবা অধিদপ্তর"),
        _abbr("LGED", "Local Government Engineering Department", "স্থানীয় সরকার প্রকৌশল অধিদপ্তর"),
        _abbr("UGC", "University Grants Commission", "বিশ্ববিদ্যালয় মঞ্জুরি কমিশন"),
        _abbr("BSTI", "Bangladesh Standards and Testing Institution", "বাংলাদেশ মান ও পরীক্ষণ প্রতিষ্ঠান"),
        _abbr("CPU", "Central Processing Unit", "কেন্দ্রীয় প্রক্রিয়াকরণ একক — কম্পিউটারের 'মস্তিষ্ক'"),
        _abbr("RAM", "Random Access Memory", "কম্পিউটারের অস্থায়ী স্মৃতি"),
        _abbr("ROM", "Read Only Memory", "কম্পিউটারের স্থায়ী স্মৃতি"),
        _abbr("WWW", "World Wide Web", "বিশ্বব্যাপী তথ্যজাল"),
        _abbr("HTML", "HyperText Markup Language", "ওয়েবপেজ তৈরির ভাষা"),
        _abbr("URL", "Uniform Resource Locator", "ওয়েব ঠিকানা"),
        _abbr("GPS", "Global Positioning System", "বৈশ্বিক অবস্থান নির্ণয় ব্যবস্থা"),
        _abbr("ATM", "Automated Teller Machine", "স্বয়ংক্রিয় টাকা তোলার যন্ত্র"),
        _abbr("SIM", "Subscriber Identity Module", "মোবাইল গ্রাহক শনাক্তকরণ চিপ"),
        _abbr("SMS", "Short Message Service", "খুদে বার্তা সেবা"),
        _abbr("DNA", "Deoxyribonucleic Acid", "বংশগতির ধারক অণু"),
        _abbr("HIV", "Human Immunodeficiency Virus", "এইডস সৃষ্টিকারী ভাইরাস"),
        _abbr("AIDS", "Acquired Immunodeficiency Syndrome", "অর্জিত রোগ-প্রতিরোধ-ঘাটতি রোগলক্ষণসমষ্টি"),
        _abbr("LASER", "Light Amplification by Stimulated Emission of Radiation", "উদ্দীপিত বিকিরণ নিঃসরণে আলো বিবর্ধন"),
        _abbr("RADAR", "Radio Detection and Ranging", "বেতার তরঙ্গে বস্তু শনাক্ত ও দূরত্ব নির্ণয়"),
        _abbr("NGO", "Non-Governmental Organization", "বেসরকারি সংস্থা"),
        _abbr("BBC", "British Broadcasting Corporation", "ব্রিটিশ সম্প্রচার কর্পোরেশন"),
        _abbr("CNN", "Cable News Network", "কেবল নিউজ নেটওয়ার্ক (সংবাদ চ্যানেল)"),
        _abbr("FIFA", "International Federation of Association Football (Fédération Internationale de Football Association)", "আন্তর্জাতিক ফুটবল ফেডারেশন"),
        _abbr("ICC", "International Cricket Council", "আন্তর্জাতিক ক্রিকেট কাউন্সিল"),
    ],
}

# =====================================================================
# Pack 6 — #943 ছদ্মনাম/উপাধি + #944 গ্রন্থ-লেখক
# =====================================================================

def _author(topic, kind, text, keywords=None):
    return {"topic": topic, "kind": kind, "keywords": keywords or [topic],
            "text": text}

PACK_AUTHORS = {
    "id": "authors_books",
    "refs": "#943, #944",
    "title": "ছদ্মনাম/উপাধি ও গ্রন্থ-লেখক প্যাক",
    "header": DISCLAIMER,
    "entries": [
        # ---- #943 ছদ্মনাম / উপাধি ----
        _author("রবীন্দ্রনাথ ঠাকুর", "ছদ্মনাম/উপাধি",
                "রবীন্দ্রনাথ ঠাকুর — উপাধি: বিশ্বকবি, কবিগুরু। কিশোর বয়সে 'ভানুসিংহ ঠাকুর' ছদ্মনামে/ভণিতায় পদাবলি-ধাঁচের কবিতা লিখেছিলেন।"),
        _author("বঙ্কিমচন্দ্র চট্টোপাধ্যায়", "ছদ্মনাম/উপাধি",
                "বঙ্কিমচন্দ্র চট্টোপাধ্যায় — উপাধি: সাহিত্য সম্রাট। তাঁর বিখ্যাত রসরচনার চরিত্র/ভণিতা: কমলাকান্ত (কমলাকান্তের দপ্তর)।"),
        _author("শরৎচন্দ্র চট্টোপাধ্যায়", "ছদ্মনাম/উপাধি",
                "শরৎচন্দ্র চট্টোপাধ্যায় — উপাধি: অপরাজেয় কথাশিল্পী। ছদ্মনাম: অনিলা দেবী (এই নামে তিনি রচনা প্রকাশ করেছিলেন)।"),
        _author("কাজী নজরুল ইসলাম", "ছদ্মনাম/উপাধি",
                "কাজী নজরুল ইসলাম — উপাধি: বিদ্রোহী কবি; তিনি বাংলাদেশের জাতীয় কবি। 'অগ্নিবীণা' কাব্যের 'বিদ্রোহী' কবিতা থেকেই এই উপাধি।"),
        _author("মাইকেল মধুসূদন দত্ত", "ছদ্মনাম/উপাধি",
                "মাইকেল মধুসূদন দত্ত — উপাধি: মহাকবি। বাংলা সাহিত্যে অমিত্রাক্ষর ছন্দ ও সনেটের প্রবর্তক হিসেবে পরিচিত।"),
        _author("ঈশ্বরচন্দ্র বিদ্যাসাগর", "ছদ্মনাম/উপাধি",
                "ঈশ্বরচন্দ্র বন্দ্যোপাধ্যায় — উপাধি: বিদ্যাসাগর (সংস্কৃত পাণ্ডিত্যের জন্য)। তিনি বাংলা গদ্যের জনক হিসেবে পরিচিত।"),
        _author("বেগম রোকেয়া", "ছদ্মনাম/উপাধি",
                "বেগম রোকেয়া সাখাওয়াত হোসেন — পরিচিতি: মুসলিম নারী জাগরণের অগ্রদূত। নারীশিক্ষা প্রসারে তিনি অগ্রণী ভূমিকা রাখেন।"),
        _author("জসীমউদ্দীন", "ছদ্মনাম/উপাধি",
                "জসীমউদ্দীন — উপাধি: পল্লিকবি। গ্রামবাংলার জীবন ও প্রকৃতি তাঁর কবিতার প্রাণ।"),
        _author("সুকান্ত ভট্টাচার্য", "ছদ্মনাম/উপাধি",
                "সুকান্ত ভট্টাচার্য — উপাধি: কিশোর কবি। অল্প বয়সেই তিনি মারা যান; 'ছাড়পত্র' তাঁর বিখ্যাত কাব্য।"),
        _author("জীবনানন্দ দাশ", "ছদ্মনাম/উপাধি",
                "জীবনানন্দ দাশ — উপাধি: রূপসী বাংলার কবি। 'রূপসী বাংলা' কাব্য ও 'বনলতা সেন' কবিতার জন্য বিখ্যাত।"),
        _author("ফররুখ আহমদ", "ছদ্মনাম/উপাধি",
                "ফররুখ আহমদ — উপাধি: মুসলিম রেনেসাঁর কবি। 'সাত সাগরের মাঝি' তাঁর বিখ্যাত কাব্য।"),
        _author("প্রমথ চৌধুরী", "ছদ্মনাম/উপাধি",
                "প্রমথ চৌধুরী — ছদ্মনাম: বীরবল। তিনি বাংলা চলিত গদ্যরীতির প্রবর্তক হিসেবে পরিচিত; 'সবুজপত্র' পত্রিকার সম্পাদক ছিলেন।"),
        _author("রাজশেখর বসু", "ছদ্মনাম/উপাধি",
                "রাজশেখর বসু — ছদ্মনাম: পরশুরাম। হাস্যরসাত্মক রচনার জন্য বিখ্যাত; 'চলন্তিকা' অভিধানের প্রণেতা।"),
        _author("সমরেশ বসু", "ছদ্মনাম/উপাধি",
                "সমরেশ বসু — ছদ্মনাম: কালকূট (এবং ভ্রমর)। 'শাম্ব' উপন্যাস কালকূট ছদ্মনামে লেখা।"),
        _author("বনফুল", "ছদ্মনাম/উপাধি",
                "বনফুল — আসল নাম: বলাইচাঁদ মুখোপাধ্যায়। 'বনফুল' তাঁর সাহিত্যিক ছদ্মনাম; পেশায় তিনি চিকিৎসক ছিলেন।"),
        _author("জরাসন্ধ", "ছদ্মনাম/উপাধি",
                "জরাসন্ধ — আসল নাম: চারুচন্দ্র চক্রবর্তী। কারাগারের অভিজ্ঞতাভিত্তিক রচনা 'লৌহকপাট'-এর জন্য বিখ্যাত।"),
        _author("কালীপ্রসন্ন সিংহ", "ছদ্মনাম/উপাধি",
                "কালীপ্রসন্ন সিংহ — ছদ্মনাম: হুতোম পেঁচা। 'হুতোম পেঁচার নকশা' তাঁর বিখ্যাত রচনা।"),
        _author("প্যারীচাঁদ মিত্র", "ছদ্মনাম/উপাধি",
                "প্যারীচাঁদ মিত্র — ছদ্মনাম: টেকচাঁদ ঠাকুর। 'আলালের ঘরের দুলাল' এই ছদ্মনামে প্রকাশিত।"),
        _author("নারায়ণ গঙ্গোপাধ্যায়", "ছদ্মনাম/উপাধি",
                "নারায়ণ গঙ্গোপাধ্যায় — ছদ্মনাম: সুনন্দ। টেনিদা চরিত্রের স্রষ্টা হিসেবে শিশু-কিশোর পাঠকের কাছে বিশেষ পরিচিত।"),
        _author("অন্নদাশঙ্কর রায়", "ছদ্মনাম/উপাধি",
                "অন্নদাশঙ্কর রায় — ছদ্মনাম: লীলাময় রায়। ছড়া ও প্রবন্ধে সিদ্ধহস্ত লেখক।"),
        _author("সুনীল গঙ্গোপাধ্যায়", "ছদ্মনাম/উপাধি",
                "সুনীল গঙ্গোপাধ্যায় — ছদ্মনাম: নীললোহিত। কবিতা ও উপন্যাস দুটোতেই সমান খ্যাতি।"),
        _author("সত্যেন্দ্রনাথ দত্ত", "ছদ্মনাম/উপাধি",
                "সত্যেন্দ্রনাথ দত্ত — উপাধি: ছন্দের জাদুকর। বাংলা ছন্দে অসাধারণ দক্ষতার জন্য এই নাম।"),
        _author("গোবিন্দচন্দ্র দাস", "ছদ্মনাম/উপাধি",
                "গোবিন্দচন্দ্র দাস — উপাধি: স্বভাব কবি। সহজ-স্বাভাবিক ভাষার কবিতার জন্য পরিচিত।"),
        _author("কায়কোবাদ", "ছদ্মনাম/উপাধি",
                "কায়কোবাদ — আসল নাম মোহাম্মদ কাজেম আল কোরায়শী; উপাধি: মহাকবি। 'মহাশ্মশান' তাঁর বিখ্যাত মহাকাব্য।"),
        _author("আবদুল করিম সাহিত্য বিশারদ", "ছদ্মনাম/উপাধি",
                "আবদুল করিম — উপাধি: সাহিত্য বিশারদ। বাংলা পুথি সংগ্রহ ও গবেষণায় অগ্রণী; চট্টগ্রামের সন্তান।"),
        _author("মীর মশাররফ হোসেন", "ছদ্মনাম/উপাধি",
                "মীর মশাররফ হোসেন — ছদ্মনাম: গাজী মিয়া ('গাজী মিয়ার বস্তানী')। 'বিষাদ সিন্ধু' তাঁর সবচেয়ে বিখ্যাত গ্রন্থ।"),
        # ---- #944 গ্রন্থ-লেখক ----
        _author("পদ্মা নদীর মাঝি", "গ্রন্থ-লেখক",
                "পদ্মা নদীর মাঝি (উপন্যাস) — লেখক: মানিক বন্দ্যোপাধ্যায়। জেলে-মাঝিদের জীবন নিয়ে লেখা; কুবের মাঝি এর কেন্দ্রীয় চরিত্র।", ["পদ্মা নদীর মাঝি কার লেখা", "পদ্মা নদীর মাঝি"]),
        _author("পথের পাঁচালী", "গ্রন্থ-লেখক",
                "পথের পাঁচালী (উপন্যাস) — লেখক: বিভূতিভূষণ বন্দ্যোপাধ্যায়। অপু-দুর্গার শৈশবের গল্প; এর পরের অংশ 'অপরাজিত'।", ["পথের পাঁচালী কার লেখা"]),
        _author("আরণ্যক", "গ্রন্থ-লেখক",
                "আরণ্যক (উপন্যাস) — লেখক: বিভূতিভূষণ বন্দ্যোপাধ্যায়। বন-প্রকৃতি ও মানুষের সম্পর্ক নিয়ে লেখা।", ["আরণ্যক কার লেখা"]),
        _author("হাঁসুলী বাঁকের উপকথা", "গ্রন্থ-লেখক",
                "হাঁসুলী বাঁকের উপকথা (উপন্যাস) — লেখক: তারাশঙ্কর বন্দ্যোপাধ্যায়।", ["হাঁসুলী বাঁকের উপকথা কার লেখা"]),
        _author("গীতাঞ্জলি", "গ্রন্থ-লেখক",
                "গীতাঞ্জলি (কাব্য) — লেখক: রবীন্দ্রনাথ ঠাকুর। এর ইংরেজি অনুবাদ 'Song Offerings'-এর জন্য তিনি ১৯১৩ সালে নোবেল পুরস্কার পান।", ["গীতাঞ্জলি কার লেখা"]),
        _author("শেষের কবিতা", "গ্রন্থ-লেখক",
                "শেষের কবিতা (উপন্যাস) — লেখক: রবীন্দ্রনাথ ঠাকুর। অমিত ও লাবণ্য এর কেন্দ্রীয় চরিত্র।", ["শেষের কবিতা কার লেখা"]),
        _author("অগ্নিবীণা", "গ্রন্থ-লেখক",
                "অগ্নিবীণা (কাব্য) — লেখক: কাজী নজরুল ইসলাম। তাঁর প্রথম কাব্যগ্রন্থ; 'বিদ্রোহী' কবিতা এতেই আছে।", ["অগ্নিবীণা কার লেখা"]),
        _author("আনন্দমঠ", "গ্রন্থ-লেখক",
                "আনন্দমঠ (উপন্যাস) — লেখক: বঙ্কিমচন্দ্র চট্টোপাধ্যায়। 'বন্দে মাতরম' গানটি এই উপন্যাসে আছে।", ["আনন্দমঠ কার লেখা"]),
        _author("কপালকুণ্ডলা", "গ্রন্থ-লেখক",
                "কপালকুণ্ডলা (উপন্যাস) — লেখক: বঙ্কিমচন্দ্র চট্টোপাধ্যায়। নবকুমার ও কপালকুণ্ডলা এর চরিত্র।", ["কপালকুণ্ডলা কার লেখা"]),
        _author("দেবদাস", "গ্রন্থ-লেখক",
                "দেবদাস (উপন্যাস) — লেখক: শরৎচন্দ্র চট্টোপাধ্যায়। দেবদাস-পার্বতী-চন্দ্রমুখীর গল্প।", ["দেবদাস কার লেখা"]),
        _author("পথের দাবী", "গ্রন্থ-লেখক",
                "পথের দাবী (উপন্যাস) — লেখক: শরৎচন্দ্র চট্টোপাধ্যায়। সব্যসাচী এর কেন্দ্রীয় চরিত্র।", ["পথের দাবী কার লেখা"]),
        _author("শ্রীকান্ত", "গ্রন্থ-লেখক",
                "শ্রীকান্ত (উপন্যাস) — লেখক: শরৎচন্দ্র চট্টোপাধ্যায়। আত্মজৈবনিক ধাঁচের বিখ্যাত রচনা।", ["শ্রীকান্ত কার লেখা"]),
        _author("সুলতানার স্বপ্ন", "গ্রন্থ-লেখক",
                "সুলতানার স্বপ্ন (Sultana's Dream) — লেখক: বেগম রোকেয়া সাখাওয়াত হোসেন। নারী-শাসিত কাল্পনিক জগতের গল্প; ইংরেজিতে লেখা।", ["সুলতানার স্বপ্ন কার লেখা", "sultana's dream"]),
        _author("মতিচূর", "গ্রন্থ-লেখক",
                "মতিচূর (প্রবন্ধ সংকলন) — লেখক: বেগম রোকেয়া সাখাওয়াত হোসেন। নারী অধিকার নিয়ে তাঁর যুক্তিনির্ভর প্রবন্ধের বই।", ["মতিচূর কার লেখা"]),
        _author("পদ্মাবতী", "গ্রন্থ-লেখক",
                "পদ্মাবতী (কাব্য) — লেখক: আলাওল। মধ্যযুগের বাংলা সাহিত্যের বিখ্যাত রোমান্টিক কাব্য।", ["পদ্মাবতী কার লেখা"]),
        _author("মেঘনাদবধ কাব্য", "গ্রন্থ-লেখক",
                "মেঘনাদবধ কাব্য (মহাকাব্য) — লেখক: মাইকেল মধুসূদন দত্ত। অমিত্রাক্ষর ছন্দে লেখা; রামায়ণের কাহিনি নতুন দৃষ্টিতে।", ["মেঘনাদবধ কার লেখা"]),
        _author("নকশী কাঁথার মাঠ", "গ্রন্থ-লেখক",
                "নকশী কাঁথার মাঠ (কাব্য) — লেখক: জসীমউদ্দীন। রূপাই ও সাজুর করুণ প্রেমকাহিনি।", ["নকশী কাঁথার মাঠ কার লেখা"]),
        _author("বনলতা সেন", "গ্রন্থ-লেখক",
                "বনলতা সেন (কাব্য) — লেখক: জীবনানন্দ দাশ। 'বাংলার মুখ আমি দেখিয়াছি' এই কাব্যেরই লাইন।", ["বনলতা সেন কার লেখা"]),
        _author("আবোল তাবোল", "গ্রন্থ-লেখক",
                "আবোল তাবোল (শিশুতোষ ছড়ার বই) — লেখক: সুকুমার রায়। 'রামগরুড়ের ছানা'সহ বিখ্যাত হাস্যরসের ছড়ার সংকলন।", ["আবোল তাবোল কার লেখা"]),
        _author("হাজার বছর ধরে", "গ্রন্থ-লেখক",
                "হাজার বছর ধরে (উপন্যাস) — লেখক: জহির রায়হান। গ্রামীণ নারীজীবনের চিরন্তন চিত্র।", ["হাজার বছর ধরে কার লেখা"]),
        _author("লালসালু", "গ্রন্থ-লেখক",
                "লালসালু (উপন্যাস) — লেখক: সৈয়দ ওয়ালীউল্লাহ। মজিদ চরিত্রের মাধ্যমে ধর্মান্ধতা ও ভণ্ডামির চিত্র।", ["লালসালু কার লেখা"]),
        _author("সূর্য দীঘল বাড়ী", "গ্রন্থ-লেখক",
                "সূর্য দীঘল বাড়ী (উপন্যাস) — লেখক: আবু ইসহাক। জয়গুনের সংগ্রামী জীবনের গল্প।", ["সূর্য দীঘল বাড়ী কার লেখা"]),
        _author("তিতাস একটি নদীর নাম", "গ্রন্থ-লেখক",
                "তিতাস একটি নদীর নাম (উপন্যাস) — লেখক: অদ্বৈত মল্লবর্মণ। তিতাস পাড়ের মালো সম্প্রদায়ের জীবন নিয়ে লেখা।", ["তিতাস কার লেখা", "তিতাস একটি নদীর নাম কার লেখা"]),
        _author("বিষাদ সিন্ধু", "গ্রন্থ-লেখক",
                "বিষাদ সিন্ধু (গদ্য মহাকাব্য/ঐতিহাসিক রচনা) — লেখক: মীর মশাররফ হোসেন। কারবালার ঘটনা এর মূল বিষয়।", ["বিষাদ সিন্ধু কার লেখা"]),
        _author("ক্রীতদাসের হাসি", "গ্রন্থ-লেখক",
                "ক্রীতদাসের হাসি (উপন্যাস) — লেখক: শওকত ওসমান। রূপকধর্মী বিখ্যাত রচনা।", ["ক্রীতদাসের হাসি কার লেখা"]),
        _author("সারেং বৌ", "গ্রন্থ-লেখক",
                "সারেং বৌ (উপন্যাস) — লেখক: শহীদুল্লাহ কায়সার। নাবিক জীবন ও উপকূলের মানুষের গল্প।", ["সারেং বৌ কার লেখা"]),
        _author("চিলেকোঠার সেপাই", "গ্রন্থ-লেখক",
                "চিলেকোঠার সেপাই (উপন্যাস) — লেখক: আখতারুজ্জামান ইলিয়াস। ঊনসত্তরের গণঅভ্যুত্থানের পটভূমিতে লেখা।", ["চিলেকোঠার সেপাই কার লেখা"]),
        _author("নন্দিত নরকে", "গ্রন্থ-লেখক",
                "নন্দিত নরকে (উপন্যাস) — লেখক: হুমায়ূন আহমেদ। এটি তাঁর প্রকাশিত প্রথম উপন্যাস হিসেবে পরিচিত।", ["নন্দিত নরকে কার লেখা"]),
    ],
}

# =====================================================================
# Pack 7 — #949 বিজ্ঞানী-আবিষ্কার + #945 রেকর্ড তথ্য (প্রথম/বৃহত্তম)
# =====================================================================

def _sci(topic, kind, text, keywords=None):
    return {"topic": topic, "kind": kind, "keywords": keywords or [topic],
            "text": text}

PACK_SCIENCE_RECORDS = {
    "id": "science_records",
    "refs": "#949, #945",
    "title": "বিজ্ঞানী-আবিষ্কার ও রেকর্ড তথ্য প্যাক",
    "header": DISCLAIMER,
    "entries": [
        # ---- #949 বিজ্ঞানী → আবিষ্কার/অবদান ----
        _sci("আইজ্যাক নিউটন", "বিজ্ঞানী-আবিষ্কার",
             "আইজ্যাক নিউটন — মাধ্যাকর্ষণ (মহাকর্ষ) সূত্র ও গতির তিন সূত্রের প্রবক্তা।", ["নিউটন", "মাধ্যাকর্ষণ কে আবিষ্কার", "newton"]),
        _sci("টমাস আলভা এডিসন", "বিজ্ঞানী-আবিষ্কার",
             "টমাস আলভা এডিসন — বৈদ্যুতিক বাল্বের ব্যবহারিক রূপদান ও ফোনোগ্রাফ (শব্দ রেকর্ডের যন্ত্র) আবিষ্কারের জন্য বিখ্যাত।", ["এডিসন", "বাল্ব কে আবিষ্কার", "edison"]),
        _sci("আলেকজান্ডার গ্রাহাম বেল", "বিজ্ঞানী-আবিষ্কার",
             "আলেকজান্ডার গ্রাহাম বেল — টেলিফোনের আবিষ্কারক হিসেবে পরিচিত।", ["গ্রাহাম বেল", "টেলিফোন কে আবিষ্কার"]),
        _sci("গুগলিয়েলমো মারকোনি", "বিজ্ঞানী-আবিষ্কার",
             "গুগলিয়েলমো মারকোনি — বেতার (রেডিও) যোগাযোগের পথিকৃৎ; দূরপাল্লার বেতার বার্তা পাঠানোর সফল প্রদর্শনের জন্য বিখ্যাত।", ["মারকোনি", "রেডিও কে আবিষ্কার", "বেতার"]),
        _sci("জগদীশচন্দ্র বসু", "বিজ্ঞানী-আবিষ্কার",
             "আচার্য জগদীশচন্দ্র বসু — বেতার তরঙ্গ গবেষণার পথিকৃৎ এবং উদ্ভিদের সাড়া/প্রাণ নিয়ে গবেষণার জন্য বিশ্বখ্যাত; ক্রেসকোগ্রাফ যন্ত্র তাঁর উদ্ভাবন।", ["জগদীশচন্দ্র", "ক্রেসকোগ্রাফ"]),
        _sci("রাইট ভ্রাতৃদ্বয়", "বিজ্ঞানী-আবিষ্কার",
             "রাইট ভ্রাতৃদ্বয় (উইলবার ও অরভিল রাইট) — প্রথম সফল চালিত উড়োজাহাজ (বিমান) ওড়ানোর কৃতিত্ব তাঁদের।", ["রাইট", "বিমান কে আবিষ্কার", "উড়োজাহাজ"]),
        _sci("আলবার্ট আইনস্টাইন", "বিজ্ঞানী-আবিষ্কার",
             "আলবার্ট আইনস্টাইন — আপেক্ষিকতা তত্ত্বের প্রবক্তা; বিখ্যাত সমীকরণ E = mc² (ভর-শক্তি সমতা)।", ["আইনস্টাইন", "আপেক্ষিকতা"]),
        _sci("চার্লস ডারউইন", "বিজ্ঞানী-আবিষ্কার",
             "চার্লস ডারউইন — বিবর্তনবাদ ও প্রাকৃতিক নির্বাচন তত্ত্বের প্রবক্তা; গ্রন্থ: 'On the Origin of Species'।", ["ডারউইন", "বিবর্তনবাদ"]),
        _sci("লুই পাস্তুর", "বিজ্ঞানী-আবিষ্কার",
             "লুই পাস্তুর — জলাতঙ্ক রোগের টিকা উদ্ভাবন এবং দুধ সংরক্ষণের 'পাস্তুরায়ন' পদ্ধতির জন্য বিখ্যাত।", ["পাস্তুর", "জলাতঙ্ক", "পাস্তুরায়ন"]),
        _sci("আলেকজান্ডার ফ্লেমিং", "বিজ্ঞানী-আবিষ্কার",
             "আলেকজান্ডার ফ্লেমিং — পেনিসিলিন (প্রথম অ্যান্টিবায়োটিক) আবিষ্কারক।", ["ফ্লেমিং", "পেনিসিলিন কে আবিষ্কার"]),
        _sci("মারি কুরি", "বিজ্ঞানী-আবিষ্কার",
             "মারি কুরি — তেজস্ক্রিয়তা নিয়ে গবেষণার পথিকৃৎ; রেডিয়াম ও পোলোনিয়াম মৌল আবিষ্কার করেন। দুটি আলাদা বিজ্ঞানশাখায় নোবেল পাওয়া একমাত্র ব্যক্তি।", ["মারি কুরি", "রেডিয়াম কে আবিষ্কার"]),
        _sci("গ্যালিলিও গ্যালিলি", "বিজ্ঞানী-আবিষ্কার",
             "গ্যালিলিও গ্যালিলি — দূরবীক্ষণ যন্ত্র দিয়ে আকাশ পর্যবেক্ষণ করে আধুনিক জ্যোতির্বিজ্ঞানের ভিত্তি রাখেন; আধুনিক বিজ্ঞানের জনকদের একজন।", ["গ্যালিলিও", "দূরবীক্ষণ"]),
        _sci("নিকোলাস কোপার্নিকাস", "বিজ্ঞানী-আবিষ্কার",
             "নিকোলাস কোপার্নিকাস — সৌরকেন্দ্রিক মতবাদের প্রবক্তা (পৃথিবী নয়, সূর্যই কেন্দ্রে — এই ধারণা প্রতিষ্ঠা করেন)।", ["কোপার্নিকাস", "সৌরকেন্দ্রিক"]),
        _sci("জেমস ওয়াট", "বিজ্ঞানী-আবিষ্কার",
             "জেমস ওয়াট — বাষ্পীয় ইঞ্জিনের উন্নত ও ব্যবহারিক রূপদান করেন, যা শিল্পবিপ্লবকে গতি দেয়।", ["জেমস ওয়াট", "বাষ্পীয় ইঞ্জিন"]),
        _sci("উইলহেম রন্টজেন", "বিজ্ঞানী-আবিষ্কার",
             "উইলহেম রন্টজেন — এক্স-রে (X-ray) রশ্মির আবিষ্কারক।", ["রন্টজেন", "এক্স-রে কে আবিষ্কার", "x-ray"]),
        _sci("জন লগি বেয়ার্ড", "বিজ্ঞানী-আবিষ্কার",
             "জন লগি বেয়ার্ড — টেলিভিশনের পথিকৃৎ; প্রথম যান্ত্রিক টেলিভিশন প্রদর্শনের কৃতিত্ব তাঁর।", ["বেয়ার্ড", "টেলিভিশন কে আবিষ্কার"]),
        _sci("টিম বার্নার্স-লি", "বিজ্ঞানী-আবিষ্কার",
             "টিম বার্নার্স-লি — ওয়ার্ল্ড ওয়াইড ওয়েব (WWW) উদ্ভাবক।", ["বার্নার্স-লি", "www কে আবিষ্কার"]),
        _sci("চার্লস ব্যাবেজ", "বিজ্ঞানী-আবিষ্কার",
             "চার্লস ব্যাবেজ — কম্পিউটারের জনক; অ্যানালিটিক্যাল ইঞ্জিনের নকশা প্রণয়ন করেন।", ["ব্যাবেজ", "কম্পিউটারের জনক"]),
        _sci("আর্কিমিডিস", "বিজ্ঞানী-আবিষ্কার",
             "আর্কিমিডিস — প্লবতা সূত্রের (ভাসমান বস্তুর নীতি) জন্য বিখ্যাত প্রাচীন গ্রিক বিজ্ঞানী।", ["আর্কিমিডিস", "প্লবতা"]),
        _sci("দিমিত্রি মেন্ডেলিভ", "বিজ্ঞানী-আবিষ্কার",
             "দিমিত্রি মেন্ডেলিভ — মৌলসমূহের পর্যায় সারণি (Periodic Table) প্রণয়নের জন্য বিখ্যাত।", ["মেন্ডেলিভ", "পর্যায় সারণি কে তৈরি"]),
        _sci("সত্যেন্দ্রনাথ বসু", "বিজ্ঞানী-আবিষ্কার",
             "সত্যেন্দ্রনাথ বসু — আইনস্টাইনের সঙ্গে 'বোস-আইনস্টাইন পরিসংখ্যান'-এর প্রবক্তা; 'বোসন' কণার নাম তাঁর নামে রাখা হয়েছে।", ["সত্যেন্দ্রনাথ বসু", "বোসন"]),
        # ---- #945 রেকর্ড: প্রথম / বৃহত্তম / দীর্ঘতম ----
        _sci("বৃহত্তম ব-দ্বীপ", "রেকর্ড",
             "বিশ্বের বৃহত্তম নদী ব-দ্বীপ হলো গঙ্গা-ব্রহ্মপুত্র ব-দ্বীপ (বঙ্গীয় ব-দ্বীপ) — এর সবচেয়ে বড় অংশ বাংলাদেশে অবস্থিত।", ["বৃহত্তম ব-দ্বীপ", "ব-দ্বীপ"]),
        _sci("কক্সবাজার সমুদ্র সৈকত", "রেকর্ড",
             "কক্সবাজার বিশ্বের দীর্ঘতম অবিচ্ছিন্ন বালুকাময় সমুদ্র সৈকত হিসেবে পরিচিত — দৈর্ঘ্য প্রায় ১২০ কিলোমিটার।", ["দীর্ঘতম সমুদ্র সৈকত", "কক্সবাজার"]),
        _sci("সুন্দরবন", "রেকর্ড",
             "সুন্দরবন বিশ্বের বৃহত্তম ম্যানগ্রোভ বন; বাংলাদেশ ও ভারতে বিস্তৃত এই বন ইউনেস্কো বিশ্ব ঐতিহ্যের তালিকায় আছে। রয়েল বেঙ্গল টাইগারের আবাস হিসেবে বিখ্যাত।", ["বৃহত্তম ম্যানগ্রোভ", "সুন্দরবন"]),
        _sci("সেন্ট মার্টিন দ্বীপ", "রেকর্ড",
             "সেন্ট মার্টিন বাংলাদেশের একমাত্র প্রবাল দ্বীপ — বঙ্গোপসাগরে অবস্থিত ছোট্ট এই দ্বীপ স্থানীয়ভাবে 'নারকেল জিঞ্জিরা' নামেও পরিচিত।", ["প্রবাল দ্বীপ", "সেন্ট মার্টিন"]),
        _sci("কুয়াকাটা", "রেকর্ড",
             "কুয়াকাটা এমন এক সমুদ্র সৈকত, যেখান থেকে একই জায়গায় দাঁড়িয়ে সূর্যোদয় ও সূর্যাস্ত — দুটোই দেখা যায়।", ["কুয়াকাটা", "সূর্যোদয় সূর্যাস্ত"]),
        _sci("রাঙামাটি জেলা", "রেকর্ড",
             "আয়তনে বাংলাদেশের বৃহত্তম জেলা হলো রাঙামাটি (পার্বত্য জেলা)।", ["বৃহত্তম জেলা", "রাঙামাটি"]),
        _sci("ভোলা দ্বীপ", "রেকর্ড",
             "ভোলা বাংলাদেশের বৃহত্তম দ্বীপ জেলা/দ্বীপ হিসেবে পরিচিত।", ["বৃহত্তম দ্বীপ", "ভোলা"]),
        _sci("বঙ্গবন্ধু স্যাটেলাইট-১", "রেকর্ড",
             "বঙ্গবন্ধু স্যাটেলাইট-১ বাংলাদেশের প্রথম কৃত্রিম উপগ্রহ (স্যাটেলাইট) — উৎক্ষেপণ করা হয় ২০১৮ সালে।", ["প্রথম স্যাটেলাইট", "বঙ্গবন্ধু স্যাটেলাইট"]),
        _sci("মাউন্ট এভারেস্ট", "রেকর্ড",
             "মাউন্ট এভারেস্ট বিশ্বের উচ্চতম পর্বতশৃঙ্গ। ১৯৫৩ সালে এডমন্ড হিলারি ও তেনজিং নোরগে প্রথম এর চূড়ায় ওঠেন।", ["উচ্চতম পর্বত", "এভারেস্ট প্রথম"]),
        _sci("প্রথম চাঁদে অবতরণ", "রেকর্ড",
             "চাঁদে পা রাখা প্রথম মানুষ নিল আর্মস্ট্রং (১৯৬৯ সাল, অ্যাপোলো-১১ অভিযান)।", ["চাঁদে প্রথম", "আর্মস্ট্রং"]),
        _sci("প্রশান্ত মহাসাগর", "রেকর্ড",
             "বিশ্বের বৃহত্তম ও গভীরতম মহাসাগর হলো প্রশান্ত মহাসাগর।", ["বৃহত্তম মহাসাগর"]),
        _sci("এশিয়া মহাদেশ", "রেকর্ড",
             "এশিয়া বিশ্বের বৃহত্তম মহাদেশ — আয়তন ও জনসংখ্যা দুটোতেই।", ["বৃহত্তম মহাদেশ"]),
        _sci("নীল নদ", "রেকর্ড",
             "নীল নদকে সাধারণত বিশ্বের দীর্ঘতম নদী হিসেবে ধরা হয়; আর পানিপ্রবাহের পরিমাণে বৃহত্তম নদী আমাজন।", ["দীর্ঘতম নদী", "নীল নদ"]),
        _sci("সাহারা মরুভূমি", "রেকর্ড",
             "সাহারা বিশ্বের বৃহত্তম উষ্ণ মরুভূমি — আফ্রিকা মহাদেশে অবস্থিত।", ["বৃহত্তম মরুভূমি", "সাহারা"]),
        _sci("রাশিয়া", "রেকর্ড",
             "আয়তনে বিশ্বের বৃহত্তম দেশ রাশিয়া।", ["বৃহত্তম দেশ"]),
        _sci("ভ্যাটিকান সিটি", "রেকর্ড",
             "আয়তনে বিশ্বের ক্ষুদ্রতম দেশ ভ্যাটিকান সিটি।", ["ক্ষুদ্রতম দেশ"]),
        _sci("চীনের মহাপ্রাচীর", "রেকর্ড",
             "চীনের মহাপ্রাচীর (Great Wall) মানুষের তৈরি দীর্ঘতম প্রাচীর/স্থাপনা হিসেবে বিখ্যাত।", ["মহাপ্রাচীর", "দীর্ঘতম প্রাচীর"]),
        _sci("নীল তিমি", "রেকর্ড",
             "নীল তিমি পৃথিবীর বৃহত্তম প্রাণী — স্থলভাগে বৃহত্তম প্রাণী আফ্রিকান হাতি, আর দ্রুততম স্থলপ্রাণী চিতা।", ["বৃহত্তম প্রাণী", "নীল তিমি", "দ্রুততম প্রাণী"]),
        _sci("হাকালুকি হাওর", "রেকর্ড",
             "হাকালুকি হাওর বাংলাদেশের অন্যতম বৃহত্তম হাওর — বর্ষায় বিস্তীর্ণ জলরাশি আর শীতে পাখির আগমনের জন্য পরিচিত।", ["বৃহত্তম হাওর", "হাকালুকি"]),
        _sci("প্রথম বাঙালি এভারেস্টজয়ী", "রেকর্ড",
             "বাংলাদেশের পক্ষে প্রথম এভারেস্ট জয়ের কৃতিত্ব মুসা ইব্রাহিমের (২০১০ সাল)।", ["প্রথম এভারেস্টজয়ী বাংলাদেশ", "মুসা ইব্রাহিম"]),
    ],
}

# =====================================================================
# Pack 8 — #922 + #923 : মেগা প্রকল্প
# =====================================================================

PACK_MEGA_PROJECTS = {
    "id": "mega_projects",
    "refs": "#922, #923",
    "title": "মেগা প্রকল্প প্যাক",
    "header": DISCLAIMER,
    "entries": [
        {
            "topic": "মেগা প্রকল্প পরিচিতি",
            "keywords": ["মেগা প্রকল্প", "mega project", "তালিকা"],
            "text": (
                "বাংলাদেশের আলোচিত বড় (মেগা) প্রকল্পগুলোর মধ্যে রয়েছে: পদ্মা সেতু, "
                "ঢাকা মেট্রোরেল, রূপপুর পারমাণবিক বিদ্যুৎ কেন্দ্র, কর্ণফুলী (বঙ্গবন্ধু) টানেল, "
                "পায়রা সমুদ্র বন্দর এবং মাতারবাড়ী গভীর সমুদ্র বন্দর ও বিদ্যুৎ কেন্দ্র। "
                "প্রতিটির আলাদা কার্ড এই প্যাকে আছে — প্রকল্পের নাম ধরে জিজ্ঞেস করলেই "
                "বিস্তারিত পাওয়া যাবে। (খরচ, টোল ও ভাড়ার মতো বদলানো সংখ্যা এই প্যাকে "
                "রাখা হয়নি।)"
            ),
        },
        {
            "topic": "পদ্মা সেতু",
            "keywords": ["পদ্মা সেতু", "padma bridge", "পদ্মা"],
            "text": (
                "পদ্মা সেতু:\n"
                "• অবস্থান: পদ্মা নদীর ওপর — এক পাড়ে মুন্সীগঞ্জের মাওয়া, অন্য পাড়ে "
                "শরীয়তপুর/মাদারীপুরের জাজিরা প্রান্ত\n"
                "• দৈর্ঘ্য: ৬.১৫ কিলোমিটার (মূল সেতু)\n"
                "• ধরন: দ্বিতল সেতু — ওপরে সড়কপথ, নিচে রেলপথ\n"
                "• উদ্দেশ্য: দক্ষিণ-পশ্চিমাঞ্চলের জেলাগুলোকে রাজধানীর সঙ্গে সরাসরি সড়ক "
                "(ও পরে রেল) যোগাযোগে যুক্ত করা\n"
                "• উদ্বোধন: ২০২২ সাল (সড়কপথে যান চলাচলের জন্য খুলে দেওয়া হয়)"
            ),
        },
        {
            "topic": "ঢাকা মেট্রোরেল",
            "keywords": ["মেট্রোরেল", "metro rail", "mrt-6", "এমআরটি"],
            "text": (
                "ঢাকা মেট্রোরেল (MRT-6 লাইন):\n"
                "• পথ: উত্তরা থেকে আগারগাঁও-ফার্মগেট হয়ে মতিঝিল পর্যন্ত\n"
                "• উদ্দেশ্য: ঢাকার যানজট কমানো ও দ্রুত গণপরিবহন দেওয়া — দেশের প্রথম "
                "মেট্রোরেল ও প্রথম বৈদ্যুতিক দ্রুতগতির নগর রেল ব্যবস্থা\n"
                "• উদ্বোধন: ডিসেম্বর ২০২২ (প্রথম অংশ দিয়াবাড়ি-আগারগাঁও দিয়ে যাত্রা শুরু)\n"
                "(ভাড়ার হার বদলাতে পারে — সর্বশেষ তথ্য যাচাই করে নিও।)"
            ),
        },
        {
            "topic": "রূপপুর পারমাণবিক বিদ্যুৎ কেন্দ্র",
            "keywords": ["রূপপুর", "পারমাণবিক", "nuclear", "পাবনা"],
            "text": (
                "রূপপুর পারমাণবিক বিদ্যুৎ কেন্দ্র:\n"
                "• অবস্থান: পাবনা জেলার ঈশ্বরদী উপজেলার রূপপুরে, পদ্মা নদীর তীরে\n"
                "• পরিচিতি: বাংলাদেশের প্রথম পারমাণবিক বিদ্যুৎ কেন্দ্র\n"
                "• সহায়তা: রাশিয়ার কারিগরি ও আর্থিক সহায়তায় নির্মিত\n"
                "• গঠন: ২টি ইউনিট; পরিকল্পিত মোট ক্ষমতা ২,৪০০ মেগাওয়াট\n"
                "• উদ্দেশ্য: দীর্ঘমেয়াদে বড় আকারের বিদ্যুৎ উৎপাদন বাড়ানো\n"
                "(চালুর সময়সূচি বদলাতে পারে — সর্বশেষ তথ্য যাচাই করে নিও।)"
            ),
        },
        {
            "topic": "কর্ণফুলী টানেল (বঙ্গবন্ধু টানেল)",
            "keywords": ["কর্ণফুলী টানেল", "বঙ্গবন্ধু টানেল", "টানেল", "চট্টগ্রাম", "tunnel"],
            "text": (
                "কর্ণফুলী টানেল (বঙ্গবন্ধু শেখ মুজিবুর রহমান টানেল):\n"
                "• অবস্থান: চট্টগ্রামে কর্ণফুলী নদীর তলদেশে — পতেঙ্গা প্রান্তকে আনোয়ারা "
                "প্রান্তের সঙ্গে যুক্ত করেছে\n"
                "• পরিচিতি: বাংলাদেশের প্রথম নদীর তলদেশের সড়ক টানেল\n"
                "• উদ্দেশ্য: বন্দরনগরীর দুই পাড়ের যোগাযোগ সহজ করা ও আনোয়ারা-কক্সবাজার "
                "অঞ্চলের সঙ্গে সংযোগ দ্রুত করা\n"
                "• উদ্বোধন: ২০২৩ সাল"
            ),
        },
        {
            "topic": "পায়রা সমুদ্র বন্দর",
            "keywords": ["পায়রা", "বন্দর", "payra", "পটুয়াখালী"],
            "text": (
                "পায়রা সমুদ্র বন্দর:\n"
                "• অবস্থান: পটুয়াখালী জেলার কলাপাড়ায়, রামনাবাদ চ্যানেলের তীরে\n"
                "• পরিচিতি: চট্টগ্রাম ও মোংলার পর বাংলাদেশের তৃতীয় সমুদ্র বন্দর\n"
                "• উদ্দেশ্য: দক্ষিণাঞ্চলের পণ্য পরিবহন সহজ করা এবং অন্য বন্দরগুলোর ওপর "
                "চাপ কমানো"
            ),
        },
        {
            "topic": "মাতারবাড়ী গভীর সমুদ্র বন্দর ও বিদ্যুৎ কেন্দ্র",
            "keywords": ["মাতারবাড়ী", "গভীর সমুদ্র বন্দর", "মহেশখালী", "matarbari"],
            "text": (
                "মাতারবাড়ী প্রকল্প এলাকা:\n"
                "• অবস্থান: কক্সবাজার জেলার মহেশখালী উপজেলার মাতারবাড়ীতে\n"
                "• গভীর সমুদ্র বন্দর: বড় (মাদার) জাহাজ সরাসরি ভেড়ার উপযোগী গভীর সমুদ্র "
                "বন্দর গড়ে তোলার কাজ চলমান — জাপানের সহায়তা এই উন্নয়নে গুরুত্বপূর্ণ\n"
                "• বিদ্যুৎ কেন্দ্র: একই এলাকায় বড় ক্ষমতার কয়লাভিত্তিক বিদ্যুৎ কেন্দ্রের "
                "পরিকল্পনা/নির্মাণ যুক্ত আছে\n"
                "(প্রকল্পের অগ্রগতি ও চালুর তারিখ বদলাতে থাকে — সর্বশেষ তথ্য যাচাই করে নিও।)"
            ),
        },
    ],
}

# =====================================================================
# Registry + lookup API
# =====================================================================

PACKS = {
    PACK_SOCIAL_SERVICE["id"]: PACK_SOCIAL_SERVICE,
    PACK_SOCIAL_SAFETY["id"]: PACK_SOCIAL_SAFETY,
    PACK_UNION_PARISHAD["id"]: PACK_UNION_PARISHAD,
    PACK_KURIGRAM["id"]: PACK_KURIGRAM,
    PACK_ABBREVIATIONS["id"]: PACK_ABBREVIATIONS,
    PACK_AUTHORS["id"]: PACK_AUTHORS,
    PACK_SCIENCE_RECORDS["id"]: PACK_SCIENCE_RECORDS,
    PACK_MEGA_PROJECTS["id"]: PACK_MEGA_PROJECTS,
}

# Chat commands → (pack_id, topic query or "" for topic list)
# INTEGRATION-JOBPREP.md-তে এই মানচিত্রটাই handle_message-এ বসানোর কথা বলা আছে।
COMMAND_MAP = {
    "সমাজসেবা শেখাও": ("social_service", ""),
    "সমাজসেবা": ("social_service", ""),
    "সমাজকর্ম": ("social_service", "সমাজকর্মের সংজ্ঞা"),
    "ভাতা": ("social_safety", ""),
    "সামাজিক নিরাপত্তা": ("social_safety", ""),
    "বয়স্ক ভাতা": ("social_safety", "বয়স্ক ভাতা"),
    "বিধবা ভাতা": ("social_safety", "বিধবা ও স্বামী-নিগৃহীতা মহিলা ভাতা"),
    "প্রতিবন্ধী ভাতা": ("social_safety", "প্রতিবন্ধী ভাতা"),
    "মুক্তিযোদ্ধা ভাতা": ("social_safety", "মুক্তিযোদ্ধা সম্মানী ভাতা"),
    "ইউনিয়ন পরিষদ": ("union_parishad", ""),
    "ইউনিয়ন সমাজকর্মী": ("social_service", "ইউনিয়ন সমাজকর্মীর কাজের ক্ষেত্র"),
    "কুড়িগ্রাম": ("kurigram", ""),
    "কুড়িগ্রাম জেলা": ("kurigram", ""),
    "সংক্ষেপণ": ("abbreviations", ""),
    "abbreviation": ("abbreviations", ""),
    "ছদ্মনাম": ("authors_books", ""),
    "উপাধি": ("authors_books", ""),
    "গ্রন্থ লেখক": ("authors_books", ""),
    "কার লেখা": ("authors_books", ""),
    "আবিষ্কার": ("science_records", ""),
    "বিজ্ঞানী": ("science_records", ""),
    "রেকর্ড": ("science_records", ""),
    "মেগা প্রকল্প": ("mega_projects", ""),
    "পদ্মা সেতু": ("mega_projects", "পদ্মা সেতু"),
    "মেট্রোরেল": ("mega_projects", "ঢাকা মেট্রোরেল"),
    "রূপপুর": ("mega_projects", "রূপপুর পারমাণবিক বিদ্যুৎ কেন্দ্র"),
    "jobprep": ("__all__", ""),
    "চাকরির পড়া": ("__all__", ""),
}

_PUNCT = re.compile(r"[^\w\u0980-\u09FF ]+", re.UNICODE)


def _norm(s):
    s = _PUNCT.sub(" ", (s or "").lower())
    return re.sub(r"\s+", " ", s).strip()


def all_packs():
    """সব প্যাকের সারসংক্ষেপ: [{id, refs, title, header, topic_count}]"""
    out = []
    for pid, pack in PACKS.items():
        out.append({
            "id": pid,
            "refs": pack["refs"],
            "title": pack["title"],
            "header": pack["header"],
            "topic_count": len(pack["entries"]),
        })
    return out


def pack_topics(pack_id):
    """একটি প্যাকের সব topic-এর তালিকা; অজানা pack_id হলে None।"""
    pack = PACKS.get(pack_id)
    if not pack:
        return None
    return [e["topic"] for e in pack["entries"]]


def _score(entry, q_norm, q_tokens):
    topic_n = _norm(entry["topic"])
    best = 0
    if q_norm == topic_n:
        best = 100
    elif q_norm and (q_norm in topic_n or topic_n in q_norm):
        # longer topic match wins ties (e.g. UNESCO beats UN)
        best = 75 + min(len(topic_n), 20)
    for kw in entry.get("keywords", []):
        kw_n = _norm(kw)
        if not kw_n:
            continue
        if q_norm == kw_n:
            best = max(best, 95)
        elif kw_n in q_norm or q_norm in kw_n:
            best = max(best, 70 + min(len(kw_n), 20))
    # token overlap (topic + keywords)
    hay = set(topic_n.split())
    for kw in entry.get("keywords", []):
        hay |= set(_norm(kw).split())
    if q_tokens:
        overlap = len(q_tokens & hay)
        if overlap:
            best = max(best, 30 + 15 * overlap)
    return best


def pack_text(pack_id, topic_query=""):
    """
    Fuzzy lookup:
    - pack_id অজানা হলে None ফেরত দেয়।
    - topic_query খালি হলে header + topic তালিকা ফেরত দেয়।
    - মিল পেলে header + entry-এর text ফেরত দেয়।
    - মিল না পেলে header + 'পাইনি' বার্তা + কাছাকাছি topic তালিকা ফেরত দেয়।
    """
    pack = PACKS.get(pack_id)
    if not pack:
        return None
    head = f"📚 {pack['title']} ({pack['refs']})\n{pack['header']}\n"
    q = (topic_query or "").strip()
    if not q:
        topics = "\n".join(f"• {t}" for t in pack_topics(pack_id))
        return (head + "\nএই প্যাকে যা যা আছে:\n" + topics +
                "\n\nযেটা পড়তে চাও, সেই বিষয়ের নাম ধরে বলো।")
    q_norm = _norm(q)
    q_tokens = set(q_norm.split())
    scored = sorted(
        ((_score(e, q_norm, q_tokens), e) for e in pack["entries"]),
        key=lambda x: -x[0],
    )
    if scored and scored[0][0] >= 40:
        e = scored[0][1]
        kind = f" [{e['kind']}]" if e.get("kind") else ""
        return head + f"\n■ {e['topic']}{kind}\n{e['text']}"
    topics = "\n".join(f"• {t}" for t in pack_topics(pack_id))
    return (head + f"\n'{q}' নামে ঠিক এই বিষয়টা এই প্যাকে পেলাম না। "
            "কাছাকাছি বিষয়গুলো:\n" + topics)


def search_all(query):
    """সব প্যাকে খুঁজে সেরা মিলের (pack_id, text) ফেরত দেয়; না পেলে (None, None)।"""
    q_norm = _norm(query)
    q_tokens = set(q_norm.split())
    best_pid, best_entry, best_score = None, None, 0
    for pid, pack in PACKS.items():
        for e in pack["entries"]:
            s = _score(e, q_norm, q_tokens)
            if s > best_score:
                best_pid, best_entry, best_score = pid, e, s
    if best_pid and best_score >= 40:
        return best_pid, pack_text(best_pid, best_entry["topic"])
    return None, None


def jobprep_handle(query):
    """
    Chat-entry helper (INTEGRATION-JOBPREP.md দ্রষ্টব্য):
    COMMAND_MAP-এর trigger মিললে বা search_all-এ শক্ত মিল পেলে
    study text ফেরত দেয়, নাহলে None — যাতে handle_message পরের ধাপে যেতে পারে।
    """
    q = (query or "").strip()
    if not q:
        return None
    low = q.lower()
    for trigger, (pid, topic) in COMMAND_MAP.items():
        if trigger in q or trigger in low:
            if pid == "__all__":
                lines = ["📚 চাকরি-প্রস্তুতি জ্ঞান প্যাকসমূহ:"]
                for p in all_packs():
                    lines.append(f"• {p['title']} ({p['refs']}) — {p['topic_count']}টি বিষয়")
                lines.append("\nবিষয়ের নাম ধরে বললেই পড়া শুরু হবে। "
                             f"নোট: {DISCLAIMER}")
                return "\n".join(lines)
            return pack_text(pid, topic)
    pid, text = search_all(q)
    if pid:
        return text
    return None




# ================= v1.7.0: #697 মাস্টারি টেস্ট (interactive) =================
_MASTERY_FILE = DATA / "study-mastery-session.json"


def _mastery_load():
    st = load_json(_MASTERY_FILE, None)
    return st if isinstance(st, dict) and st.get("questions") else None


def _mastery_fmt(st):
    q = st["questions"][st["idx"]]
    opts = "\n".join(f"{_OPT_LETTERS[i]}) {op}" for i, op in enumerate(q["options"]))
    return (f"প্রশ্ন {_bn_num(st['idx'] + 1)}/{_bn_num(len(st['questions']))} "
            f"(বিষয়: {st['subject']}, টপিক: {q.get('topic', 'সাধারণ')})\n"
            f"{q['q']}\n{opts}\n"
            "উত্তরটা লেখো (ক/খ/গ/ঘ বা অপশনের হুবহু লেখা)। থামাতে বলো: 'মাস্টারি থামাও'।")


def mastery_start(subject):
    """Bank-প্রশ্ন (4 options, int answer) অন্তত ৩টা থাকলে interactive
    মাস্টারি সেশন শুরু করে; নইলে None (display mode-এ যাবে)।"""
    try:
        qs = [q for q in mastery_questions(subject)
              if isinstance(q.get("options"), list) and len(q["options"]) == 4
              and isinstance(q.get("answer"), int)]
    except Exception:
        return None
    if len(qs) < 3:
        return None
    qs = qs[:5]
    st = {"subject": subject, "idx": 0, "score": 0, "total": len(qs),
          "questions": qs}
    _study_save(_MASTERY_FILE, st)
    return ("🏆 মাস্টারি টেস্ট শুরু হলো! মোট " + _bn_num(st["total"]) +
            "টি প্রশ্ন — একে একে উত্তর দাও।\n\n" + _mastery_fmt(st))


def mastery_active():
    return _mastery_load() is not None


def mastery_answer(text):
    st = _mastery_load()
    if not st:
        return None
    if "মাস্টারি থামাও" in text or "মাস্টারি বন্ধ" in text:
        _study_delete(_MASTERY_FILE)
        return "মাস্টারি টেস্ট থামিয়ে দিলাম। আবার চাইলে বলো: 'মাস্টারি টেস্ট <বিষয়>'।"
    q = st["questions"][st["idx"]]
    picked = _parse_answer(text, q)
    if picked is None:
        return None
    correct = int(q["answer"])
    if picked == correct:
        st["score"] += 1
        fb = f"✅ ঠিক হয়েছে! সঠিক উত্তর: {_OPT_LETTERS[correct]}) {q['options'][correct]}"
    else:
        fb = (f"❌ ভুল হয়েছে। তুমি দিয়েছ: {_OPT_LETTERS[picked]}) {q['options'][picked]}\n"
              f"সঠিক উত্তর: {_OPT_LETTERS[correct]}) {q['options'][correct]}")
    st["idx"] += 1
    if st["idx"] >= len(st["questions"]):
        verdict = mastery_grade(st["score"], st["total"])
        out = (fb + f"\n\n🏁 মাস্টারি টেস্ট শেষ! স্কোর: "
               f"{_bn_num(st['score'])}/{_bn_num(st['total'])}\n" + verdict)
        _study_delete(_MASTERY_FILE)
        return out
    _study_save(_MASTERY_FILE, st)
    return fb + "\n\n" + _mastery_fmt(st)


# ------------------------------------------------------------- TTS voice
# Best free Bangla female voice: Microsoft Edge TTS, bn-BD-NabanitaNeural
# (natural female). Needs the free `edge-tts` tool on Bhaiya's laptop —
# start-sokhi.bat installs it in the background on first run. If it is
# not there, this returns None and the browser's own voice is used.

VOICE_STATE = {"engine": "", "error": "", "note": ""}

_EDGE_INSTALL_FLAG = DATA / ".edge-tts-install-tried"
_edge_install_started = False


def _edge_available():
    """True when the free edge-tts tool can actually be run: either the
    `edge-tts` executable is on PATH or the `edge_tts` python module is
    importable (make_tts tries both invocation styles)."""
    if shutil.which("edge-tts") or shutil.which("edge-tts.exe"):
        return True
    try:
        import importlib.util
        return importlib.util.find_spec("edge_tts") is not None
    except Exception:
        return False


def ensure_edge_tts():
    """If edge-tts is missing, retry `pip install edge-tts` ONCE in a
    background daemon thread (same idea as the start-sokhi.bat marker:
    a flag file in data/ marks that the attempt was made, so we never
    spawn installers repeatedly). Silent on failure. Lazy-triggered from
    /api/status, /api/tts_test and make_tts_audio — main() untouched.
    Returns True when edge-tts is already available."""
    global _edge_install_started
    if _edge_available():
        return True
    if _edge_install_started or _EDGE_INSTALL_FLAG.exists():
        return False
    _edge_install_started = True
    try:
        _EDGE_INSTALL_FLAG.write_text(
            datetime.now().isoformat(timespec="seconds"), encoding="utf-8")
    except Exception:
        pass

    def _install():
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "edge-tts"],
                           capture_output=True, text=True, timeout=600)
        except Exception:
            pass  # silent by design — Google/browser voices keep working

    try:
        threading.Thread(target=_install, daemon=True).start()
    except Exception:
        pass
    return False


def voice_identity(rate=None, pitch=None, cfg=None):
    """F9 signature voice — the ONE place voice/rate/pitch come from, so
    every engine (Edge, Google, and the values reported to the browser)
    speaks with the same identity.

    `rate` here is NOT an absolute rate: it is the mood adjustment sent by
    the page (JS moodRate(), e.g. '-16%' when Bhaiya sounds tired/sad).
    Final rate% = preset% + (voice_rate - 1) * 100 + mood_adjust%,
    clamped to [-12%, +25%]: total slowdown NEVER below -12%.

    `pitch`: an explicit value, when given, is the absolute pitch;
    otherwise the preset pitch from config is used (clamped [-20%, +20%]
    as a safety bound). Voice name always comes from config tts_voice."""
    cfg = cfg if cfg is not None else get_config()
    preset_pct = _parse_pct(cfg.get("tts_rate", "-3%"), -3.0)
    slider = _clamp_voice_rate(cfg.get("voice_rate", 1.0))
    mood_pct = _parse_pct(rate, 0.0) if rate is not None else 0.0
    final_pct = preset_pct + (slider - 1.0) * 100.0 + mood_pct
    final_pct = round(max(-12.0, min(25.0, final_pct)), 2)
    if pitch is not None:
        pitch_pct = _parse_pct(pitch, 4.0)
    else:
        pitch_pct = _parse_pct(cfg.get("tts_pitch", "+4%"), 4.0)
    pitch_pct = max(-20.0, min(20.0, pitch_pct))
    return {"voice": cfg.get("tts_voice", "bn-BD-NabanitaNeural"),
            "rate": _fmt_pct(final_pct), "pitch": _fmt_pct(pitch_pct),
            "rate_pct": final_pct, "pitch_pct": pitch_pct,
            "voice_rate": slider, "preset": cfg.get("tts_preset", "মিষ্টি")}


def tts_engine_status():
    """কণ্ঠের অবস্থা — কোন ইঞ্জিন + কোন গলা শেষবার বলেছে (বা বলবে),
    পরিষ্কার বাংলায়, যাতে নিজে যাচাই করা যায় নীরবে ব্রাউজার-ফলব্যাকে
    আছি কিনা। Gemini ফলব্যাকের নোট থাকলে শেষে যোগ হয়।"""
    cfg = get_config()
    pref = (cfg.get("tts_engine") or "edge").strip().lower()
    ident = voice_identity(cfg=cfg)
    last = VOICE_STATE.get("engine", "")
    gvoice = cfg.get("gemini_voice") or "Aoede"
    if gvoice not in GEMINI_TTS_VOICES:
        gvoice = "Aoede"
    if last == "gemini":
        s = f"Gemini কণ্ঠ — {gvoice} (শেষবার এই গলাতেই বলেছি)"
    elif last == "edge-নাবনিতা":
        s = f"Edge — {ident['voice']} (আসল গলা)"
    elif last == "google-বাংলা":
        s = "Google fallback — Edge পাওয়া যাচ্ছে না"
    elif last == "browser":
        s = "ব্রাউজারের গলা (ডিভাইসের নিজের কণ্ঠ — শেষবার এটাই বলেছে)"
    elif pref == "gemini":
        if (cfg.get("gemini_api_key") or "").strip():
            s = f"Gemini কণ্ঠ — {gvoice} (বেছে দেওয়া; এই সেশনে এখনো বলেনি)"
        else:
            s = (f"Gemini কণ্ঠ — {gvoice} বেছে দেওয়া, কিন্তু Gemini key "
                 "বসানো নেই — Edge/Google গলা চলবে")
    elif pref == "browser":
        s = "ব্রাউজারের গলা (বেছে দেওয়া — ডিভাইসের নিজের কণ্ঠ)"
    elif VOICE_STATE.get("error"):
        s = "Browser voice (শেষ আশ্রয়)"
    elif _edge_available():
        s = f"Edge — {ident['voice']} (আসল গলা)"
    else:
        s = "Google fallback — Edge পাওয়া যাচ্ছে না"
    _last_family = {"gemini": "gemini", "edge-নাবনিতা": "edge",
                    "google-বাংলা": "edge", "browser": "browser"}.get(last, "")
    if _last_family and _last_family != pref:
        if pref == "gemini":
            s += (f"; এখন বেছে দেওয়া: Gemini কণ্ঠ — {gvoice}"
                  + ("" if (cfg.get("gemini_api_key") or "").strip()
                     else " (কিন্তু key নেই — Edge/Google চলবে)"))
        elif pref == "browser":
            s += "; এখন বেছে দেওয়া: ব্রাউজারের গলা"
        else:
            s += f"; এখন বেছে দেওয়া: Edge — {ident['voice']}"
    _note = (VOICE_STATE.get("note") or "").strip()
    if _note:
        s += " ⚠️ " + _note
    return s


def _tts_edge(text, out_file, rate=None, pitch=None):
    # rate/pitch arriving here are FINAL, already resolved + clamped by
    # voice_identity() in make_tts_audio; when called directly without
    # them, resolve the same identity here (no mood adjustment).
    ident = voice_identity()
    voice = ident["voice"]
    rate = rate if rate is not None else ident["rate"]
    pitch = pitch if pitch is not None else ident["pitch"]
    candidates = []
    exe = shutil.which("edge-tts") or shutil.which("edge-tts.exe")
    if exe:
        candidates.append([exe])
    candidates.append([sys.executable, "-m", "edge_tts"])
    last = "edge-tts পাওয়া যায়নি"
    for cmd in candidates:
        try:
            r = subprocess.run(cmd + ["--voice", voice,
                                      "--rate=" + rate,
                                      "--pitch=" + pitch,
                                      "--text", text, "--write-media", str(out_file)],
                               capture_output=True, text=True, timeout=30)
            if r.returncode == 0 and out_file.exists() and out_file.stat().st_size > 1000:
                return True
            last = (r.stderr or "returncode " + str(r.returncode))[-200:]
        except Exception as e:
            last = str(e)
    raise RuntimeError("Edge গলা: " + last)


def _tts_google(text, out_file, rate=None, pitch=None):
    # Google's free translate_tts endpoint has NO pitch control and only a
    # best-effort speed hint (ttsspeed). We still pass the SAME clamped,
    # identity-resolved rate as every other engine (as ttsspeed, capped at
    # 1.0 because the endpoint ignores >1) and record the resolved
    # rate/pitch in VOICE_STATE so status/logs show what was intended.
    # Honest limit: Google may ignore ttsspeed entirely — pitch cannot be
    # applied on this engine at all.
    ident = voice_identity()
    rate = rate if rate is not None else ident["rate"]
    pitch = pitch if pitch is not None else ident["pitch"]
    VOICE_STATE.update(rate=rate, pitch=pitch)
    speed = max(0.24, min(1.0, 1.0 + _parse_pct(rate, 0.0) / 100.0))
    q = urllib.parse.quote(text)
    url = ("https://translate.google.com/translate_tts?ie=UTF-8&q=" + q +
           "&tl=bn&client=tw-ob&ttsspeed=" + f"{speed:.2f}")
    data = http_get_bytes(url, 20)
    if len(data) < 2000:
        raise RuntimeError("Google গলা ছোট/খালি সাড়া দিল")
    out_file.write_bytes(data)
    return True


# ------------------------------------------------- Gemini TTS (v1.9.2)
# Gemini-র নিজের কণ্ঠ — এই মুহূর্তে সবচেয়ে প্রাণবন্ত ফ্রি পথ। চ্যাটের
# মাথার একই ফ্রি Gemini key দিয়ে চলে (আলাদা key লাগে না)। API কাঁচা
# PCM (16-bit, 24 kHz, mono) দেয় — stdlib wave দিয়ে WAV বানিয়ে অন্য
# ইঞ্জিনের মতোই ফাইল ফেরত দেওয়া হয়, তাই পেজের speak() পথ আর v1.9.1
# echo guard হুবহু একই থাকে।
# সৎ সীমা: Gemini TTS rate/pitch প্যারামিটার নেয় না — গতি স্লাইডার
# শুধু Edge/Google-এ কাজ করে; Gemini-র গতি/ভাব কণ্ঠের নিজের ধরনে থাকে।

GEMINI_TTS_MODEL_DEFAULT = "gemini-2.5-flash-preview-tts"
GEMINI_TTS_SAMPLE_RATE = 24000

# ফলব্যাক-নোট (VOICE_STATE["note"]-এ থাকে): engine=gemini বেছে দেওয়া
# থাকলেও key না থাকলে / API সাড়া না দিলে নোটটা status লাইন আর
# ডাক্তার-রিপোর্টে দেখা যায় — চ্যাটে বারবার আসে না। Gemini সফল হলেই
# নোট মোছে যায়।
_GEMINI_TTS_NOTE_NOKEY = ("Gemini কণ্ঠ বেছে দেওয়া আছে, কিন্তু Gemini key বসানো নেই — "
                          "আপাতত অন্য গলায় বলছি। Settings-এ ফ্রি Gemini key বসালেই Gemini কণ্ঠ চলবে।")


def _gemini_tts_note_fail(winner_label):
    return ("Gemini কণ্ঠ এখন সাড়া দিচ্ছে না — আপাতত " + winner_label +
            " গলায় বলছি। পরের বার নিজে থেকেই আবার Gemini চেষ্টা করব।")


def _tts_gemini(text, out_file, rate=None, pitch=None):
    # rate/pitch এখানে ইচ্ছে করেই ব্যবহার হয় না (উপরের সৎ সীমা দেখো)।
    # সফল হলে out_file-এ বৈধ WAV লিখে True; নইলে RuntimeError —
    # make_tts_audio তখন পরের ইঞ্জিনে নামে। key কখনো error-এ যায় না:
    # key শুধু header-এ থাকে, URL/body/log-এ নয়।
    import base64
    import wave
    cfg = get_config()
    key = (cfg.get("gemini_api_key") or "").strip()
    if not key:
        raise RuntimeError("Gemini key বসানো নেই")
    voice = cfg.get("gemini_voice") or "Aoede"
    if voice not in GEMINI_TTS_VOICES:
        voice = "Aoede"
    model = (cfg.get("gemini_tts_model") or GEMINI_TTS_MODEL_DEFAULT).strip() \
        or GEMINI_TTS_MODEL_DEFAULT
    body = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": voice}}}},
    }
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent")
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        detail = str(e)
        try:
            if hasattr(e, "read"):
                detail += " " + e.read().decode("utf-8", errors="ignore")[:200]
        except Exception:
            pass
        raise RuntimeError("Gemini কণ্ঠ: " + detail[:250])
    b64 = ""
    try:
        for _p in data["candidates"][0]["content"]["parts"]:
            _in = _p.get("inlineData") or _p.get("inline_data") or {}
            if _in.get("data"):
                b64 = _in["data"]
                break
    except Exception:
        b64 = ""
    if not b64:
        raise RuntimeError("Gemini কণ্ঠ খালি সাড়া দিল (অডিও পাইনি)")
    try:
        pcm = base64.b64decode(b64)
    except Exception:
        raise RuntimeError("Gemini কণ্ঠের অডিও পড়া গেল না")
    if len(pcm) < 2000:
        raise RuntimeError("Gemini কণ্ঠ ছোট/খালি অডিও দিল")
    with wave.open(str(out_file), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(GEMINI_TTS_SAMPLE_RATE)
        w.writeframes(pcm)
    return True


def make_tts_audio(text, rate=None, pitch=None):
    # One call = one text = one request per engine (no server-side
    # chunking — short replies are never split; the 600-char cap is a
    # safety trim only, and the page's own chunking is a client concern).
    # `rate` = mood adjustment (JS moodRate); voice_identity() folds it
    # into the final clamped rate/pitch used by the Edge/Google engines
    # (Gemini TTS rate/pitch নেয় না — _tts_gemini-র নোট দেখো).
    #
    # v1.9.2: engine পছন্দ (cfg tts_engine) —
    #   "gemini" : Gemini কণ্ঠ আগে (ক্যাশ, তারপর live); key না থাকলে /
    #              API ব্যর্থ হলে Edge → Google চেইনে নামে আর
    #              VOICE_STATE["note"]-এ সৎ বাংলা নোট থাকে (status
    #              লাইন + ডাক্তারে দেখা যায়; Gemini সফল হলে মোছে)।
    #   "edge"   : আগের আচরণ (Edge → Google, একই fallback order)।
    #   "browser": সার্ভার অডিও বানায় না — None ফেরত যায়; /api/tts
    #              তখন HTTP 500 দেয়, পেজ নিজের speechSynthesis
    #              গলায় বলে (ডিভাইসের কণ্ঠ)।
    # ক্যাশ ইঞ্জিনভেদে আলাদা ফাইল (Gemini=.wav, বাকিরা=.mp3), হ্যাশে
    # ইঞ্জিন + গলার নাম থাকে — ইঞ্জিন/গলা বদলালে পুরোনো ফাইল মিলবে না।
    import hashlib
    text = (text or "").strip()[:600]
    if not text:
        return None
    cfg = get_config()
    pref = (cfg.get("tts_engine") or "edge").strip().lower()
    if pref not in ("edge", "gemini", "browser"):
        pref = "edge"
    ident = voice_identity(rate, pitch, cfg)
    if pref == "browser":
        VOICE_STATE.update(engine="browser", error="", note="",
                           rate=ident["rate"], pitch=ident["pitch"])
        return None
    TTS_CACHE.mkdir(parents=True, exist_ok=True)
    if not _edge_available():
        ensure_edge_tts()
    gvoice = cfg.get("gemini_voice") or "Aoede"
    if gvoice not in GEMINI_TTS_VOICES:
        gvoice = "Aoede"

    def _cache_file(engine_id, ext, vlabel):
        h = hashlib.md5(("v5|" + engine_id + "|" + vlabel + "|" +
                         ident["rate"] + "|" + ident["pitch"] + "|" +
                         text).encode("utf-8")).hexdigest()
        return TTS_CACHE / f"{h}{ext}"

    def _hit(engine_id, ext, vlabel):
        f = _cache_file(engine_id, ext, vlabel)
        if f.exists() and f.stat().st_size > 1000:
            return f
        return None

    def _drop(engine_id, ext, vlabel):
        try:
            f = _cache_file(engine_id, ext, vlabel)
            if f.exists():
                f.unlink()
        except Exception:
            pass

    errors = []
    winner = ""
    winner_file = None

    # ধাপ ১: Gemini — শুধু বেছে দেওয়া থাকলে (ক্যাশ, তারপর live)।
    if pref == "gemini":
        f = _hit("gemini", ".wav", gvoice)
        if f:
            winner, winner_file = "gemini", f
        else:
            try:
                out_file = _cache_file("gemini", ".wav", gvoice)
                if _tts_gemini(text, out_file, ident["rate"], ident["pitch"]):
                    winner, winner_file = "gemini", out_file
            except Exception as e:
                errors.append(str(e))
                _drop("gemini", ".wav", gvoice)

    # ধাপ ২: Edge → Google — ক্যাশ আগে, তারপর live (আগের ক্রমই)।
    if not winner:
        for engine_id, fn in (("edge-নাবনিতা", _tts_edge),
                              ("google-বাংলা", _tts_google)):
            f = _hit(engine_id, ".mp3", ident["voice"])
            if f:
                winner, winner_file = engine_id, f
                break
            try:
                out_file = _cache_file(engine_id, ".mp3", ident["voice"])
                if fn(text, out_file, ident["rate"], ident["pitch"]):
                    winner, winner_file = engine_id, out_file
                    break
            except Exception as e:
                errors.append(str(e))
                _drop(engine_id, ".mp3", ident["voice"])

    if winner:
        VOICE_STATE.update(engine=winner, error="",
                           rate=ident["rate"], pitch=ident["pitch"])
        if winner == "gemini" or pref != "gemini":
            VOICE_STATE["note"] = ""
        else:
            _label = "Edge" if winner == "edge-নাবনিতা" else "Google"
            VOICE_STATE["note"] = (
                _GEMINI_TTS_NOTE_NOKEY
                if not (cfg.get("gemini_api_key") or "").strip()
                else _gemini_tts_note_fail(_label))
        return winner_file

    VOICE_STATE.update(engine="", error=" | ".join(errors)[:300])
    if pref == "gemini":
        VOICE_STATE["note"] = (
            _GEMINI_TTS_NOTE_NOKEY
            if not (cfg.get("gemini_api_key") or "").strip()
            else _gemini_tts_note_fail("ব্রাউজারের"))
    try:
        (DATA / "voice-error.log").write_text(
            f"{datetime.now().isoformat(timespec='seconds')}\n" + VOICE_STATE["error"],
            encoding="utf-8")
    except Exception:
        pass
    return None


# ------------------------------------------------------------- PC actions
# Allow-list ONLY. Chat text can never build a shell command.

APPS_WINDOWS = {
    "notepad": "notepad.exe", "calculator": "calc.exe", "paint": "mspaint.exe",
    "ক্যালকুলেটর": "calc.exe", "নোটপ্যাড": "notepad.exe",
}
SITES = {
    "youtube": "https://www.youtube.com", "ইউটিউব": "https://www.youtube.com",
    "facebook": "https://www.facebook.com", "ফেসবুক": "https://www.facebook.com",
    "google": "https://www.google.com", "গুগল": "https://www.google.com",
    "gmail": "https://mail.google.com", "জিমেইল": "https://mail.google.com",
}

_pending_confirm = {"action": None}


def pc_open(target):
    t = target.strip().lower()
    for name, url in SITES.items():
        if name in t:
            webbrowser.open(url)
            return f"খুলে দিলাম ভাইয়া — {name}।"
    if sys.platform.startswith("win"):
        for name, exe in APPS_WINDOWS.items():
            if name in t:
                subprocess.Popen([exe])
                return f"খুলে দিলাম ভাইয়া — {name}।"
    if t.startswith("http") or "." in t:
        webbrowser.open(t if t.startswith("http") else "https://" + t)
        return "ওয়েবসাইটটা খুলে দিলাম ভাইয়া।"
    return "ভাইয়া, এটা খোলার অনুমতি আমার তালিকায় নেই। YouTube, Facebook, Google, Gmail, Notepad, Calculator — এগুলো পারি।"


def system_info():
    import platform
    info = [f"সিস্টেম: {platform.system()} {platform.release()}",
            f"প্রসেসর কোর: {os.cpu_count()}"]
    try:
        if sys.platform.startswith("win"):
            out = subprocess.check_output(["wmic", "OS", "get", "FreePhysicalMemory,TotalVisibleMemorySize", "/value"], text=True, timeout=8)
            info.append("RAM তথ্য পেয়েছি (Windows)।")
        else:
            with open("/proc/meminfo") as f:
                info.append(f.readline().strip())
    except Exception:
        pass
    return "ভাইয়া, তোমার PC-র অবস্থা:\n" + "\n".join("• " + i for i in info)


# -*- coding: utf-8 -*-
# =============================================================================
# N8 — ১২টি দৈনন্দিন ভয়েস কমান্ড (Desktop Sokhi v1.0)
# -----------------------------------------------------------------------------
# পেস্ট করার জায়গা: sokhi.py-র PC-actions অংশে (pc_open / system_info-এর
# পরে), handle_message-এর আগে। handle_message-এ pc_open ডাকার আগেই এক লাইন
# যোগ করতে হবে:
#       _n8_out = n8_handle(text, low)
#       if _n8_out:
#           return _n8_out
# (n8 শুধু নিজের ১২টি প্যাটার্ন ধরলে উত্তর দেয়; বাকি সব ক্ষেত্রে None
#  ফেরত দেয়, যাতে বিদ্যমান আচরণ একদম বদলায় না।)
#
# ব্যবহারযোগ্য গ্লোবাল (sokhi.py-তে আগেই আছে): sys, os, re, subprocess,
# webbrowser, urllib.parse, Path, DATA, get_config(), get_memory(), shutil।
# নিরাপত্তা: কোথাও shell-মোড ব্যবহার হয়নি; subprocess সবসময় আর্গুমেন্ট-লিস্টে;
# ফাইল মোছা / অ্যাপ বন্ধ — সব ধ্বংসাত্মক কাজে আগে pending + read-back
# নিশ্চিতকরণ; পরের মেসেজে 'হ্যাঁ'/'করো' থাকলেই কাজ হয়, অন্য কিছুতে বাতিল।
# ভাষা: এই ফ্র্যাগমেন্টের উত্তরে 'ভাইয়া' সম্বোধন নেই — নিরপেক্ষ/তুমি-ভঙ্গি।
# =============================================================================

import csv
import io
import os
import re
import subprocess
import sys
import time
import urllib.parse
import webbrowser
from pathlib import Path

# ------------------------------------------------------------ N8 state
_n8_pending = {"action": None, "data": None}
_n8_state = {"last_big": []}   # ৩ নম্বর কমান্ডের সর্বশেষ বড়-ফাইল তালিকা

_N8_BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

# ৫/৯ নম্বরের জন্য বাড়ানো ম্যাপ: label -> ("app", exe) বা ("site", url)
_N8_OPEN_TARGETS = {
    # sites (বিদ্যমান SITES + github যোগ)
    "gmail": ("site", "https://mail.google.com"),
    "জিমেইল": ("site", "https://mail.google.com"),
    "github": ("site", "https://github.com"),
    "গিটহাব": ("site", "https://github.com"),
    "youtube": ("site", "https://www.youtube.com"),
    "ইউটিউব": ("site", "https://www.youtube.com"),
    "facebook": ("site", "https://www.facebook.com"),
    "ফেসবুক": ("site", "https://www.facebook.com"),
    "google": ("site", "https://www.google.com"),
    "গুগল": ("site", "https://www.google.com"),
    "instagram": ("site", "https://www.instagram.com"),
    "ইনস্টাগ্রাম": ("site", "https://www.instagram.com"),
    # apps (Windows exe) + spotify ওয়েব
    "google chrome": ("app", "chrome.exe"),
    "chrome": ("app", "chrome.exe"),
    "ক্রোম": ("app", "chrome.exe"),
    "firefox": ("app", "firefox.exe"),
    "ফায়ারফক্স": ("app", "firefox.exe"),
    "notepad": ("app", "notepad.exe"),
    "নোটপ্যাড": ("app", "notepad.exe"),
    "calculator": ("app", "calc.exe"),
    "calc": ("app", "calc.exe"),
    "ক্যালকুলেটর": ("app", "calc.exe"),
    "paint": ("app", "mspaint.exe"),
    "পেইন্ট": ("app", "mspaint.exe"),
    "word": ("app", "winword.exe"),
    "ওয়ার্ড": ("app", "winword.exe"),
    "excel": ("app", "excel.exe"),
    "এক্সেল": ("app", "excel.exe"),
    "powerpoint": ("app", "POWERPNT.EXE"),
    "পাওয়ারপয়েন্ট": ("app", "POWERPNT.EXE"),
    "spotify": ("site", "https://open.spotify.com"),
    "স্পটিফাই": ("site", "https://open.spotify.com"),
}

# ৬ নম্বর: অ্যাপ বন্ধের image-name ম্যাপ
_N8_CLOSE_APPS = {
    "google chrome": "chrome.exe", "chrome": "chrome.exe", "ক্রোম": "chrome.exe",
    "firefox": "firefox.exe", "ফায়ারফক্স": "firefox.exe",
    "notepad": "notepad.exe", "নোটপ্যাড": "notepad.exe",
    "calculator": "calc.exe", "calc": "calc.exe", "ক্যালকুলেটর": "calc.exe",
    "paint": "mspaint.exe", "পেইন্ট": "mspaint.exe",
    "word": "winword.exe", "ওয়ার্ড": "winword.exe",
    "excel": "excel.exe", "এক্সেল": "excel.exe",
    "powerpoint": "POWERPNT.EXE", "পাওয়ারপয়েন্ট": "POWERPNT.EXE",
    "spotify": "Spotify.exe", "স্পটিফাই": "Spotify.exe",
    "vs code": "Code.exe", "code": "Code.exe",
}

# ৪ নম্বর: ফোল্ডার ম্যাপ (নাম -> হোমের নিচের ফোল্ডার)
_N8_FOLDERS = {
    "ডাউনলোড": "Downloads", "download": "Downloads", "downloads": "Downloads",
    "পিকচার": "Pictures", "ছবি": "Pictures", "picture": "Pictures", "pictures": "Pictures",
    "ডকুমেন্ট": "Documents", "document": "Documents", "documents": "Documents",
    "ডেস্কটপ": "Desktop", "desktop": "Desktop",
    "মিউজিক": "Music", "music": "Music",
    "ভিডিও": "Videos", "video": "Videos", "videos": "Videos",
}

# ৭ নম্বর: মুড -> YouTube সার্চ কোয়েরি
_N8_MOODS = [
    (("lo-fi", "lofi", "লোফাই", "লো-ফাই", "লো ফাই"), "lofi beats relax study", "lo-fi"),
    (("ঘুমের গান", "ঘুমের", "ঘুম পাড়ানি", "sleep"), "deep sleep relaxing music", "ঘুমের"),
    (("মন ভালো", "মন খারাপ", "হাসির গান"), "feel good happy songs", "মন ভালো করার"),
    (("মনোযোগ", "ফোকাস", "focus", "কনসেনট্রেশন", "পড়ার গান", "পড়াশোনার গান"),
     "deep focus concentration music for study", "মনোযোগের"),
    (("বৃষ্টির শব্দ", "বৃষ্টির গান", "rain sound"), "rain sounds for relaxation", "বৃষ্টির"),
]


# ------------------------------------------------------------ helpers
def _n8_is_win():
    return sys.platform.startswith("win")


def _n8_norm_digits(s):
    """বাংলা সংখ্যা -> ইংরেজি সংখ্যা (শুধু পার্সিংয়ের জন্য)।"""
    return (s or "").translate(_N8_BN_DIGITS)


def _n8_fmt_size(n):
    try:
        n = float(n)
    except Exception:
        n = 0
    if n >= 1024 ** 3:
        return f"{n / 1024 ** 3:.2f} GB"
    if n >= 1024 ** 2:
        return f"{n / 1024 ** 2:.1f} MB"
    if n >= 1024:
        return f"{n / 1024:.1f} KB"
    return f"{int(n)} B"


def _n8_sanitize_name(name):
    """ফোল্ডার/ফাইলের নাম নিরাপদ করা: /, \\, .., নিয়ন্ত্রণ-অক্ষর বাদ।"""
    name = (name or "").strip().strip('"').strip("'").strip("“”")
    name = name.replace("..", "").replace("/", "").replace("\\", "")
    name = re.sub(r'[<>:"|?*\x00-\x1f]', "", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name[:60]


def _n8_open_folder_path(path):
    """Windows-এ Explorer-এ খোলে; অন্য OS-এ পথ জানিয়ে পরিষ্কার বার্তা।"""
    if not path.exists():
        return f"ফোল্ডারটা খুঁজে পেলাম না: {path} — মনে হচ্ছে এই নামে ফোল্ডারটা নেই।"
    if _n8_is_win():
        try:
            os.startfile(str(path))  # noqa: S606 - Windows shell-open, allow-listed path
            return f"ফোল্ডারটা খুলে দিলাম: {path.name}"
        except Exception:
            try:
                subprocess.Popen(["explorer", str(path)])
                return f"ফোল্ডারটা খুলে দিলাম: {path.name}"
            except Exception:
                return f"ফোল্ডারটা খুলতে পারলাম না। পথটা হলো: {path}"
    return ("এই সিস্টেমে (Windows নয়) ফোল্ডার সরাসরি Explorer-এ খোলা যাচ্ছে না। "
            f"ফোল্ডারটার পথ হলো: {path}")


def _n8_open_one_target(label, kind, value):
    """একটা টার্গেট খোলে; (সফল কিনা, ছোট নোট) ফেরত দেয়।"""
    if kind == "site":
        try:
            webbrowser.open(value)
            return True, label
        except Exception:
            return False, label
    # app — শুধু Windows-এ
    if not _n8_is_win():
        return False, f"{label} (অ্যাপ শুধু Windows-এ খোলে)"
    try:
        subprocess.Popen([value])
        return True, label
    except Exception:
        return False, f"{label} (খুলতে পারলাম না)"


def _n8_find_open_targets(text, low):
    """লেখায় থাকা পরিচিত অ্যাপ/সাইটগুলো খোঁজে — লম্বা নাম আগে, যাতে
    'google chrome'-কে chrome+google দুটো ধরা না হয়।"""
    hay = " " + text + " "
    hay_low = " " + low + " "
    found, seen = [], set()
    for key in sorted(_N8_OPEN_TARGETS, key=len, reverse=True):
        kind, value = _N8_OPEN_TARGETS[key]
        canon = (kind, value)
        if canon in seen:
            continue
        if key in hay or key in hay_low:
            found.append((key, kind, value))
            seen.add(canon)
            hay = hay.replace(key, " ")
            hay_low = hay_low.replace(key, " ")
    return found


def _n8_search_files(needle, base, max_depth=4, limit=5, seconds=8):
    """সীমিত খোঁজ: সর্বোচ্চ ~max_depth স্তর, সময়-সীমা, সর্বোচ্চ limit ফল।"""
    needle_n = re.sub(r"[\s_\-]+", " ", needle.lower()).strip()
    if not needle_n:
        return []
    skip_dirs = {"appdata", ".cache", ".git", "node_modules", "__pycache__",
                 "$recycle.bin", "system volume information", ".local"}
    results, start = [], time.monotonic()
    base = Path(base)
    try:
        base_depth = len(base.parts)
    except Exception:
        return []
    for root, dirs, files in os.walk(str(base)):
        if time.monotonic() - start > seconds or len(results) >= limit:
            break
        depth = len(Path(root).parts) - base_depth
        if depth >= max_depth:
            dirs[:] = []
        dirs[:] = [d for d in dirs if d.lower() not in skip_dirs]
        for fn in files:
            fn_n = re.sub(r"[\s_\-]+", " ", fn.lower())
            if needle_n in fn_n:
                results.append(str(Path(root) / fn))
                if len(results) >= limit:
                    break
    return results


def _n8_big_files(folder, min_bytes, seconds=8):
    """folder-এর নিচে min_bytes-এর বড় ফাইল, সাইজ অনুযায়ী সাজিয়ে শীর্ষ ৫।"""
    found, start = [], time.monotonic()
    for root, dirs, files in os.walk(str(folder)):
        if time.monotonic() - start > seconds:
            dirs[:] = []
            break
        dirs[:] = [d for d in dirs if d.lower() not in
                   {"$recycle.bin", "system volume information", ".git"}]
        for fn in files:
            try:
                p = Path(root) / fn
                sz = p.stat().st_size
                if sz >= min_bytes:
                    found.append((sz, str(p)))
            except Exception:
                continue
    found.sort(key=lambda x: x[0], reverse=True)
    return found[:5]


def _n8_ram_top():
    """১০ নম্বর: RAM-খেকো শীর্ষ ৫ প্রসেস। Windows: tasklist; Linux: /proc।"""
    agg = {}
    if _n8_is_win():
        try:
            out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"],
                                 capture_output=True, text=True, timeout=10)
            for row in csv.reader(io.StringIO(out.stdout or "")):
                if len(row) < 5:
                    continue
                name = (row[0] or "unknown").strip()
                mem = re.sub(r"[^\d]", "", _n8_norm_digits(row[4] or ""))
                if mem:
                    agg[name] = agg.get(name, 0) + int(mem) * 1024  # KB -> B
        except Exception:
            agg = {}
    if not agg:
        # Linux fallback: /proc থেকে VmRSS যোগ করে (একই নামের প্রসেস মিলিয়ে)
        try:
            for pid_dir in Path("/proc").iterdir():
                if not pid_dir.name.isdigit():
                    continue
                try:
                    comm = (pid_dir / "comm").read_text(
                        encoding="utf-8", errors="ignore").strip() or "unknown"
                    rss_kb = 0
                    for line in (pid_dir / "status").read_text(
                            encoding="utf-8", errors="ignore").splitlines():
                        if line.startswith("VmRSS:"):
                            rss_kb = int(re.sub(r"[^\d]", "", line) or 0)
                            break
                    if rss_kb:
                        agg[comm] = agg.get(comm, 0) + rss_kb * 1024
                except Exception:
                    continue
        except Exception:
            pass
    if not agg:
        return "এই মুহূর্তে RAM-এর তথ্যটা পড়তে পারলাম না — একটু পরে আবার চেষ্টা করো।"
    top = sorted(agg.items(), key=lambda x: x[1], reverse=True)[:5]
    lines = [f"সবচেয়ে বেশি RAM খাচ্ছে {top[0][0]} ({_n8_fmt_size(top[0][1])})।",
             "শীর্ষ ৫ প্রসেস:"]
    lines += [f"• {name} — {_n8_fmt_size(size)}" for name, size in top]
    return "\n".join(lines)


def _n8_parse_phone(segment):
    """লেখা থেকে ফোন নম্বর বের করে wa.me-যোগ্য আন্তর্জাতিক রূপে আনে।"""
    if not segment:
        return None
    m = re.search(r"\+?\d[\d\s\-]{7,}\d", _n8_norm_digits(segment))
    if not m:
        return None
    digits = re.sub(r"\D", "", m.group(0))
    if len(digits) == 11 and digits.startswith("01"):
        digits = "880" + digits[1:]
    elif len(digits) == 10 and digits.startswith("1"):
        digits = "880" + digits
    if 10 <= len(digits) <= 15:
        return digits
    return None


# ------------------------------------------------------------ pending
def _n8_run_pending():
    """নিশ্চিতকরণের পর pending কাজটা চালায়।"""
    action, data = _n8_pending.get("action"), _n8_pending.get("data")
    _n8_pending["action"], _n8_pending["data"] = None, None
    if action == "delete_file":
        p = Path(data or "")
        try:
            if p.exists() and p.is_file():
                sz = _n8_fmt_size(p.stat().st_size)
                p.unlink()
                _n8_state["last_big"] = [x for x in _n8_state["last_big"]
                                          if x[1] != str(p)]
                return f"মুছে দিলাম: {p.name} ({sz} জায়গা খালি হলো)।"
            return "ফাইলটা আর খুঁজে পেলাম না — হয়তো আগেই সরে গেছে।"
        except Exception:
            return "ফাইলটা মুছতে গিয়ে সমস্যা হলো — নিজে একবার দেখে নাও।"
    if action == "close_app":
        image, label = (data or {}).get("image", ""), (data or {}).get("label", "")
        if not _n8_is_win():
            return "অ্যাপ বন্ধ করার কাজটা শুধু Windows-এ চলবে।"
        try:
            r = subprocess.run(["taskkill", "/IM", image, "/F"],
                               capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                return f"বন্ধ করে দিলাম: {label}।"
            return f"{label} মনে হচ্ছে এখন চলছেই না (বন্ধ করার কিছু পেলাম না)।"
        except Exception:
            return "বন্ধ করতে গিয়ে সমস্যা হলো — Task Manager থেকে দেখে নিতে পারো।"
    if action == "whatsapp_send":
        number = (data or {}).get("number", "")
        message = (data or {}).get("message", "")
        url = f"https://wa.me/{number}?text=" + urllib.parse.quote(message)
        try:
            webbrowser.open(url)
        except Exception:
            return f"পেজটা খুলতে পারলাম না। লিংকটা হলো: {url}"
        return ("WhatsApp-এর পেজটা খুলে দিলাম, বার্তাটা লিখে বসানো আছে। "
                "আমি সরাসরি পাঠাইনি — তুমি নিজে Send বোতাম চেপে পাঠিয়ে দাও।")
    return "কাজটা করে দিলাম।"


def _n8_pending_gate(text, low):
    """pending থাকলে: হ্যাঁ/করো -> কাজ; বাতিল/অন্য কিছু -> বাতিল বার্তা।"""
    stripped = text.strip()
    if ("বাতিল" in text or stripped in ("না", "না থাক", "থাক", "no")
            or "cancel" in low):
        _n8_pending["action"], _n8_pending["data"] = None, None
        return "বাতিল করে দিলাম — কিছু করা হয়নি।"
    if any(w in text for w in ("হ্যাঁ", "করো")) or any(
            w in low for w in ("yes", "confirm", "ok")):
        return _n8_run_pending()
    _n8_pending["action"], _n8_pending["data"] = None, None
    return "বাতিল করে দিলাম — কিছু করা হয়নি।"


# ------------------------------------------------------------ main entry
def n8_handle(text, low):
    """N8-এর ১২টি কমান্ডের প্রবেশদ্বার। মিললে উত্তরের string, না মিললে None।"""
    text = (text or "").strip()
    low = low or text.lower()
    if not text:
        return None

    # ০) আগের কোনো pending নিশ্চিতকরণ থাকলে সেটাই আগে নিষ্পত্তি করি
    if _n8_pending.get("action"):
        return _n8_pending_gate(text, low)

    # ------------------------------------------------ ১২) WhatsApp বার্তা
    if "whatsapp" in low or "হোয়াটসঅ্যাপ" in text or "হোয়াটস অ্যাপ" in text:
        colon = re.search(r"[:：]\s*(.+)$", text, re.S)
        message, head = "", text
        if colon:
            message, head = colon.group(1).strip(), text[:colon.start()]
        else:
            m_send = re.search(r"পাঠাও[:：]?\s*(.+)$", text, re.S)
            if m_send:
                message, head = m_send.group(1).strip(), text[:m_send.start()]
        target_m = re.search(
            r"(?:whatsapp|হোয়াটস\s*অ্যাপ|হোয়াটসঅ্যাপ)[\s\-এ]*(.+?)\s*(?:-কে|কে)?\s*(?:পাঠাও|পাঠিয়ে দাও|পাঠা)?$",
            head, re.I)
        target = target_m.group(1).strip(" -") if target_m else head
        target = re.sub(r"^এ\s+", "", target).strip()
        number = _n8_parse_phone(head) or _n8_parse_phone(target)
        if not message:
            return ("বার্তাটা কী হবে সেটা বলোনি। এভাবে বলো: "
                    "‘WhatsApp-এ 01XXXXXXXXX-কে পাঠাও: তোমার বার্তা’।")
        if not number:
            who = f"‘{target}’-এর " if target else ""
            return (f"{who}নম্বরটা আমার কাছে নেই — নম্বরটা দিয়ে আবার বলো, যেমন: "
                    "‘WhatsApp-এ 01XXXXXXXXX-কে পাঠাও: ...’। নাম দিয়ে সরাসরি পাঠানোর "
                    "সুবিধা এই সংস্করণে নেই।")
        _n8_pending["action"] = "whatsapp_send"
        _n8_pending["data"] = {"number": number, "message": message}
        return (f"নিশ্চিত করো তো — WhatsApp-এ {number} নম্বরে এই বার্তার পেজ খুলব:\n"
                f"“{message}”\n"
                "ঠিক থাকলে বলো ‘হ্যাঁ করো’; না হলে অন্য কিছু বললেই বাতিল হয়ে যাবে। "
                "(পেজ খুললেও Send তুমি নিজে চাপবে।)")

    # ------------------------------------------------ ১) ডেস্কটপে ফোল্ডার তৈরি
    if "ডেস্কটপ" in text and "ফোল্ডার" in text and any(
            w in text for w in ("বানাও", "তৈরি", "বানিয়ে", "বানাতে")):
        m = re.search(r"ডেস্কটপে?\s*(.+?)\s+নামে(?:র)?\s+(?:একটা\s+|একটি\s+)?ফোল্ডার", text)
        if not m:
            m = re.search(r"(.+?)\s+নামে(?:র)?\s+(?:একটা\s+|একটি\s+)?ফোল্ডার", text)
        name = _n8_sanitize_name(m.group(1)) if m else ""
        if not name:
            return "ফোল্ডারটার নামটা বুঝতে পারলাম না — এভাবে বলো: ‘ডেস্কটপে পড়াশোনা নামে ফোল্ডার বানাও’।"
        folder = Path.home() / "Desktop" / name
        try:
            if folder.exists():
                return f"‘{name}’ নামের ফোল্ডারটা ডেস্কটপে আগেই আছে: {folder}"
            folder.mkdir(parents=True, exist_ok=False)
            return f"তৈরি করে দিলাম: ডেস্কটপে ‘{name}’ ফোল্ডার।\nপথ: {folder}"
        except Exception:
            return f"ফোল্ডারটা বানাতে পারলাম না (‘{name}’) — নামটা বদলে আবার বলো।"

    # --------------------------------------- ৩-এর ধারাবাহিকতা) বড় ফাইল মোছা
    if ("মুছে" in text or "মুছো" in text or "ডিলিট" in text or "delete" in low) \
            and ("ফাইল" in text or "নম্বর" in text or _n8_state["last_big"]):
        big = _n8_state.get("last_big") or []
        if not big:
            return ("কোন ফাইলটা মুছব সেটা এখনো জানি না। আগে বলো ‘বড় ফাইল দেখাও’, "
                    "তারপর তালিকা থেকে বলো ‘১ নম্বরটা মুছে দাও’।")
        norm = _n8_norm_digits(text)
        idx = None
        m_num = re.search(r"(\d+)\s*নম্বর", norm)
        words = {"প্রথম": 0, "দ্বিতীয়": 1, "তৃতীয়": 2, "চতুর্থ": 3, "পঞ্চম": 4}
        if m_num:
            idx = int(m_num.group(1)) - 1
        else:
            for w, i in words.items():
                if w in text:
                    idx = i
                    break
        chosen = None
        if idx is not None and 0 <= idx < len(big):
            chosen = big[idx]
        else:
            for sz, pth in big:
                if Path(pth).name in text:
                    chosen = (sz, pth)
                    break
        if not chosen:
            return "তালিকার কোন ফাইলটা বুঝতে পারলাম না — নম্বর ধরে বলো, যেমন ‘২ নম্বরটা মুছে দাও’।"
        _n8_pending["action"] = "delete_file"
        _n8_pending["data"] = chosen[1]
        return (f"নিশ্চিত করো তো — এই ফাইলটা স্থায়ীভাবে মুছে ফেলব:\n"
                f"{chosen[1]} ({_n8_fmt_size(chosen[0])})\n"
                "মুছতে চাইলে বলো ‘হ্যাঁ করো’; না হলে অন্য কিছু বললেই বাতিল।")

    # ------------------------------------------------ ৬) অ্যাপ বন্ধ (নিশ্চিতকরণসহ)
    if ("বন্ধ করো" in text or "বন্ধ করে দাও" in text or "close" in low) \
            and not any(w in text for w in ("পিসি", "কম্পিউটার")) and "pc" not in low:
        hay = " " + text + " "
        hay_low = " " + low + " "
        hit = None
        for key in sorted(_N8_CLOSE_APPS, key=len, reverse=True):
            if key in hay or key in hay_low:
                hit = (key, _N8_CLOSE_APPS[key])
                break
        if hit:
            if not _n8_is_win():
                return (f"অ্যাপ বন্ধ করার কাজটা শুধু Windows-এ চলবে — "
                        f"এই সিস্টেমে {hit[0]} বন্ধ করা যাচ্ছে না।")
            _n8_pending["action"] = "close_app"
            _n8_pending["data"] = {"image": hit[1], "label": hit[0]}
            return (f"নিশ্চিত করো তো — {hit[0]} বন্ধ করে দেব (না-সেভ-করা কাজ থাকলে "
                    "হারিয়ে যেতে পারে)।\nবলো ‘হ্যাঁ করো’; না হলে অন্য কিছু বললেই বাতিল।")
        # চেনা অ্যাপ না মিললে n8 চুপ থাকবে (বিদ্যমান PC-বন্ধের ধাঁচ চলবে)

    # ------------------------------------------------ ৩) বড় ফাইল শিকার
    size_m = re.search(r"(\d+(?:\.\d+)?)\s*(এমবি|mb|জিবি|gb|কেবি|kb)",
                       _n8_norm_digits(low if any(c.isascii() for c in low) else text), re.I)
    size_m = size_m or re.search(
        r"(\d+(?:\.\d+)?)\s*(এমবি|জিবি|কেবি)", _n8_norm_digits(text))
    if "বড় ফাইল" in text or (size_m and "ফাইল" in text):
        threshold = 100 * 1024 * 1024  # নির্দিষ্ট না থাকলে 100 MB+
        if size_m:
            val, unit = float(size_m.group(1)), size_m.group(2).lower()
            mult = 1024 ** 3 if unit in ("জিবি", "gb") else (
                1024 if unit in ("কেবি", "kb") else 1024 ** 2)
            threshold = int(val * mult)
        if "ডেস্কটপ" in text:
            folder = Path.home() / "Desktop"
        elif "ভিডিও" in text:
            folder = Path.home() / "Videos"
        else:
            folder = Path.home() / "Downloads"
            if not folder.exists():
                folder = Path.home()
        if not folder.exists():
            return f"যে ফোল্ডারটা স্ক্যান করব সেটাই পেলাম না: {folder}"
        big = _n8_big_files(folder, threshold)
        _n8_state["last_big"] = big
        if not big:
            return (f"{folder.name} ফোল্ডারে {_n8_fmt_size(threshold)}-এর বড় কোনো "
                    "ফাইল পেলাম না — জায়গা বেশ পরিষ্কারই আছে।")
        lines = [f"{folder.name}-এ {_n8_fmt_size(threshold)}+ বড় ফাইল (বড় থেকে ছোট):"]
        for i, (sz, pth) in enumerate(big, 1):
            lines.append(f"{i}. {Path(pth).name} — {_n8_fmt_size(sz)}")
        lines.append("মুছতে চাইলে বলো ‘১ নম্বরটা মুছে দাও’ — তবে মুছার আগে "
                     "আবার তোমার নিশ্চিতকরণ নেব, এমনি এমনি কিছু মুছব না।")
        return "\n".join(lines)

    # ------------------------------------------------ ২) হারানো ফাইল খোঁজা
    if ("খুঁজে দাও" in text or "খুঁজে দাও তো" in text or "কোথায় আছে" in text
            or "কোথায়" in text) and ("ফাইল" in text or "কোথায় আছে" in text):
        m = re.search(r"(.+?)\s*ফাইল(?:টা|টি)?\s*(?:খুঁজে দাও|খোঁজো|খুঁজো|কোথায়)", text)
        if not m:
            m = re.search(r"(.+?)\s*(?:কোথায় আছে|কোথায়)\s*\??\s*$", text)
        name = ""
        if m:
            name = m.group(1)
            for junk in ("আমার", "একটা", "একটি", "দ্য", "the"):
                name = name.replace(junk, " ")
        name = _n8_sanitize_name(name) if name else ""
        # স্যানিটাইজে এক্সটেনশনের ডট মুছে যেতে পারে; আসল নামে ডট থাকলে সেটা রাখি
        if m and "." in m.group(1):
            name = m.group(1).strip().strip('"').strip("'")
            for junk in ("আমার ", "একটা "):
                name = name.replace(junk, "")
            name = name.strip()
        if not name:
            return "কোন ফাইলটা খুঁজব — নামটা বলো, যেমন ‘রিপোর্ট ফাইলটা খুঁজে দাও’।"
        hits = _n8_search_files(name, Path.home())
        if not hits and " " in name:
            longest = max(name.split(), key=len)
            if len(longest) >= 3:
                hits = _n8_search_files(longest, Path.home())
        if not hits:
            return (f"‘{name}’ নামে কোনো ফাইল হোম ফোল্ডারের কাছাকাছি (৪ স্তর পর্যন্ত) "
                    "পেলাম না। নামের বানানটা একটু বদলে বা এক্সটেনশনসহ (যেমন .pdf) বলো।")
        return f"‘{name}’ খুঁজে পেয়েছি:\n" + "\n".join("• " + h for h in hits)

    # ------------------------------------------------ ১০) RAM খাচ্ছে কে?
    if ("ram" in low or "র‍্যাম" in text or "র্যাম" in text) and any(
            w in text for w in ("খাচ্ছে", "বেশি", "কে", "ব্যবহার", "খায়")):
        return _n8_ram_top()

    # ------------------------------------------------ ১১) ডিস্কে জায়গা কত বাকি?
    if any(w in text for w in ("স্টোরেজ", "সি ড্রাইভ", "জায়গা কত", "ডিস্ক")) \
            or "c drive" in low or "c:" in low:
        if any(w in text for w in ("বাকি", "খালি", "কত", "আছে")) or "c drive" in low:
            import shutil as _sh
            anchor = "C:\\" if _n8_is_win() else (Path.home().anchor or "/")
            try:
                total, used, free = _sh.disk_usage(anchor)
            except Exception:
                return "ডিস্কের জায়গার হিসাবটা এই মুহূর্তে পড়তে পারলাম না।"
            drive = "C drive" if _n8_is_win() else "মূল ডিস্ক"
            return (f"{drive}-এ মোট {_n8_fmt_size(total)}, "
                    f"খালি আছে {_n8_fmt_size(free)} "
                    f"(ব্যবহার হয়েছে {_n8_fmt_size(used)})।")

    # ------------------------------------------------ ৭+১১-ক) YouTube সার্চ বনাম মুড
    yt_present = "ইউটিউব" in text or "youtube" in low
    if yt_present and ("সার্চ" in text or "search" in low):
        topic = text
        for junk in ("ইউটিউবে", "ইউটিউব", "youtube", "সার্চ করো", "সার্চ করে দাও",
                     "সার্চ", "search", "দেখাও", "খোঁজো", "করো"):
            topic = re.sub(re.escape(junk), " ", topic, flags=re.I)
        topic = re.sub(r"\s+", " ", topic).strip(" :：-")
        if not topic:
            webbrowser.open("https://www.youtube.com")
            return "YouTube খুলে দিলাম — কী সার্চ করবে সেটা বললেই খুঁজে দেব।"
        webbrowser.open("https://www.youtube.com/results?search_query="
                        + urllib.parse.quote(topic))
        return f"YouTube-এ ‘{topic}’ সার্চ করে দিলাম।"

    # ৭) মুড অনুযায়ী গান (YouTube)
    mood_hit = None
    for keys, query, label in _N8_MOODS:
        if any(k in low or k in text for k in keys):
            mood_hit = (query, label)
            break
    if mood_hit and (yt_present or "গান" in text or "চালাও" in text
                    or "বাজাও" in text or "শোনাও" in text or "সাউন্ড" in text
                    or any(k in low for k in ("lo-fi", "lofi"))):
        webbrowser.open("https://www.youtube.com/results?search_query="
                        + urllib.parse.quote(mood_hit[0]))
        return f"{mood_hit[1]} গান/সাউন্ড YouTube-এ চালিয়ে দিলাম — উপভোগ করো।"

    if yt_present and ("দেখাও" in text or "খোঁজো" in text or "চালাও" in text):
        topic = text
        for junk in ("ইউটিউবে", "ইউটিউব", "youtube", "দেখাও", "খোঁজো",
                     "চালাও", "বাজাও", "করো"):
            topic = re.sub(re.escape(junk), " ", topic, flags=re.I)
        topic = re.sub(r"\s+", " ", topic).strip(" :：-")
        if topic:
            webbrowser.open("https://www.youtube.com/results?search_query="
                            + urllib.parse.quote(topic))
            return f"YouTube-এ ‘{topic}’ দেখিয়ে দিলাম।"

    # ------------------------------------------------ ৪) ফোল্ডার খোলা
    if ("খোলো" in text or "খুলে দাও" in text or "open" in low) and (
            "ফোল্ডার" in text or any(k in text or k in low for k in _N8_FOLDERS)):
        for key in sorted(_N8_FOLDERS, key=len, reverse=True):
            if key in text or key in low:
                return _n8_open_folder_path(Path.home() / _N8_FOLDERS[key])
        if "ফোল্ডার" in text:
            return None  # অচেনা ফোল্ডারের নাম — বিদ্যমান আচরণে ছেড়ে দিলাম

    # --------------------------- ৫+৯) একসাথে একাধিক অ্যাপ/সাইট খোলা
    # শুধু 'আর/এবং/and/,' দিয়ে যুক্ত প্যাটার্নই ধরি — একটা খোলার কাজ
    # বিদ্যমান pc_open-এর কাছেই থাকে, সংঘর্ষ হয় না।
    has_joiner = (" আর " in f" {text} " or "এবং" in text or " and " in low
                  or "," in text or "，" in text or "+" in text)
    if has_joiner and ("খোলো" in text or "খুলে দাও" in text or "open" in low):
        targets = _n8_find_open_targets(text, low)
        if len(targets) >= 2:
            done, failed = [], []
            for label, kind, value in targets:
                ok, note = _n8_open_one_target(label, kind, value)
                (done if ok else failed).append(note)
            if done:
                msg = "একসাথে খুলে দিলাম: " + ", ".join(done) + "।"
                if failed:
                    msg += "\nহয়নি: " + ", ".join(failed) + "।"
                return msg
            return "কিছুই খুলতে পারলাম না — হয়নি: " + ", ".join(failed) + "।"
        # ২টার কম মিললে একটা-খোলার পুরনো পথেই যাক
        return None

    return None


# ------------------------------------------------------- plugins (skills)
# Sokhi writes plugins from a SAFE template: a plugin can only reply with
# text (with {time} {date} {name} variables). System imports are rejected.

PLUGIN_TEMPLATE = '''# -*- coding: utf-8 -*-
"""Sokhi plugin: {name} — auto-generated {today}, sandbox-tested before install."""
TRIGGER = {trigger!r}
RESPONSE = {response!r}

def handle(text, ctx):
    if TRIGGER in text.lower():
        return (RESPONSE.replace("{{time}}", ctx["time"])
                         .replace("{{date}}", ctx["date"])
                         .replace("{{name}}", ctx["name"]))
    return None

def self_test():
    ctx = {{"time": "10:00 AM", "date": "today", "name": "ভাইয়া"}}
    out = handle("x " + TRIGGER + " y", ctx)
    assert out and len(out) > 0
    return True
'''

BANNED = ("import os", "import sys", "import subprocess", "import socket",
          "import shutil", "__import__", "eval(", "exec(", "open(")


def load_plugins():
    plugins = []
    for f in sorted(PLUGINS.glob("plugin_*.py")):
        try:
            code = f.read_text(encoding="utf-8")
            if any(b in code for b in BANNED):
                continue
            ns = {}
            exec(compile(code, str(f), "exec"), ns)
            if "handle" in ns:
                plugins.append(ns)
        except Exception:
            continue
    return plugins


def create_plugin(name, trigger, response):
    """Sokhi writes her own code, tests it in a sandbox, then installs it."""
    safe = re.sub(r"[^a-z0-9_]+", "_", name.lower()).strip("_") or "skill"
    fname = f"plugin_{safe}.py"
    code = PLUGIN_TEMPLATE.format(name=name, trigger=trigger.lower(),
                                  response=response, today=str(date.today()))
    if any(b in code for b in BANNED):
        return None, "কোডে নিষিদ্ধ জিনিস ছিল, বাতিল করলাম ভাইয়া।"
    draft = DRAFTS / fname
    draft.write_text(code, encoding="utf-8")
    # sandbox test: fresh python process, 6 second limit, no network use in it
    try:
        out = subprocess.run(
            [sys.executable, "-c",
             f"import importlib.util; s=importlib.util.spec_from_file_location('p', r'{draft}');"
             "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print(m.self_test())"],
            capture_output=True, text=True, timeout=6)
        if out.returncode != 0 or "True" not in out.stdout:
            return None, "টেস্টে পাস করেনি ভাইয়া, তাই ইনস্টল করিনি। " + (out.stderr or "")[-200:]
    except Exception as e:
        return None, f"টেস্ট চালাতে পারিনি ভাইয়া: {e}"
    shutil.move(str(draft), str(PLUGINS / fname))
    register_capability(f"plugin:{safe}", f"যখন বলবে '{trigger}' — উত্তর দেবে নিজে বানানো স্কিল দিয়ে")
    v = bump_version("minor")
    log_change(f"নতুন স্কিল নিজে বানিয়ে ইনস্টল: {name} (trigger: {trigger}) — নতুন ভার্সন v{v}")
    return fname, f"হয়ে গেছে ভাইয়া! নিজে কোড লিখে, টেস্ট করে নতুন স্কিল বানিয়ে নিলাম: '{trigger}' বললেই আমি উত্তর দেব। এখন আমার ভার্সন v{v}।"


# ------------------------------------------------------- self-evolution

def learn_from_text(text, mem):
    """Automatic learning from every interaction (patterns + explicit facts)."""
    low = text.lower()
    m = re.search(r"(?:মনে রেখো|মনে রাখো|mone rekho|remember)[:\- ]+(.+)", text, re.I)
    if m:
        fact = m.group(1).strip()
        if fact and fact not in mem["facts"]:
            mem["facts"].append(fact)
            mem.setdefault("learned_notes", []).append(f"{date.today()}: {fact}")
        return f"মনে রাখলাম ভাইয়া: {fact}"
    m = re.search(r"(?:আমি|ami) (.+?) (?:পছন্দ করি|pochondo kori|ভালোবাসি)", text)
    if m:
        like = m.group(1).strip()
        if like and like not in mem["likes"]:
            mem["likes"].append(like)
        return f"নোট করলাম ভাইয়া, তুমি {like} পছন্দ করো।"
    return None


def auto_evolve(mem):
    """Pattern insight + own-prompt update, after every 20 interactions."""
    if mem["interaction_count"] % 20 != 0:
        return
    counts = mem.get("command_counts", {})
    if not counts:
        return
    top = max(counts, key=counts.get)
    note = (f"{date.today()}: ভাইয়া সবচেয়ে বেশি ব্যবহার করেন '{top}' "
            f"({counts[top]} বার) — এই ধরনের কাজে দ্রুত উত্তর দেবে।")
    prompt = get_prompt()
    if top not in prompt:
        PROMPT_FILE.write_text(prompt + "\n" + note, encoding="utf-8")
        log_change(f"স্ব-বিকাশ: প্যাটার্ন বুঝে নিজের prompt হালনাগাদ — top কাজ '{top}'")


def daily_release_if_due():
    """A new version every 24h: snapshot + changelog + version up."""
    ver = get_version()
    today = str(date.today())
    if ver.get("last_daily_release") == today:
        return None
    # Auto self-upgrade first (if Bhaiya left it on): heal + learn, then
    # the daily release snapshots the improved state.
    upgrade_notes = []
    try:
        if get_config().get("auto_self_upgrade", True):
            upgrade_notes = self_upgrade()
    except Exception:
        pass
    mem = get_memory()
    caps = load_json(CAPS_FILE, [])
    summary = (f"দৈনিক রিলিজ {today}: মোট কথা {mem['interaction_count']} বার, "
               f"মনে থাকা তথ্য {len(mem['facts'])}টা, স্কিল {len(caps)}টা, "
               f"শেখা উত্তর {len(load_json(KNOW_FILE, {}))}টা। "
               + ("স্ব-আপগ্রেড: " + "; ".join(upgrade_notes) if upgrade_notes else ""))
    snap = BACKUPS / f"{today}-v{ver['version']}"
    snap.mkdir(parents=True, exist_ok=True)
    for src in (MEMORY_FILE, VERSION_FILE, CAPS_FILE, PROMPT_FILE):
        if src.exists():
            shutil.copy2(src, snap / src.name)
    if PLUGINS.exists():
        shutil.copytree(PLUGINS, snap / "plugins", dirs_exist_ok=True)
    new_v = bump_version("patch")
    ver = get_version()
    ver["last_daily_release"] = today
    ver["releases"].append({"date": today, "version": new_v, "summary": summary})
    save_json(VERSION_FILE, ver)
    log_change(f"প্রতি ২৪ ঘণ্টার নতুন ভার্সন লঞ্চ: v{new_v} — {summary}")
    maybe_git_push(f"Sokhi daily version v{new_v} ({today})")
    return new_v


def maybe_git_push(message):
    cfg = get_config()
    if not cfg.get("git_auto_push"):
        return "Git auto-push বন্ধ আছে (config-তে চালু করলে হবে)।"
    if not shutil.which("git"):
        return "এই PC-তে Git নেই।"
    try:
        inside = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"],
                                cwd=BASE, capture_output=True, text=True, timeout=10)
        if inside.returncode != 0:
            return "এখানে Git repo নেই — আগে repo বানাতে হবে ভাইয়া।"
        subprocess.run(["git", "add", "plugins", "data/version.json", "CHANGELOG.md"],
                       cwd=BASE, capture_output=True, timeout=15)
        subprocess.run(["git", "commit", "-m", message], cwd=BASE, capture_output=True, timeout=15)
        push = subprocess.run(["git", "push"], cwd=BASE, capture_output=True, text=True, timeout=30)
        return "Git push হয়ে গেছে।" if push.returncode == 0 else "Git push হয়নি: " + push.stderr[-200:]
    except Exception as e:
        return f"Git push-এ সমস্যা: {e}"


def git_status_text():
    if not shutil.which("git"):
        return "ভাইয়া, এই PC-তে Git ইনস্টল নেই। Git বসালে (সম্পূর্ণ ফ্রি) আমি নিজের স্কিল আর ভার্সন সেখানে রাখতে পারব।"
    inside = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"],
                            cwd=BASE, capture_output=True, text=True, timeout=10)
    if inside.returncode != 0:
        return "ভাইয়া, এখনো কোনো Git repo বানানো হয়নি। তুমি চাইলে আমি ধাপে ধাপে শিখিয়ে দেব — repo বানালেই আমার কোড নিজে থেকে commit/push করার পথ খুলবে (তোমার অ্যাকাউন্টে, তোমার অনুমতিতে)।"
    remote = subprocess.run(["git", "remote", "-v"], cwd=BASE, capture_output=True, text=True, timeout=10)
    return "Git repo আছে ভাইয়া।\n" + (remote.stdout or "কোনো remote যোগ করা নেই।")


# -*- coding: utf-8 -*-
# ============================================================
# Sokhi v1.0 backend fragment — coordinator (integration into sokhi.py)
# Provides: conversation buffer (B1), layered-memory prompt block,
# N13 rules-by-talk + skill-draft approval, agent fleet (C1-C5),
# away tasks (N5/N14-lite), foundation flags (F3/F5 honesty stubs).
# Uses sokhi.py globals: DATA, PLUGINS, DRAFTS, load_json, save_json,
# get_config, get_memory, ask_gemini, web_search, get_news, system_info,
# log_change, register_capability, bump_version, PLUGIN_TEMPLATE, BANNED.
# ============================================================

CONVO_FILE = DATA / "convo.json"
RULES_FILE = DATA / "rules-custom.md"
AWAY_FILE = DATA / "away-tasks.json"
BRIDGE_QUEUE_FILE = DATA / "bridge-queue.json"


# ------------------------------------------------ conversation buffer (B1)
def convo_load():
    items = load_json(CONVO_FILE, [])
    return items if isinstance(items, list) else []


def convo_remember(user_text, reply):
    """Keep the last 8 exchanges so Gemini answers with real continuity."""
    try:
        items = convo_load()
        items.append({"r": "user", "t": (user_text or "")[:800]})
        items.append({"r": "model", "t": (reply or "")[:800]})
        save_json(CONVO_FILE, items[-16:])
    except Exception:
        pass


def gemini_contents(user_text):
    """Build a multi-turn Gemini contents array from the buffer."""
    items = convo_load()[-10:]
    contents = []
    for it in items:
        role = "model" if it.get("r") == "model" else "user"
        t = (it.get("t") or "").strip()
        if t:
            contents.append({"role": role, "parts": [{"text": t}]})
    while contents and contents[0]["role"] != "user":
        contents.pop(0)
    # merge consecutive same-role entries (Gemini prefers alternation)
    merged = []
    for c in contents:
        if merged and merged[-1]["role"] == c["role"]:
            merged[-1]["parts"][0]["text"] += "\n" + c["parts"][0]["text"]
        else:
            merged.append(c)
    merged.append({"role": "user", "parts": [{"text": user_text}]})
    return merged



# ------------------------------------------------ v1.2.0: conversations store
# DATA/"conversations.json": {"active": id, "items":[{id,title,created,
# updated,messages:[{r,t,ts}]}]} — multiple titled chats (ideas 15-21).
CONVERSATIONS_FILE = DATA / "conversations.json"
PINS_FILE = DATA / "pins.json"
FEEDBACK_FILE = DATA / "feedback.json"
_DEFAULT_CONVO_TITLE = "নতুন কথোপকথন"


def _new_convo_id():
    return "c" + str(int(time.time() * 1000)) + secrets.token_hex(3)


def convos_load():
    """Load the conversations store; always returns a sane dict."""
    data = load_json(CONVERSATIONS_FILE, None)
    if not isinstance(data, dict):
        return {"active": None, "items": []}
    items = data.get("items")
    if not isinstance(items, list):
        items = []
    data["items"] = items
    if data.get("active") not in [it.get("id") for it in items if isinstance(it, dict)]:
        data["active"] = items[0].get("id") if items else None
    return data


def convos_save(data):
    try:
        save_json(CONVERSATIONS_FILE, data)
    except Exception:
        pass
    return data


def _convo_find(data, cid):
    for it in data.get("items", []):
        if isinstance(it, dict) and it.get("id") == cid:
            return it
    return None


def pins_load():
    """Load the pins store; always returns a sane list."""
    items = load_json(PINS_FILE, [])
    return items if isinstance(items, list) else []


def pins_save(items):
    try:
        save_json(PINS_FILE, items if isinstance(items, list) else [])
    except Exception:
        pass
    return items


def convo_new(title=None):
    """Create a new conversation, make it active, and return it."""
    data = convos_load()
    now = int(time.time())
    title = str(title or "").strip()[:80] or _DEFAULT_CONVO_TITLE
    item = {"id": _new_convo_id(), "title": title,
            "created": now, "updated": now, "messages": []}
    data.setdefault("items", []).append(item)
    data["active"] = item["id"]
    convos_save(data)
    return item


def convo_active():
    """Return the active conversation dict (creating one if none exists)."""
    data = convos_load()
    item = _convo_find(data, data.get("active"))
    if item is None:
        if data.get("items"):
            item = data["items"][0]
            data["active"] = item.get("id")
            convos_save(data)
        else:
            item = convo_new()
    return item


def convo_append(user_text, reply):
    """Append a user+model exchange to the active conversation.
    Auto-titles from the first user message when the title is still
    empty/the default. Returns the active conversation item."""
    data = convos_load()
    item = _convo_find(data, data.get("active"))
    if item is None:
        if data.get("items"):
            item = data["items"][0]
            data["active"] = item.get("id")
        else:
            now = int(time.time())
            item = {"id": _new_convo_id(), "title": _DEFAULT_CONVO_TITLE,
                    "created": now, "updated": now, "messages": []}
            data.setdefault("items", []).append(item)
            data["active"] = item["id"]
    now = int(time.time())
    item.setdefault("messages", [])
    item["messages"].append({"r": "user", "t": str(user_text or ""), "ts": now})
    item["messages"].append({"r": "model", "t": str(reply or ""), "ts": now})
    item["updated"] = now
    if not str(item.get("title") or "").strip() or item.get("title") == _DEFAULT_CONVO_TITLE:
        first_user = str(user_text or "").strip()
        if first_user:
            item["title"] = first_user[:40]
    convos_save(data)
    return item


def convos_api(data):
    """POST /api/convos handler (ideas 15-21)."""
    data = data or {}
    action = str(data.get("action") or "").strip()
    store = convos_load()
    if action == "create":
        item = convo_new(data.get("title"))
        return {"ok": True, "id": item["id"], "active": item["id"],
                "title": item.get("title", "")}
    if action == "switch":
        cid = str(data.get("id") or "")
        if _convo_find(store, cid) is None:
            return {"ok": False, "error": "এই কথোপকথনটা খুঁজে পাইনি।"}
        store["active"] = cid
        convos_save(store)
        return {"ok": True, "id": cid, "active": cid}
    if action == "get":
        cid = str(data.get("id") or store.get("active") or "")
        item = _convo_find(store, cid)
        if item is None:
            return {"ok": False, "error": "এই কথোপকথনটা খুঁজে পাইনি।", "messages": []}
        return {"ok": True, "id": item.get("id"), "title": item.get("title", ""),
                "messages": item.get("messages", [])}
    if action == "rename":
        cid = str(data.get("id") or "")
        item = _convo_find(store, cid)
        title = str(data.get("title") or "").strip()[:80]
        if item is None:
            return {"ok": False, "error": "এই কথোপকথনটা খুঁজে পাইনি।"}
        if not title:
            return {"ok": False, "error": "নতুন নামটা লিখে দাও।"}
        item["title"] = title
        item["updated"] = int(time.time())
        convos_save(store)
        return {"ok": True, "id": cid, "title": title}
    if action == "pin":
        cid = str(data.get("id") or "")
        item = _convo_find(store, cid)
        if item is None:
            return {"ok": False, "error": "এই কথোপকথনটা খুঁজে পাইনি।"}
        item["pinned"] = bool(data.get("pinned"))
        convos_save(store)
        return {"ok": True, "id": cid, "pinned": item["pinned"]}
    if action == "delete":
        cid = str(data.get("id") or "")
        if _convo_find(store, cid) is None:
            return {"ok": False, "error": "এই কথোপকথনটা খুঁজে পাইনি।"}
        was_active = store.get("active") == cid
        store["items"] = [it for it in store.get("items", [])
                          if not (isinstance(it, dict) and it.get("id") == cid)]
        try:
            _pins = pins_load()
            _pins_filtered = [p for p in _pins if not (isinstance(p, dict) and p.get("convo_id") == cid)]
            if len(_pins_filtered) != len(_pins):
                pins_save(_pins_filtered)
        except Exception:
            pass
        if not store["items"]:
            convos_save(store)
            item = convo_new()
            return {"ok": True, "id": cid, "active": item["id"]}
        if was_active:
            store["active"] = store["items"][-1].get("id")
        convos_save(store)
        return {"ok": True, "id": cid, "active": store.get("active")}
    if action == "clear":
        item = _convo_find(store, store.get("active"))
        if item is None:
            item = convo_new()
            return {"ok": True, "id": item["id"], "active": item["id"]}
        item["messages"] = []
        item["updated"] = int(time.time())
        convos_save(store)
        return {"ok": True, "id": item.get("id"), "active": item.get("id")}
    if action == "search":
        q = str(data.get("q") or "").strip()
        if not q:
            return {"ok": True, "results": [], "items": []}
        ql = q.lower()
        results = []
        for it in store.get("items", []):
            if not isinstance(it, dict):
                continue
            title = str(it.get("title") or "")
            snippet = ""
            if ql in title.lower():
                snippet = title[:80]
            else:
                for m in it.get("messages", []):
                    t = str(m.get("t") or "")
                    idx = t.lower().find(ql)
                    if idx >= 0:
                        start = max(0, idx - 20)
                        snippet = t[start:start + 80]
                        break
                if not snippet:
                    continue
            results.append({"id": it.get("id"), "title": title, "snippet": snippet})
        return {"ok": True, "results": results, "items": results}
    if action == "truncate":
        cid = str(data.get("id") or store.get("active") or "")
        item = _convo_find(store, cid)
        if item is None:
            return {"ok": False, "error": "এই কথোপকথনটা খুঁজে পাইনি।"}
        try:
            keep = int(data.get("keep", 0))
        except Exception:
            keep = 0
        keep = max(0, keep)
        item["messages"] = list(item.get("messages", []))[:keep]
        item["updated"] = int(time.time())
        convos_save(store)
        return {"ok": True, "id": cid, "count": len(item["messages"])}
    return {"ok": False, "error": "কী করতে হবে বুঝতে পারিনি — action ঠিক করে পাঠাও।"}


def pins_api(data):
    """POST /api/pins handler (idea 43): pinned messages."""
    data = data or {}
    action = str(data.get("action") or "").strip()
    if action == "list":
        store = convos_load()
        titles = {}
        for it in store.get("items", []):
            if isinstance(it, dict):
                titles[it.get("id")] = it.get("title", "")
        pins = []
        for pin in pins_load():
            if not isinstance(pin, dict):
                continue
            item = dict(pin)
            if item.get("convo_id") in titles:
                item["convo_title"] = titles[item.get("convo_id")]
            pins.append(item)
        return {"ok": True, "pins": pins}
    if action == "add":
        convo_id = str(data.get("convo_id") or "")
        store = convos_load()
        if _convo_find(store, convo_id) is None:
            return {"ok": False, "error": "এই কথোপকথনটা খুঁজে পাইনি।"}
        try:
            idx = int(data.get("idx"))
        except Exception:
            idx = -1
        pins = pins_load()
        for pin in pins:
            if isinstance(pin, dict) and pin.get("convo_id") == convo_id and pin.get("idx") == idx:
                return {"ok": True, "pin": pin, "dupe": True}
        who = str(data.get("who") or "")
        if who not in ("me", "sokhi"):
            who = "sokhi"
        pin = {"id": "p" + str(int(time.time() * 1000)) + secrets.token_hex(3),
               "convo_id": convo_id, "idx": idx, "who": who,
               "text": str(data.get("text") or "")[:2000],
               "ts": int(time.time())}
        pins.append(pin)
        pins_save(pins)
        return {"ok": True, "pin": pin}
    if action == "remove":
        pid = str(data.get("id") or "")
        pins = [pin for pin in pins_load()
                if not (isinstance(pin, dict) and pin.get("id") == pid)]
        pins_save(pins)
        return {"ok": True}
    return {"ok": False, "error": "কী করতে হবে বুঝতে পারিনি — action ঠিক করে পাঠাও।"}


# Whitelist of config keys safe to export / restore in a backup or sync
# bundle (ideas 44 + 48). gemini_api_key is NEVER in this list.
_BACKUP_CONFIG_KEYS = ("city", "tts_voice", "tts_preset", "tts_rate",
                       "tts_pitch", "voice_rate", "call_name", "reply_style",
                       "reply_language", "quiet_start", "quiet_end",
                       "dim_start", "dim_end", "dim_level", "wake_word", "echo_guard",
                       "update_url", "auto_self_upgrade", "bridge_enabled",
                       "computer_use_enabled", "away_mode", "gemini_model",
                       "tts_engine", "gemini_voice")


def backup_api(data):
    """POST /api/backup handler (ideas 44 + 48): export / import a
    backup or sync bundle. The Gemini key is never exported, and an
    import never overwrites the key already on this device."""
    data = data or {}
    action = str(data.get("action") or "").strip()
    if action == "export":
        kind = str(data.get("kind") or "")
        if kind not in ("backup", "sync"):
            kind = "backup"
        cfg = get_config()
        _notes_file = DATA / "notes.txt"
        try:
            _notes = _notes_file.read_text(encoding="utf-8") if _notes_file.exists() else ""
        except Exception:
            _notes = ""
        bundle = {"app": "sokhi-desktop", "kind": kind,
                  "version": APP_VERSION,
                  "exported_at": datetime.now().isoformat(),
                  "config": {k: cfg.get(k) for k in _BACKUP_CONFIG_KEYS if k in cfg},
                  "memory": get_memory(),
                  "conversations": convos_load(),
                  "pins": pins_load(),
                  "notes": _notes,
                  "tasks": load_json(AWAY_FILE, []) if AWAY_FILE.exists() else [],
                  "daily_q": load_json(DAILY_Q_FILE, {}) if DAILY_Q_FILE.exists() else {},
                  "reminders": load_json(REMINDERS_FILE, []) if REMINDERS_FILE.exists() else [],
                  "fact_weights": load_json(FACT_WEIGHTS_FILE, {}) if FACT_WEIGHTS_FILE.exists() else {},
                  "fact_archive": load_json(FACT_ARCHIVE_FILE, []) if FACT_ARCHIVE_FILE.exists() else []}
        _fname = f"sokhi-{kind}-{datetime.now().strftime('%Y%m%d')}.json"
        return {"ok": True, "filename": _fname, "bundle": bundle}
    if action == "import":
        bundle = data.get("bundle")
        if not isinstance(bundle, dict) or bundle.get("app") != "sokhi-desktop" or bundle.get("kind") not in ("backup", "sync"):
            return {"ok": False, "error": "এটা Sokhi-র ব্যাকআপ ফাইল বলে মনে হচ্ছে না।"}
        # FIRST snapshot everything that exists, so a restore can be undone.
        _stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        _snap = BACKUPS / ("pre-restore-" + _stamp)
        try:
            _snap.mkdir(parents=True, exist_ok=True)
            for _src in (CONFIG_FILE, MEMORY_FILE, CONVERSATIONS_FILE,
                         PINS_FILE, DATA / "notes.txt", AWAY_FILE,
                         DAILY_Q_FILE, REMINDERS_FILE, FACT_WEIGHTS_FILE,
                         FACT_ARCHIVE_FILE):
                try:
                    if _src.exists():
                        shutil.copy2(_src, _snap / _src.name)
                except Exception:
                    pass
        except Exception:
            pass
        restored = {"conversations": 0, "pins": 0, "facts": 0}
        _bcfg = bundle.get("config")
        if isinstance(_bcfg, dict):
            cfg = get_config()
            for _k in _BACKUP_CONFIG_KEYS:
                if _k in _bcfg:
                    cfg[_k] = _bcfg[_k]
            save_config(cfg)
        _bmem = bundle.get("memory")
        if isinstance(_bmem, dict):
            save_json(MEMORY_FILE, _bmem)
            _facts = _bmem.get("facts")
            restored["facts"] = len(_facts) if isinstance(_facts, list) else 0
        _bconvos = bundle.get("conversations")
        if isinstance(_bconvos, dict) and isinstance(_bconvos.get("items"), list):
            convos_save(_bconvos)
            restored["conversations"] = len(_bconvos.get("items") or [])
        _bpins = bundle.get("pins")
        if isinstance(_bpins, list):
            pins_save(_bpins)
            restored["pins"] = len(_bpins)
        _bnotes = bundle.get("notes")
        if isinstance(_bnotes, str):
            try:
                (DATA / "notes.txt").write_text(_bnotes[:20000], encoding="utf-8")
            except Exception:
                pass
        _btasks = bundle.get("tasks")
        if isinstance(_btasks, list):
            save_json(AWAY_FILE, _btasks[-50:])
        _bdq = bundle.get("daily_q")
        if isinstance(_bdq, dict):
            save_json(DAILY_Q_FILE, _bdq)
        _brem = bundle.get("reminders")
        if isinstance(_brem, list):
            save_json(REMINDERS_FILE, _brem[-200:])
        _bfw = bundle.get("fact_weights")
        if isinstance(_bfw, dict):
            save_json(FACT_WEIGHTS_FILE, _bfw)
        _bfa = bundle.get("fact_archive")
        if isinstance(_bfa, list):
            save_json(FACT_ARCHIVE_FILE, _bfa[-500:])
        return {"ok": True, "snapshot": _snap.name, "restored": restored}
    return {"ok": False, "error": "কী করতে হবে বুঝতে পারিনি — action ঠিক করে পাঠাও।"}


# =====================================================================
#  v1.4.0 — Worker B: #700 daily hard question, #109 reminder rules,
#  #100 weekly board (lite), #52 self-doctor (lite)
#  সব state DATA-র ভিতরে; Gemini key কোথাও output-এ যায় না।
# =====================================================================
DAILY_Q_FILE = DATA / "daily_q.json"
REMINDERS_FILE = DATA / "reminders.json"
_WEEKDAY_KEYS = ("sat", "sun", "mon", "tue", "wed", "thu", "fri")


# ------------------------------------------------ #700 দৈনিক কঠিন প্রশ্ন
def _dailyq_candidates():
    """প্রার্থী প্রশ্ন: আগে ভুলের খাতা, না থাকলে অফলাইন ব্যাংক (সব বিষয়)।

    ভুলের খাতার আসল আকার (exam_answer থেকে): {q, options, correct(সঠিক
    উত্তরের TEXT), your_answer, subject, topic, date} — তাই 'answer' index
    থাকলে সেটা, না থাকলে 'correct' text থেকে index বের করা হয়।"""
    cands = []
    book = load_json(_WRONG_BOOK_FILE, [])
    if isinstance(book, list):
        for e in book:
            if not isinstance(e, dict):
                continue
            q = e.get("q")
            opts = e.get("options")
            if not q or not isinstance(opts, list) or len(opts) < 2:
                continue
            ans = None
            if isinstance(e.get("answer"), int) and 0 <= e["answer"] < len(opts):
                ans = e["answer"]
            elif e.get("correct") is not None:
                try:
                    ans = [str(o) for o in opts].index(str(e["correct"]))
                except ValueError:
                    continue
            if ans is None:
                continue
            cands.append({"q": str(q),
                          "options": [str(o) for o in opts[:4]],
                          "answer": int(ans),
                          "topic": str(e.get("topic") or "ভুলের খাতা"),
                          "source": "ভুলের খাতা"})
    if cands:
        return cands
    pooled = []
    for subj, qs_ in OFFLINE_BANK.items():
        for it in qs_ or []:
            if (isinstance(it, dict) and it.get("q")
                    and isinstance(it.get("options"), list)
                    and isinstance(it.get("answer"), int)
                    and 0 <= it["answer"] < len(it["options"])):
                pooled.append({"q": str(it["q"]),
                               "options": [str(o) for o in it["options"][:4]],
                               "answer": int(it["answer"]),
                               "topic": str(it.get("topic") or subj),
                               "source": subj})
    return pooled


def _dailyq_today_state():
    """আজকের state; তারিখ বদলালে নতুন প্রশ্ন বেছে সেভ করে।"""
    today = str(date.today())
    st = load_json(DAILY_Q_FILE, {})
    if isinstance(st, dict) and st.get("date") == today and st.get("q"):
        return st
    cands = _dailyq_candidates()
    if not cands:
        return None
    pick = cands[date.today().toordinal() % len(cands)]
    st = {"date": today, "q": pick["q"], "options": pick["options"],
          "answer": pick["answer"], "topic": pick["topic"],
          "source": pick["source"], "done": False, "revealed": False}
    save_json(DAILY_Q_FILE, st)
    return st


def dailyq_get():
    """GET /api/dailyq — উত্তরের index/text কখনোই পাঠানো হয় না।"""
    st = _dailyq_today_state()
    if not st:
        return {"ok": True, "done": True, "date": str(date.today()),
                "question": None}
    return {"ok": True, "done": bool(st.get("done")),
            "date": st.get("date"),
            "question": {"q": st.get("q"), "options": st.get("options"),
                         "topic": st.get("topic"),
                         "source": st.get("source")}}


def dailyq_api(data):
    """POST /api/dailyq — action: 'reveal' | 'skip'."""
    data = data if isinstance(data, dict) else {}
    action = str(data.get("action") or "").strip()
    st = _dailyq_today_state()
    if action == "reveal":
        if not st:
            return {"ok": False, "error": "আজকের জন্য কোনো প্রশ্ন পাইনি।"}
        st["revealed"] = True
        st["done"] = True
        save_json(DAILY_Q_FILE, st)
        ans = int(st.get("answer", 0))
        opts = st.get("options") or []
        return {"ok": True, "answer_index": ans,
                "answer_text": opts[ans] if 0 <= ans < len(opts) else ""}
    if action == "skip":
        if st:
            st["done"] = True
            save_json(DAILY_Q_FILE, st)
        return {"ok": True}
    return {"ok": False,
            "error": "action হতে হবে 'reveal' বা 'skip'।"}


# ------------------------------------------------ #109 রিমাইন্ডার নিয়ম
def _reminders_load():
    items = load_json(REMINDERS_FILE, [])
    return items if isinstance(items, list) else []


def _reminders_save(items):
    save_json(REMINDERS_FILE, items[-200:])


def reminders_api(data):
    """POST /api/reminders — action: 'list' | 'add' | 'delete'.
    GET /api/reminders এই একই ফাংশনকে {'action':'list'} দিয়ে ডাকে।"""
    data = data if isinstance(data, dict) else {}
    action = str(data.get("action") or "list").strip()
    if action == "list":
        return {"ok": True, "rules": _reminders_load()}
    if action == "add":
        text = str(data.get("text") or "").strip()
        if not text or len(text) > 200:
            return {"ok": False,
                    "error": "রিমাইন্ডারের লেখা খালি নয়, সর্বোচ্চ ২০০ অক্ষর হতে হবে।"}
        tm = str(data.get("time") or "").strip()
        m = re.match(r"^(\d{2}):(\d{2})$", tm)
        if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
            return {"ok": False,
                    "error": "সময়টা HH:MM আকারে দাও, যেমন 07:30।"}
        days = str(data.get("days") or "daily").strip()
        if days != "daily":
            parts = [d.strip() for d in days.split(",") if d.strip()]
            if not parts or any(d not in _WEEKDAY_KEYS for d in parts):
                return {"ok": False,
                        "error": "বার হতে হবে 'daily' অথবা sat,sun,mon,tue,wed,thu,fri থেকে বেছে কমা দিয়ে।"}
            days = ",".join(parts)
        rules = _reminders_load()
        ids = []
        for r in rules:
            if isinstance(r, dict):
                try:
                    ids.append(int(r.get("id", 0)))
                except Exception:
                    pass
        rule = {"id": (max(ids) + 1) if ids else 1, "text": text,
                "time": tm, "days": days, "created": str(date.today())}
        rules.append(rule)
        _reminders_save(rules)
        return {"ok": True, "rules": rules}
    if action == "delete":
        try:
            rid = int(data.get("id"))
        except Exception:
            return {"ok": False, "error": "নিয়মের id ঠিক করে পাঠাও।"}
        rules = [r for r in _reminders_load()
                 if not (isinstance(r, dict) and r.get("id") == rid)]
        _reminders_save(rules)
        return {"ok": True, "rules": rules}
    return {"ok": False,
            "error": "action হতে হবে 'list', 'add' বা 'delete'।"}


# ------------------------------------------------ #100 সাপ্তাহিক বোর্ড-সভা lite
def board_text():
    """গত ৭ দিনের সারসংক্ষেপ — শুধু বিদ্যমান ডেটা থেকে, সহজ বাংলায়।

    সতর্কতা: study-progress.json-এ cumulative গণনা + last_date থাকে,
    সাপ্তাহিক delta পাওয়া যায় না — তাই মোট হিসাবটা 'সার্বিক' বলে
    পরিষ্কার লেখা হয়, আর ৭ দিনের অংশটা শুধু last_date দিয়ে দেখানো হয়।"""
    today = date.today()
    lines = ["🗓️ সাপ্তাহিক বোর্ড-সভা রিপোর্ট",
             f"তৈরি: {now_str()} (গত ৭ দিনের চিত্র যেখানে তারিখ আছে)",
             ""]
    prog = load_json(_STUDY_PROGRESS_FILE, {})
    if not isinstance(prog, dict):
        prog = {}
    tot_sessions = tot_mocks = tot_steps = 0
    active = []
    for subj, ent in prog.items():
        if not isinstance(ent, dict):
            continue
        tot_sessions += int(ent.get("sessions", 0) or 0)
        tot_mocks += int(ent.get("mock_tests", 0) or 0)
        tot_steps += int(ent.get("total_steps", 0) or 0)
        try:
            ld = date.fromisoformat(str(ent.get("last_date") or ""))
            if 0 <= (today - ld).days <= 6:
                active.append((subj, ent))
        except Exception:
            pass
    lines.append("📚 পড়াশোনা — সক্রিয় বিষয় ও সর্বশেষ অগ্রগতি")
    if prog:
        lines.append(f"• সার্বিক হিসাব: সেশন {_bn_num(tot_sessions)}টি, "
                     f"মক টেস্ট {_bn_num(tot_mocks)}টি, ধাপ {_bn_num(tot_steps)}টি")
        if active:
            for subj, ent in active:
                lines.append(f"• {subj}: শেষ টপিক — "
                             f"{ent.get('last_topic') or '—'} "
                             f"(শেষ পড়া: {ent.get('last_date') or '—'})")
        else:
            lines.append("• গত ৭ দিনে কোনো বিষয়ে নতুন অগ্রগতির রেকর্ড নেই।")
    else:
        lines.append("• এখনো কোনো পড়ার রেকর্ড নেই।")
    lines.append("")
    book = load_json(_WRONG_BOOK_FILE, [])
    if not isinstance(book, list):
        book = []
    recent_wrong = 0
    for e in book:
        if isinstance(e, dict):
            try:
                d0 = date.fromisoformat(str(e.get("date") or ""))
                if 0 <= (today - d0).days <= 6:
                    recent_wrong += 1
            except Exception:
                pass
    lines.append("📕 ভুলের খাতা")
    lines.append(f"• মোট ভুল প্রশ্ন জমা: {_bn_num(len(book))}টি")
    lines.append(f"• গত ৭ দিনে নতুন ভুল: {_bn_num(recent_wrong)}টি")
    lines.append("")
    tasks = away_load()
    pending = sum(1 for t in tasks
                  if isinstance(t, dict) and t.get("status") == "অপেক্ষায়")
    shown = sum(1 for t in tasks
                if isinstance(t, dict) and t.get("status") == "দেখানো হয়েছে")
    done_like = sum(1 for t in tasks
                    if isinstance(t, dict)
                    and str(t.get("status") or "") in ("সম্পন্ন", "done", "শেষ"))
    lines.append("✅ কাজের তালিকা")
    lines.append(f"• মোট কাজ: {_bn_num(len(tasks))}টি — অপেক্ষায় "
                 f"{_bn_num(pending)}টি, দেখানো হয়েছে {_bn_num(shown)}টি, "
                 f"সম্পন্ন চিহ্নিত {_bn_num(done_like)}টি")
    lines.append("")
    mem = get_memory()
    store = convos_load()
    items = [it for it in store.get("items", []) if isinstance(it, dict)]
    n_msgs = sum(len(it.get("messages", []) or []) for it in items)
    lines.append("🧠 স্মৃতি ও কথোপকথন")
    lines.append(f"• মনে রাখা তথ্য: {_bn_num(len(mem.get('facts', []) or []))}টি")
    lines.append(f"• মোট কথাবার্তা (interaction): "
                 f"{_bn_num(int(mem.get('interaction_count', 0) or 0))}টি")
    lines.append(f"• কথোপকথন: {_bn_num(len(items))}টি "
                 f"(মোট বার্তা {_bn_num(n_msgs)}টি)")
    return "\n".join(lines)


def board_api():
    return {"ok": True, "text": board_text(), "generated": now_str()}


# ------------------------------------------------ #52 নিজের ডাক্তার lite
def doctor_report():
    """নিজের স্বাস্থ্য-পরীক্ষা — শুধু রিপোর্ট, কোনো auto-fix নয়।
    Gemini key কখনোই দেখানো হয় না (শুধু বসানো আছে/নেই বলা হয়)।

    নোট: ফাইলে আসল self_test() ফাংশন নেই — ওই নামটা শুধু PLUGIN_TEMPLATE
    string-এর ভিতরে plugin-দের জন্য; তাই এখানে নিজের ছোট checks চালানো হয়।"""
    checks = []

    def _add(name, ok, detail, suggestion=""):
        checks.append({"name": name, "status": "ok" if ok else "warn",
                       "detail": detail,
                       "suggestion": "" if ok else suggestion})

    try:
        _ver = get_version().get("version", "?")
    except Exception:
        _ver = "?"
    _add("অ্যাপের ভার্সন", True,
         f"চলমান ভার্সন v{_ver} (কোডের ভার্সন v{APP_VERSION})")
    try:
        _probe = DATA / ".doctor-probe.tmp"
        _probe.write_text("ok", encoding="utf-8")
        try:
            _probe.unlink()
        except Exception:
            pass
        _add("ডেটা ফোল্ডারে লেখা যায়", True,
             "data ফোল্ডারে লিখতে পারছি — স্মৃতি ও সেটিংস সেভ হবে।")
    except Exception as e:
        _add("ডেটা ফোল্ডারে লেখা যায়", False, f"লিখতে পারিনি: {e}",
             "data ফোল্ডারটা অন্য প্রোগ্রামে খোলা আছে কিনা দেখো; "
             "ল্যাপটপ একবার রিস্টার্ট দিয়ে আবার চেষ্টা করো।")
    for _label, _file in (("স্মৃতির ফাইল (memory.json)", MEMORY_FILE),
                          ("কথোপকথনের ফাইল (conversations.json)",
                           CONVERSATIONS_FILE)):
        try:
            if not _file.exists():
                _add(_label, True,
                     "ফাইল এখনো তৈরি হয়নি — নতুন ইনস্টলে এটা স্বাভাবিক।")
            else:
                json.loads(_file.read_text(encoding="utf-8"))
                _add(_label, True, "ফাইল ঠিকঠাক পড়া যাচ্ছে (JSON ঠিক আছে)।")
        except Exception as e:
            _add(_label, False, f"ফাইল পড়তে সমস্যা: {e}",
                 "ব্যাকআপ থেকে restore করে দেখো, অথবা Saba-কে এই "
                 "রিপোর্টটা পাঠাও। ফাইলটা নিজে হাতে এডিট কোরো না।")
    try:
        _kw = ("error", "ত্রুটি", "failed", "traceback", "429")
        _hits = 0
        _last = ""
        if CHANGELOG.exists():
            _cl = CHANGELOG.read_text(encoding="utf-8",
                                      errors="ignore").splitlines()[-15:]
            for _ln in _cl:
                if any(k in _ln.lower() for k in _kw):
                    _hits += 1
                    _last = _ln.strip()[:120]
        if _hits == 0:
            _add("সাম্প্রতিক লগে ত্রুটি", True,
                 "CHANGELOG-এর শেষ লাইনগুলোতে ত্রুটির চিহ্ন পাইনি।")
        else:
            _add("সাম্প্রতিক লগে ত্রুটি", False,
                 f"ত্রুটি-জাতীয় লাইন {_bn_num(_hits)}টি। সর্বশেষ: {_last}",
                 "একই ত্রুটি বারবার এলে Saba-কে এই রিপোর্টটা পাঠাও।")
    except Exception as e:
        _add("সাম্প্রতিক লগে ত্রুটি", False, f"লগ পড়তে পারিনি: {e}",
             "CHANGELOG.md ফাইলটা অ্যাপের ফোল্ডারে আছে কিনা দেখো।")
    _gerr = (_last_gemini_error.get("info") or "").strip()
    if not _gerr:
        try:
            _gl = DATA / "gemini-error.log"
            if _gl.exists():
                _gll = [x for x in _gl.read_text(
                    encoding="utf-8", errors="ignore").splitlines()
                    if x.strip()]
                _gerr = _gll[-1][:200] if _gll else ""
        except Exception:
            _gerr = ""
    _key_set = bool((get_config().get("gemini_api_key") or "").strip())
    if not _key_set:
        _add("স্মার্ট মাথা (Gemini)", True,
             "key বসানো নেই — অফলাইন মাথায় চলছি (এটা সমস্যা নয়)।"
             + (f" শেষ লগের ত্রুটি: {_gerr[:120]}" if _gerr else ""))
    elif _gerr:
        _add("স্মার্ট মাথা (Gemini)", False,
             "key বসানো আছে, তবে শেষ চেষ্টায় ত্রুটি ছিল: " + _gerr[:160],
             "ত্রুটিতে 429 থাকলে ফ্রি লিমিট — একটু পরে আবার চেষ্টা করো। "
             "নেট সংযোগটাও একবার দেখে নাও।")
    else:
        _add("স্মার্ট মাথা (Gemini)", True,
             "key বসানো আছে, সাম্প্রতিক কোনো ত্রুটি নেই।")
    _edge = bool(shutil.which("edge-tts") or shutil.which("edge-tts.exe"))
    try:
        _vstat = tts_engine_status()
    except Exception:
        _vstat = ""
    _verr = (VOICE_STATE.get("error") or "").strip()
    _vnote = (VOICE_STATE.get("note") or "").strip()
    _tpref = (get_config().get("tts_engine") or "edge").strip().lower()
    if _tpref == "browser":
        _add("গলা (TTS ইঞ্জিন)", True,
             f"বেছে দেওয়া ইঞ্জিন: ব্রাউজারের গলা। অবস্থা: {_vstat}")
    elif _tpref == "gemini" and not _key_set:
        _add("গলা (TTS ইঞ্জিন)", False,
             "বেছে দেওয়া ইঞ্জিন: Gemini কণ্ঠ, কিন্তু Gemini key বসানো "
             "নেই — তাই এখন Edge/Google/ব্রাউজার গলায় বলছি।"
             + (f" নোট: {_vnote}" if _vnote else ""),
             "Settings থেকে ফ্রি Gemini key বসালেই Gemini কণ্ঠ চলবে; "
             "না চাইলে কণ্ঠের ইঞ্জিন Edge করে দাও।")
    else:
        _add("গলা (TTS ইঞ্জিন)", bool((_edge or _tpref == "gemini") and not _verr),
             f"বেছে দেওয়া ইঞ্জিন: {_tpref}। অবস্থা: {_vstat}"
             + (f"; শেষ গলার ত্রুটি: {_verr[:120]}" if _verr else "")
             + (f"; নোট: {_vnote}" if _vnote else ""),
             "edge-tts না থাকলে ব্রাউজারের গলা চলবে। Sokhi আবার চালু করলে "
             "সে নিজে edge-tts বসানোর চেষ্টা করে।")
    try:
        _du = shutil.disk_usage(BASE)
        _free_gb = _du.free / (1024 ** 3)
        _add("ডিস্কে ফাঁকা জায়গা", _free_gb >= 0.5,
             f"ফাঁকা আছে প্রায় {_free_gb:.1f} GB।",
             "ডিস্ক প্রায় ভরে গেছে — অপ্রয়োজনীয় বড় ফাইল সরিয়ে "
             "জায়গা করো।")
    except Exception as e:
        _add("ডিস্কে ফাঁকা জায়গা", False, f"মাপতে পারিনি: {e}",
             "PC-র ডিস্কের অবস্থা নিজে একবার দেখে নাও।")
    _bad = sum(1 for c in checks if c["status"] != "ok")
    lines = ["🩺 নিজের ডাক্তার — স্বাস্থ্য রিপোর্ট",
             f"তৈরি: {now_str()}", ""]
    for c in checks:
        lines.append(("✅ " if c["status"] == "ok" else "⚠️ ")
                     + c["name"] + ": " + c["detail"])
        if c["status"] != "ok" and c["suggestion"]:
            lines.append("   প্রস্তাবিত পদক্ষেপ: " + c["suggestion"])
    lines.append("")
    if _bad == 0:
        lines.append("সারসংক্ষেপ: সব ঠিক আছে।")
    else:
        lines.append(f"সারসংক্ষেপ: {_bn_num(_bad)}টি বিষয়ে মনোযোগ দরকার "
                     "(উপরে দেখো)। আমি নিজে থেকে কিছু ঠিক করিনি — "
                     "সিদ্ধান্ত তোমার।")
    return {"ok": True, "text": "\n".join(lines), "checks": checks}


def memory_api(data):
    """POST /api/memory handler (ideas 22-24): view-side mutations."""
    data = data or {}
    action = str(data.get("action") or "").strip()
    mem = get_memory()
    if action == "delete_fact":
        try:
            idx = int(data.get("index"))
        except Exception:
            return {"ok": False, "error": "তথ্যের নম্বরটা ঠিক করে পাঠাও।"}
        facts = mem.setdefault("facts", [])
        if 0 <= idx < len(facts):
            _removed = facts.pop(idx)
            save_json(MEMORY_FILE, mem)
            _fact_weight_forget(_removed)
            return {"ok": True, "facts": facts,
                    "fact_weights": fact_weights_aligned(facts)}
        return {"ok": False, "error": "এই নম্বরের কোনো তথ্য পাইনি।"}
    if action == "add_fact":
        text = str(data.get("text") or "").strip()
        if not text:
            return {"ok": False, "error": "যে তথ্যটা মনে রাখতে হবে, সেটা লিখে দাও।"}
        mem.setdefault("facts", []).append(text[:500])
        save_json(MEMORY_FILE, mem)
        _w = _fact_weights_load()
        _w.setdefault(text[:500], 1)
        _fact_weights_save(_w)
        return {"ok": True, "facts": mem["facts"],
                "fact_weights": fact_weights_aligned(mem["facts"])}
    if action == "archive_fact":
        # #85: delete_fact-এর মতোই সরায়, তবে আগে fact_archive.json-এ রাখে।
        try:
            idx = int(data.get("index"))
        except Exception:
            return {"ok": False, "error": "তথ্যের নম্বরটা ঠিক করে পাঠাও।"}
        facts = mem.setdefault("facts", [])
        if 0 <= idx < len(facts):
            _arch = facts.pop(idx)
            _lst = load_json(FACT_ARCHIVE_FILE, [])
            if not isinstance(_lst, list):
                _lst = []
            _lst.append({"text": _arch, "archived": str(date.today())})
            try:
                save_json(FACT_ARCHIVE_FILE, _lst[-500:])
            except Exception:
                pass
            save_json(MEMORY_FILE, mem)
            _fact_weight_forget(_arch)
            return {"ok": True, "facts": facts,
                    "fact_weights": fact_weights_aligned(facts),
                    "archived": _arch}
        return {"ok": False, "error": "এই নম্বরের কোনো তথ্য পাইনি।"}
    if action == "delete_note":
        try:
            idx = int(data.get("index"))
        except Exception:
            return {"ok": False, "error": "নোটের নম্বরটা ঠিক করে পাঠাও।"}
        notes = mem.setdefault("learned_notes", [])
        if 0 <= idx < len(notes):
            notes.pop(idx)
            save_json(MEMORY_FILE, mem)
            return {"ok": True, "learned_notes": notes}
        return {"ok": False, "error": "এই নম্বরের কোনো নোট পাইনি।"}
    return {"ok": False, "error": "কী করতে হবে বুঝতে পারিনি — action ঠিক করে পাঠাও।"}


def feedback_api(data):
    """POST /api/feedback handler (idea 13): 👍/👎 rating log."""
    data = data or {}
    rating = str(data.get("rating") or "").strip()
    if rating not in ("up", "down"):
        return {"ok": False, "error": "রেটিংটা 'up' বা 'down' হতে হবে।"}
    text = str(data.get("text") or "")[:200]
    items = load_json(FEEDBACK_FILE, [])
    if not isinstance(items, list):
        items = []
    items.append({"ts": int(time.time()), "rating": rating, "text": text})
    save_json(FEEDBACK_FILE, items[-500:])
    return {"ok": True}


def _parse_image_data_url(image):
    """Parse a data-URL (or raw base64) into {mime_type, data} or None."""
    if not image:
        return None
    if isinstance(image, dict):
        d = str(image.get("data") or "")
        if d:
            return {"mime_type": str(image.get("mime_type") or image.get("mime") or "image/png"),
                    "data": d}
        return None
    s = str(image).strip()
    m = re.match(r"data:([^;]+);base64,(.*)", s, re.S)
    if m:
        return {"mime_type": m.group(1), "data": m.group(2).strip()}
    if s:
        return {"mime_type": "image/png", "data": s}
    return None


def layered_memory_block(mem):
    """Layered memory (N3): recent learned notes + custom rules, for the
    Gemini system prompt."""
    parts = []
    notes = mem.get("learned_notes", [])[-5:]
    if notes:
        parts.append("সাম্প্রতিক শেখা নোট: " + "; ".join(notes))
    rules = rules_text()
    if rules:
        parts.append("মনিরের নিজের বসানো নিয়ম (অবশ্যই মানবে):\n" + rules)
    return "\n".join(parts)


# ------------------------------------------------------- N13: rules by talk
def rules_text():
    try:
        if RULES_FILE.exists():
            return RULES_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return ""


def rules_add(rule):
    rule = (rule or "").strip()
    if not rule:
        return "কোনো নিয়ম পেলাম না — 'নিয়ম যোগ করো: ...' লিখে আবার বলো।"
    stamp = datetime.now().strftime("%Y-%m-%d")
    with RULES_FILE.open("a", encoding="utf-8") as f:
        f.write(f"- [{stamp}] {rule}\n")
    log_change(f"N13: কথা বলে নতুন নিয়ম যোগ হলো — {rule[:80]}")
    return (f"নিয়মটা বসিয়ে দিলাম, পড়ে শোনাচ্ছি: \"{rule}\" — "
            "এখন থেকে আমি এই নিয়ম মেনে চলব। সব নিয়ম দেখতে বলো: 'নিয়মের তালিকা দেখাও'।")


def rules_remove(fragment):
    txt = rules_text()
    if not txt:
        return "এখনো কোনো বাড়তি নিয়ম বসানো নেই।"
    lines = [ln for ln in txt.splitlines() if fragment not in ln]
    if len(lines) == len(txt.splitlines()):
        return "এমন কোনো নিয়ম খুঁজে পেলাম না।"
    RULES_FILE.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    log_change(f"N13: নিয়ম মোছা হলো — {fragment[:60]}")
    return "নিয়মটা মুছে দিলাম। এখন থেকে সেটা আর মানা হবে না।"


def rules_handle(text, low):
    m = re.search(r"(?:নিয়ম যোগ করো|নতুন নিয়ম|নিয়ম বসাও)[:\- ]+(.+)", text)
    if m:
        return rules_add(m.group(1))
    m = re.search(r"(?:নিয়ম মোছো|নিয়ম মুছে দাও)[:\- ]+(.+)", text)
    if m:
        return rules_remove(m.group(1).strip())
    if "নিয়মের তালিকা" in text or "নিয়ম দেখাও" in text or "আমার নিয়ম" in text:
        txt = rules_text()
        if not txt:
            return ("এখনো তুমি নিজে কোনো বাড়তি নিয়ম বসাওনি। বসাতে চাইলে বলো: "
                    "'নিয়ম যোগ করো: রাত ১১টার পর পড়ার কথা বলবে না' — আমি সেভ করে "
                    "পড়ে শুনিয়ে নিশ্চিত করব।")
        return "তোমার বসানো নিয়মগুলো:\n" + txt
    return None


# ------------------------------------------- N13: skill drafts + approval
def draft_plugin_only(name, trigger, response):
    """Write a skill draft WITHOUT installing (Monir approves later)."""
    safe = re.sub(r"[^a-z0-9_]+", "_", name.lower()).strip("_") or "skill"
    fname = f"plugin_{safe}.py"
    code = PLUGIN_TEMPLATE.format(name=name, trigger=trigger.lower(),
                                  response=response, today=str(date.today()))
    if any(b in code for b in BANNED):
        return "খসড়ায় নিষিদ্ধ জিনিস ছিল, বাতিল করলাম।"
    (DRAFTS / fname).write_text(code, encoding="utf-8")
    log_change(f"N13: নতুন স্কিলের খসড়া তৈরি — {name} (trigger: {trigger})")
    return (f"স্কিলটার খসড়া বানিয়ে রাখলাম: '{trigger}' বললে উত্তর দেবে। "
            "ইনস্টল করতে বলো: 'খসড়া অনুমোদন করো'। খসড়া দেখতে: 'খসড়া দেখাও'।")


def drafts_list_text():
    files = sorted(DRAFTS.glob("plugin_*.py"))
    if not files:
        return "এখন কোনো স্কিলের খসড়া জমা নেই।"
    return "জমা থাকা স্কিল-খসড়া:\n" + "\n".join("• " + f.name for f in files)


def approve_drafts():
    """Sandbox-test every draft; install only the ones that pass."""
    files = sorted(DRAFTS.glob("plugin_*.py"))
    if not files:
        return "অনুমোদনের জন্য কোনো খসড়া নেই।"
    done, failed = [], []
    for draft in files:
        try:
            out = subprocess.run(
                [sys.executable, "-c",
                 f"import importlib.util; s=importlib.util.spec_from_file_location('p', r'{draft}');"
                 "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print(m.self_test())"],
                capture_output=True, text=True, timeout=6)
            if out.returncode == 0 and "True" in out.stdout:
                shutil.move(str(draft), str(PLUGINS / draft.name))
                done.append(draft.name)
            else:
                failed.append(draft.name)
        except Exception:
            failed.append(draft.name)
    if done:
        register_capability("draft-approved", f"অনুমোদিত স্কিল: {', '.join(done)}")
        v = bump_version("minor")
        log_change(f"N13: খসড়া অনুমোদনে স্কিল ইনস্টল — {', '.join(done)} (v{v})")
    msg = []
    if done:
        msg.append("ইনস্টল হয়ে গেছে: " + ", ".join(done))
    if failed:
        msg.append("টেস্টে পাস করেনি, খসড়াতেই রইল: " + ", ".join(failed))
    return "খসড়া যাচাই শেষ। " + " ".join(msg)


def selfmod_handle(text, low):
    if "খসড়া দেখাও" in text or "খসড়া তালিকা" in text:
        return drafts_list_text()
    if "খসড়া অনুমোদন" in text or "স্কিল অনুমোদন" in text:
        return approve_drafts()
    m = re.search(r"(?:স্কিলের খসড়া|খসড়া স্কিল)[:\- ]*(.+)", text)
    if m:
        kv = {}
        for p in [p.strip() for p in re.split(r"\|", m.group(1))]:
            if "=" in p:
                k, v = p.split("=", 1)
                kv[k.strip().lower()] = v.strip()
        if kv.get("নাম") or kv.get("name"):
            return draft_plugin_only(kv.get("নাম") or kv.get("name"),
                                     kv.get("যখন") or kv.get("trigger") or "হ্যালো",
                                     kv.get("উত্তর") or kv.get("reply") or "হ্যালো!")
        return "এভাবে বলো: স্কিলের খসড়া: নাম=x | যখন=trigger | উত্তর=reply"
    return None


# ------------------------------------------------------------ agent fleet
AGENT_DEFS = {
    "research": {"name": "গবেষক", "icon": "🔬"},
    "news": {"name": "খবর-সংগ্রহকারী", "icon": "📰"},
    "study": {"name": "পড়া-সহকারী", "icon": "📚"},
    "pc": {"name": "PC-সহকারী", "icon": "🖥️"},
}
AGENT_JOBS = []
_agent_lock = threading.Lock()
_agent_seq = {"n": 0}


def _job_update(job, step=None, status=None, result=None):
    with _agent_lock:
        if step is not None:
            job["done_steps"] = step
        if status:
            job["status"] = status
            if status == "শেষ":
                job["done_steps"] = len(job["steps"])
        if result is not None:
            try:
                result = apply_call_name(result)
            except Exception:
                pass
            job["result"] = result


def _run_job(job):
    kind, payload = job["kind"], job["payload"]
    try:
        if kind == "research":
            _job_update(job, step=1)
            found = web_search(payload, 5)
            _job_update(job, step=2)
            summary = None
            try:
                summary = ask_gemini(
                    f"এই ওয়েব-ফলাফলের ভিত্তিতে '{payload}' বিষয়ে ছোট, পরিষ্কার বাংলায় "
                    f"একটি গবেষণা-সারাংশ লেখো (৫-৭ লাইন):\n{found}", get_memory())
            except Exception:
                summary = None
            _job_update(job, step=3, status="শেষ",
                        result=summary or found)
        elif kind == "news":
            _job_update(job, step=1)
            out = get_news(6)
            _job_update(job, step=2, status="শেষ", result=out)
        elif kind == "study":
            _job_update(job, step=1)
            wb = load_json(DATA / "study-wrong-book.json", [])
            prog = load_json(DATA / "study-progress.json", {})
            lines = ["📚 রিভিশন পরিকল্পনা:"]
            if isinstance(wb, list) and wb:
                topics = {}
                for w in wb:
                    topics[w.get("topic", "সাধারণ")] = topics.get(w.get("topic", "সাধারণ"), 0) + 1
                lines.append(f"ভুলের খাতায় মোট {len(wb)}টা প্রশ্ন জমা আছে।")
                for tpc, n in sorted(topics.items(), key=lambda x: -x[1])[:3]:
                    lines.append(f"• সবচেয়ে দুর্বল টপিক: {tpc} ({n}টা ভুল)")
                lines.append("আগে এই টপিকগুলোর ভুল প্রশ্ন আবার দেখো, তারপর নতুন মক টেস্ট দাও।")
            else:
                lines.append("ভুলের খাতা এখনো খালি — আগে একটা মক টেস্ট দিলে দুর্বল জায়গা ধরা পড়বে।")
            if isinstance(prog, dict) and prog:
                for subj, s in list(prog.items())[:4]:
                    if isinstance(s, dict):
                        lines.append(f"• {subj}: {s.get('sessions', 0)}টা সেশন, শেষ বিষয়: {s.get('last_topic', '—')}")
            _job_update(job, step=2, status="শেষ", result="\n".join(lines))
        elif kind == "pc":
            _job_update(job, step=1)
            out = system_info()
            _job_update(job, step=2, status="শেষ", result=out)
        else:
            _job_update(job, status="ব্যর্থ", result="এই ধরনের কাজ এখনো শিখিনি।")
    except Exception as e:
        _job_update(job, status="ব্যর্থ", result=f"কাজটা করতে গিয়ে সমস্যা হলো: {e}")
    job["finished_ts"] = time.time()
    job["reported"] = False


def delegate_agent(kind, title, payload):
    steps_map = {
        "research": ["পরিকল্পনা তৈরি", "ওয়েব সার্চ", "তথ্য যাচাই ও সারাংশ", "রিপোর্ট তৈরি"],
        "news": ["সোর্স থেকে খবর আনা", "সাজিয়ে রিপোর্ট তৈরি"],
        "study": ["ভুলের খাতা ও অগ্রগতি দেখা", "রিভিশন পরিকল্পনা তৈরি"],
        "pc": ["সিস্টেমের তথ্য সংগ্রহ", "রিপোর্ট তৈরি"],
    }
    with _agent_lock:
        _agent_seq["n"] += 1
        job = {"id": _agent_seq["n"], "kind": kind,
               "agent": AGENT_DEFS.get(kind, {}).get("name", kind),
               "icon": AGENT_DEFS.get(kind, {}).get("icon", "🤖"),
               "title": title, "payload": payload,
               "status": "চলছে", "steps": steps_map.get(kind, ["কাজ করা"]),
               "done_steps": 0, "result": "", "reported": True,
               "ts": datetime.now().strftime("%I:%M %p"), "finished_ts": None}
        AGENT_JOBS.append(job)
        del AGENT_JOBS[:-20]
    threading.Thread(target=_run_job, args=(job,), daemon=True).start()
    return job


def agent_jobs_public():
    with _agent_lock:
        return {"jobs": [dict(j) for j in reversed(AGENT_JOBS)]}


def agents_api(data):
    if (data or {}).get("action") == "ack":
        jid = data.get("id")
        with _agent_lock:
            for j in AGENT_JOBS:
                if j["id"] == jid:
                    j["reported"] = True
        return {"ok": True}
    return agent_jobs_public()


def agents_status_text():
    with _agent_lock:
        jobs = list(AGENT_JOBS)
    if not jobs:
        return ("এখন কোনো এজেন্ট কাজে নেই। কাজ দিতে বলো: 'গবেষণা করো: <বিষয়>', "
                "'রিভিশন প্ল্যান বানাও', 'খবর সাজিয়ে দাও' বা 'সিস্টেম রিপোর্ট বানাও'।")
    lines = ["এজেন্টদের অবস্থা:"]
    for j in jobs[-6:]:
        if j["status"] == "চলছে":
            cur = j["steps"][min(j["done_steps"], len(j["steps"]) - 1)]
            lines.append(f"• {j['icon']} {j['agent']}: '{j['title']}' — চলছে ({cur})")
        else:
            lines.append(f"• {j['icon']} {j['agent']}: '{j['title']}' — {j['status']}")
    return "\n".join(lines)


def agents_handle(text, low):
    if "কতদূর হলো" in text or "এজেন্টদের অবস্থা" in text or "এজেন্ট স্ট্যাটাস" in text:
        return agents_status_text()
    m = re.search(r"(?:গবেষণা|রিসার্চ|research)\s*করো[:\- ]+(.+)", text, re.I)
    if m:
        topic = m.group(1).strip()
        job = delegate_agent("research", f"গবেষণা: {topic[:40]}", topic)
        return (f"গবেষককে কাজে লাগিয়ে দিয়েছি 🔬 — বিষয়: {topic}। "
                "আমি তোমার সঙ্গে কথা চালিয়ে যাচ্ছি; গবেষণা শেষ হলেই রিপোর্টটা এখানে এসে যাবে। "
                "মাঝপথে জানতে চাইলে বলো: 'কতদূর হলো?'")
    if "রিভিশন প্ল্যান" in text or "পড়ার পরিকল্পনা বানাও" in text:
        delegate_agent("study", "রিভিশন পরিকল্পনা", "")
        return "পড়া-সহকারীকে লাগিয়ে দিয়েছি 📚 — ভুলের খাতা দেখে রিভিশন পরিকল্পনা বানাচ্ছে। শেষ হলেই জানাচ্ছি।"
    if "খবর সাজিয়ে" in text or "খবরের সারাংশ বানাও" in text:
        delegate_agent("news", "খবরের সারাংশ", "")
        return "খবর-সংগ্রহকারী কাজে নেমেছে 📰 — আজকের খবর সাজিয়ে আনছে।"
    if "সিস্টেম রিপোর্ট বানাও" in text or "PC-র রিপোর্ট" in text:
        delegate_agent("pc", "সিস্টেম রিপোর্ট", "")
        return "PC-সহকারী রিপোর্ট বানাচ্ছে 🖥️ — একটু পরেই পেয়ে যাবে।"
    m = re.search(r"এজেন্ট দিয়ে করাও[:\- ]+(.+)", text)
    if m:
        topic = m.group(1).strip()
        delegate_agent("research", f"কাজ: {topic[:40]}", topic)
        return f"এজেন্টকে কাজটা দিয়ে দিয়েছি: {topic}। শেষ হলেই রিপোর্ট আসবে।"
    return None


# ------------------------------------------------- away tasks (N5 / N14-lite)
def away_load():
    items = load_json(AWAY_FILE, [])
    return items if isinstance(items, list) else []


def away_handle(text, low):
    if "আমি যাচ্ছি" in text and ("করে রেখো" in text or "করে রাখো" in text or ":" in text or "ঃ" in text):
        m = re.split(r"করে রেখো[:\- ]*|করে রাখো[:\- ]*|[:：]", text, maxsplit=1)
        rest = m[-1].strip() if len(m) > 1 else ""
        items = [s.strip() for s in re.split(r",|、|এবং|ও ", rest) if s.strip()] or ([rest] if rest else [])
        if not items:
            return "কী কী করে রাখব, সেটা একবারে বলে দাও — যেমন: 'আমি যাচ্ছি, করে রেখো: খবর সাজানো, রিভিশন প্ল্যান'।"
        tasks = away_load()
        for it in items:
            tasks.append({"text": it, "ts": now_str(), "status": "অপেক্ষায়"})
        save_json(AWAY_FILE, tasks[-50:])
        try:
            (DATA / "away-since.txt").write_text(str(time.time()), encoding="utf-8")
        except Exception:
            pass
        log_change("Away-mode: কাজের তালিকা নেওয়া হলো — " + "; ".join(items)[:100])
        return ("ঠিক আছে, তুমি যাও — আমি জেগে আছি। এই কাজগুলো করে রাখছি:\n" +
                "\n".join("• " + i for i in items) +
                "\nফিরে এসে 'আমি এসেছি' বললেই পুরো হিসাব শুনিয়ে দেব।")
    if "আমি এসেছি" in text or "আমি ফিরেছি" in text or "আমি ফিরলাম" in text:
        since = 0.0
        try:
            since = float((DATA / "away-since.txt").read_text(encoding="utf-8").strip())
        except Exception:
            pass
        tasks = away_load()
        mine = [t for t in tasks if t.get("status") == "অপেক্ষায়"]
        lines = ["ফিরে আসায় স্বাগতম! তুমি না থাকতে যা যা হলো:"]
        if mine:
            lines.append("তোমার দিয়ে যাওয়া কাজ:")
            lines += ["• " + t["text"] for t in mine]
            for t in tasks:
                if t.get("status") == "অপেক্ষায়":
                    t["status"] = "দেখানো হয়েছে"
            save_json(AWAY_FILE, tasks)
        with _agent_lock:
            done = [j for j in AGENT_JOBS
                    if j.get("finished_ts") and j["finished_ts"] >= since and j["status"] == "শেষ"]
        if done:
            lines.append("শেষ হওয়া এজেন্ট-কাজ:")
            lines += [f"• {j['icon']} {j['title']}" for j in done]
        if not mine and not done:
            lines.append("বিশেষ কিছু জমা ছিল না — সব শান্ত ছিল।")
        return "\n".join(lines)
    return None


def tasks_api(data):
    if data and data.get("text"):
        tasks = away_load()
        tasks.append({"text": str(data["text"]).strip()[:200],
                      "ts": now_str(), "status": "অপেক্ষায়"})
        save_json(AWAY_FILE, tasks[-50:])
        return {"ok": True, "tasks": tasks}
    return {"tasks": away_load()}


# -*- coding: utf-8 -*-
# =============================================================================
#  Desktop Sokhi v1.5.0 — WAVE-3 daily-life pack (SELF-CONTAINED snippets)
#  Features: #212 বাজার-তালিকা · #334 আজকের অজানা সত্য + #324 প্রবাদ ·
#            #143 শুভেচ্ছা-সঙ্গী · #740 প্রেরণা-ব্যাংক + #573 ছোট জয়ের হিসাব ·
#            #450 দিনের শেষ লাইন + #572 লক্ষ্যের দৃশ্য
# -----------------------------------------------------------------------------
#  HOW TO INTEGRATE: paste this whole block into sokhi.py (see
#  INTEGRATION-DAILY.md for the exact anchor). It uses ONLY names that
#  already exist in sokhi.py:  DATA, load_json, save_json, now_str,
#  re, time, date, datetime.  No new imports, no network, 100% offline.
#  File paths are resolved lazily (DATA / ...) inside helpers, so this
#  block can sit anywhere after the utilities section.
#  Data files (created on first use, inside DATA = data/ folder):
#      bazaar.json = [{id, item, qty, est_price, bought, ts}]
#      wins.json   = [{id, text, date, ts}]
# =============================================================================


def _dl_bn(s):
    """ASCII digits -> Bangla digits (local copy; pack stays self-contained)."""
    return str(s).translate(str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯"))


def _dl_money(v):
    """Format a price: 300.0 -> '৩০০', 12.5 -> '১২.৫'."""
    try:
        f = float(v)
    except Exception:
        return "০"
    s = str(int(f)) if f == int(f) else str(f)
    return _dl_bn(s)


def _dl_next_id(items):
    mx = 0
    for it in items:
        try:
            mx = max(mx, int(it.get("id", 0)))
        except Exception:
            pass
    return mx + 1


# ------------------------------------------------------------ #212: বাজার
def _bazaar_load():
    items = load_json(DATA / "bazaar.json", [])
    if not isinstance(items, list):
        return []
    return [it for it in items if isinstance(it, dict)]


def _bazaar_save(items):
    save_json(DATA / "bazaar.json", items[-200:])


def _bazaar_totals(items):
    total = sum(float(it.get("est_price") or 0) for it in items)
    bought = sum(float(it.get("est_price") or 0) for it in items if it.get("bought"))
    return total, bought, total - bought


def bazaar_api(data):
    """POST /api/bazaar handler — house pattern (cf. tasks_api/memory_api).

    Actions:
      (none)/list -> {ok, items, total, bought_total, pending_total}
      add    {item, qty, est_price}   est_price = ওই আইটেমের আনুমানিক মোট দাম
      toggle {id}                     bought ফ্লিপ করে
      delete {id}
      clear_bought                    কেনা হয়ে যাওয়া আইটেম মুছে দেয়
    """
    data = data or {}
    action = str(data.get("action") or "list").strip()
    items = _bazaar_load()
    if action == "add":
        item = str(data.get("item") or "").strip()
        if not item:
            return {"ok": False, "error": "কী কিনতে হবে, সেটা লিখে দাও।"}
        try:
            price = float(data.get("est_price") or 0)
        except Exception:
            price = 0.0
        items.append({
            "id": _dl_next_id(items),
            "item": item[:120],
            "qty": str(data.get("qty") or "").strip()[:40],
            "est_price": max(0.0, price),
            "bought": False,
            "ts": now_str(),
        })
        _bazaar_save(items)
    elif action == "toggle":
        try:
            want = int(data.get("id"))
        except Exception:
            return {"ok": False, "error": "আইটেমের নম্বরটা ঠিক করে পাঠাও।"}
        hit = False
        for it in items:
            if it.get("id") == want:
                it["bought"] = not bool(it.get("bought"))
                hit = True
        if not hit:
            return {"ok": False, "error": "এই নম্বরের কোনো আইটেম পাইনি।"}
        _bazaar_save(items)
    elif action == "delete":
        try:
            want = int(data.get("id"))
        except Exception:
            return {"ok": False, "error": "আইটেমের নম্বরটা ঠিক করে পাঠাও।"}
        new = [it for it in items if it.get("id") != want]
        if len(new) == len(items):
            return {"ok": False, "error": "এই নম্বরের কোনো আইটেম পাইনি।"}
        items = new
        _bazaar_save(items)
    elif action == "clear_bought":
        items = [it for it in items if not it.get("bought")]
        _bazaar_save(items)
    elif action != "list":
        return {"ok": False, "error": "কী করতে হবে বুঝতে পারিনি — action ঠিক করে পাঠাও।"}
    total, bought_total, pending_total = _bazaar_totals(items)
    return {"ok": True, "items": items, "total": total,
            "bought_total": bought_total, "pending_total": pending_total}


def bazaar_text():
    """Chat summary for the 'বাজার' command (#212)."""
    items = _bazaar_load()
    if not items:
        return ("🛒 তোমার বাজারের তালিকা এখন খালি। যোগ করতে বলো: "
                "'বাজারে যোগ করো চাল' — অথবা টাস্ক ট্যাবের বাজার অংশে "
                "নিজে লিখে যোগ করতে পারো।")
    total, bought_total, pending_total = _bazaar_totals(items)
    lines = ["🛒 তোমার বাজারের তালিকা:"]
    for it in items:
        mark = "✅" if it.get("bought") else "⬜"
        qty = f" ({it['qty']})" if it.get("qty") else ""
        price = f" — আনুমানিক {_dl_money(it.get('est_price') or 0)} টাকা" \
            if float(it.get("est_price") or 0) > 0 else ""
        lines.append(f"{mark} {it.get('item', '')}{qty}{price}")
    lines.append(f"আনুমানিক মোট খরচ: {_dl_money(total)} টাকা "
                 f"(কেনা হয়েছে {_dl_money(bought_total)} টাকার, "
                 f"বাকি {_dl_money(pending_total)} টাকা)")
    return "\n".join(lines)


def bazaar_parse_add(text):
    """'বাজারে যোগ করো X' পার্স করে bazaar_api(add) চালায়।
    ঐচ্ছিক রূপ: 'বাজারে যোগ করো চাল, পরিমাণ ৫ কেজি, দাম ৩০০'
    (দাম = ওই আইটেমের আনুমানিক মোট দাম)। কোনোটা না মিললে পুরোটাই item।"""
    m = re.search(r"বাজারে যোগ করো[:\- ]+(.+)", text or "")
    if not m:
        return None
    rest = m.group(1).strip().rstrip("।")
    if not rest:
        return "কী যোগ করব বাজারে? যেমন বলো: 'বাজারে যোগ করো চাল'।"
    qty, price = "", 0.0
    mq = re.search(r"পরিমাণ[:\- ]*([^,।]+)", rest)
    if mq:
        qty = mq.group(1).strip()
    mp = re.search(r"দাম[:\- ]*([০-৯0-9.]+)", rest)
    if mp:
        try:
            price = float(mp.group(1).translate(
                str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")))
        except Exception:
            price = 0.0
    item = re.split(r"[,،]", rest)[0].strip()
    item = re.sub(r"পরিমাণ[:\- ]*.+$", "", item).strip() or rest
    r = bazaar_api({"action": "add", "item": item, "qty": qty,
                    "est_price": price})
    if not r.get("ok"):
        return r.get("error", "যোগ করা গেল না।")
    extra = f" ({qty})" if qty else ""
    extra += f" — আনুমানিক {_dl_money(price)} টাকা" if price > 0 else ""
    return (f"🛒 বাজারের তালিকায় যোগ করলাম: {item}{extra}। "
            "পুরো তালিকা দেখতে বলো: 'বাজার'।")


# ------------------------------------------- #334 আজকের সত্য + #324 প্রবাদ
# Static, curated, well-known content only — no invented statistics.
# (আলোর গতি জাতীয় সংখ্যায় 'প্রায়' বলা হয়েছে।)
DAILY_FACTS = [
    "বাংলাদেশের জাতীয় ফল কাঁঠাল।",
    "বাংলাদেশের জাতীয় মাছ ইলিশ।",
    "বাংলাদেশের জাতীয় পাখি দোয়েল।",
    "বাংলাদেশের জাতীয় ফুল শাপলা।",
    "বাংলাদেশের জাতীয় গাছ আম গাছ।",
    "বাংলাদেশের জাতীয় কবি কাজী নজরুল ইসলাম।",
    "বাংলাদেশের জাতীয় সংগীতের রচয়িতা বিশ্বকবি রবীন্দ্রনাথ ঠাকুর।",
    "১৯৫২ সালের ২১ ফেব্রুয়ারি ভাষা শহীদ দিবস — দিনটি এখন আন্তর্জাতিক মাতৃভাষা দিবস হিসেবে বিশ্বজুড়ে পালিত হয়।",
    "১৯৭১ সালের ১৬ ডিসেম্বর বাংলাদেশের বিজয় দিবস।",
    "২৬ মার্চ বাংলাদেশের স্বাধীনতা দিবস।",
    "ঢাকা বাংলাদেশের রাজধানী ও সবচেয়ে বড় শহর।",
    "বাংলা বাংলাদেশের রাষ্ট্রভাষা।",
    "বঙ্গবন্ধু শেখ মুজিবুর রহমান বাংলাদেশের জাতির পিতা।",
    "জাতীয় সংসদ ভবন ঢাকার শেরেবাংলা নগরে অবস্থিত।",
    "পদ্মা, মেঘনা ও যমুনা বাংলাদেশের প্রধান নদীগুলোর অন্যতম।",
    "ধান বাংলাদেশের প্রধান খাদ্যশস্য।",
    "বাংলাদেশে বছরে ছয়টি ঋতু — গ্রীষ্ম, বর্ষা, শরৎ, হেমন্ত, শীত ও বসন্ত।",
    "সুন্দরবন বিশ্বের বৃহত্তম ম্যানগ্রোভ বনগুলোর একটি এবং রয়েল বেঙ্গল টাইগারের আবাসস্থল।",
    "চাঁদ পৃথিবীর একমাত্র প্রাকৃতিক উপগ্রহ।",
    "সৌরজগতে মোট আটটি গ্রহ আছে।",
    "সূর্যের সবচেয়ে কাছের গ্রহ বুধ।",
    "পৃথিবীর সবচেয়ে বড় মহাসাগর প্রশান্ত মহাসাগর।",
    "মাউন্ট এভারেস্ট পৃথিবীর সর্বোচ্চ পর্বতশৃঙ্গ।",
    "নীল তিমি পৃথিবীর সবচেয়ে বড় প্রাণী।",
    "পানির রাসায়নিক সংকেত H2O।",
    "অক্সিজেনের রাসায়নিক প্রতীক O এবং সোনার প্রতীক Au।",
    "প্রাপ্তবয়স্ক মানুষের শরীরে ২০৬টি হাড় থাকে।",
    "মানুষের হৃদপিণ্ডে চারটি প্রকোষ্ঠ থাকে।",
    "আলো শূন্যস্থানে প্রতি সেকেন্ডে প্রায় ৩ লক্ষ কিলোমিটার বেগে চলে।",
    "মৌমাছি নাচের মাধ্যমে অন্য মৌমাছিদের ফুলের দিক্‌নির্দেশনা দেয় — একে 'ওয়াগল নাচ' বলে।",
]

DAILY_PROVERBS = [
    ("অতি চালাকের গলায় দড়ি", "অতিরিক্ত চালাকি শেষে নিজেরই বিপদ ডেকে আনে।"),
    ("অধিক সন্ন্যাসীতে গাজন নষ্ট", "কর্তা বেশি হলে কাজের বারোটা বাজে।"),
    ("অল্প বিদ্যা ভয়ংকরী", "অল্প জ্ঞান নিয়ে অহংকার করা বিপজ্জনক।"),
    ("আপন ভালো তো জগৎ ভালো", "নিজে ভালো হলে চারপাশকেও ভালো মনে হয়।"),
    ("ইচ্ছা থাকলে উপায় হয়", "মন থেকে চাইলে পথ একটা বের হবেই।"),
    ("উঠতি মূলো পত্তনেই চেনা যায়", "শুরুর লক্ষণ দেখেই ভবিষ্যৎ বোঝা যায়।"),
    ("এক মাঘে শীত যায় না", "একবারের ঘটনাতেই সব শেষ হয়ে যায় না।"),
    ("এক ঢিলে দুই পাখি", "এক কাজে দুটি ফল পাওয়া।"),
    ("কষ্ট বিনা কেষ্ট মেলে না", "কষ্ট ছাড়া সাফল্য বা প্রিয় জিনিস মেলে না।"),
    ("কানা ছেলের নাম পদ্মলোচন", "অযোগ্য জিনিসকে বাড়তি নাম-সম্মান দেওয়া।"),
    ("কুমিরের কান্না", "লোক দেখানো, ভান করা দুঃখ।"),
    ("খাল কেটে কুমির আনা", "নিজের বিপদ নিজেই ডেকে আনা।"),
    ("গাছে কাঁঠাল, গোঁফে তেল", "ফল পাওয়ার আগেই ভোগের আয়োজন করা।"),
    ("ঘোড়া ডিঙিয়ে ঘাস খাওয়া", "নিয়ম বা ঊর্ধ্বতনকে পাশ কাটিয়ে কাজ করা।"),
    ("চোরের মন পুলিশ পুলিশ", "অপরাধীর মনে সবসময় ধরা পড়ার ভয় থাকে।"),
    ("জলে কুমির ডাঙায় বাঘ", "যেদিকেই যাও, বিপদ — উভয় সংকট।"),
    ("তিলকে তাল করা", "ছোট ঘটনাকে ফুলিয়ে-ফাঁপিয়ে বড় করা।"),
    ("দশে মিলি করি কাজ, হারি জিতি নাহি লাজ", "সবাই মিলে কাজ করলে হার-জিতে লজ্জা নেই।"),
    ("ধরি মাছ না ছুঁই পানি", "কষ্ট বা ঝুঁকি ছাড়াই লাভ চাওয়া।"),
    ("নাচতে না জানলে উঠোন বাঁকা", "নিজের অযোগ্যতা ঢাকতে অন্যের দোষ দেওয়া।"),
    ("পিপীলিকার পাখা ওঠে মরিবার তরে", "অহংকার বেড়ে যাওয়া পতনের লক্ষণ।"),
    ("বামন হয়ে চাঁদে হাত", "সাধ্যের বাইরে বড় আকাঙ্ক্ষা করা।"),
    ("ভাবিয়া করিও কাজ, করিয়া ভাবিও না", "কাজ শুরুর আগে ভাবো; শুরু করে আফসোস কোরো না।"),
    ("মরা হাতি লাখ টাকা", "বড় জিনিস ক্ষয়ে গেলেও তার মূল্য থেকে যায়।"),
    ("রতনে রতন চেনে", "যোগ্য লোকই অন্যের যোগ্যতা বুঝতে পারে।"),
    ("লোভে পাপ, পাপে মৃত্যু", "লোভ মানুষকে অন্যায়ে ঠেলে ধ্বংস ডাকে।"),
    ("সবুরে মেওয়া ফলে", "ধৈর্য ধরে অপেক্ষা করলে ভালো ফল আসে।"),
    ("হাতি ঘোড়া গেল তল, মশা বলে কত জল", "ক্ষমতাহীনের বড় বড় কথা বলা।"),
    ("অতি লোভে তাঁতি নষ্ট", "অতিরিক্ত লোভে যা ছিল, তাও হারাতে হয়।"),
    ("কাঁটা দিয়ে কাঁটা তোলা", "সমস্যা বা প্রতিপক্ষ দিয়েই সমস্যার সমাধান করা।"),
]


def daily_card(for_date=None):
    """GET /api/dailycard-এর backend (#334 + #324)।
    Deterministic by date ordinal: একই দিনে সারাদিন একই কার্ড, পরদিন নতুন।
    for_date: datetime.date (না দিলে আজ)। Returns JSON-able dict."""
    d = for_date or date.today()
    try:
        ordinal = d.toordinal()
    except Exception:
        ordinal = 0
    fact = DAILY_FACTS[ordinal % len(DAILY_FACTS)]
    proverb, meaning = DAILY_PROVERBS[(ordinal * 11 + 5) % len(DAILY_PROVERBS)]
    return {"ok": True, "date": str(d), "fact": fact,
            "proverb": proverb, "meaning": meaning}


def daily_card_text(for_date=None):
    """Chat form of daily_card — 'আজকের তথ্য' কমান্ডের উত্তর।"""
    c = daily_card(for_date)
    return ("🌞 আজকের তথ্য\n"
            f"💡 অজানা সত্য: {c['fact']}\n"
            f"📜 প্রবাদ: {c['proverb']}\n"
            f"মানে: {c['meaning']}")


# ------------------------------------------------------- #143: শুভেচ্ছা-সঙ্গী
GREETING_OCCASIONS = ("জন্মদিন", "ঈদ", "বিয়ে", "নতুন চাকরি", "পরীক্ষা", "সাধারণ")

_GREETING_TEMPLATES = {
    "জন্মদিন": [
        "শুভ জন্মদিন, {name}! 🎂 তোমার নতুন বছরটা সুস্থতা, সাফল্য আর হাসিতে ভরে উঠুক। অনেক অনেক শুভকামনা রইল।",
        "{name}, জন্মদিনের অনেক অনেক শুভেচ্ছা! তোমার সব স্বপ্ন একে একে পূরণ হোক — এটাই কামনা করি।",
        "আজ তোমার বিশেষ দিন, {name}! শুভ জন্মদিন — আগামী দিনগুলো হোক আরও উজ্জ্বল ও আনন্দময়।",
    ],
    "ঈদ": [
        "ঈদ মোবারক, {name}! 🌙 তোমার ও তোমার পরিবারের জন্য রইল সুখ, শান্তি আর সমৃদ্ধির শুভকামনা।",
        "{name}, ঈদের শুভেচ্ছা নাও! এই ঈদ তোমার জীবনে নিয়ে আসুক আনন্দ আর কাছের মানুষদের ভালোবাসা।",
        "চাঁদ রাতের শুভেচ্ছা, {name}! ঈদ মোবারক — দিনটা কাটুক প্রিয়জনদের সঙ্গে হাসি-আনন্দে।",
    ],
    "বিয়ে": [
        "অভিনন্দন, {name}! 💐 তোমাদের নতুন জীবন হোক ভালোবাসা, বোঝাপড়া আর সুখে ভরপুর। শুভ বিবাহ!",
        "{name}, বিয়ের অনেক অনেক শুভেচ্ছা! দুজনের যৌথ যাত্রা হোক আজীবন সুন্দর ও শান্তিময়।",
        "শুভ বিবাহ, {name}! তোমাদের সংসার জীবনে বরকত ও আনন্দ চিরস্থায়ী হোক — এই দোয়া রইল।",
    ],
    "নতুন চাকরি": [
        "অভিনন্দন, {name}! 🎉 নতুন চাকরিতে যোগদানের জন্য অনেক শুভকামনা — তোমার পরিশ্রমের ফল এটা। নতুন যাত্রা শুভ হোক!",
        "{name}, নতুন চাকরির খবরে খুব খুশি হলাম! কর্মজীবনে তুমি আরও অনেক দূর এগিয়ে যাও — এই কামনা রইল।",
        "শুভকামনা, {name}! নতুন কর্মস্থলে প্রথম দিন থেকে সবকিছু ভালো যাক — তুমি পারবে, এই বিশ্বাস আছে।",
    ],
    "পরীক্ষা": [
        "পরীক্ষার জন্য অনেক শুভকামনা, {name}! 📚 শান্ত মাথায় দাও — প্রস্তুতি অনুযায়ী ফল ভালোই হবে, ইনশাআল্লাহ।",
        "{name}, পরীক্ষার আগের দুশ্চিন্তা স্বাভাবিক — তুমি তোমার সেরাটা দাও, ফল নিয়ে ভেবো না। শুভকামনা রইল!",
        "Best of luck, {name}! মনোযোগ দিয়ে লেখো, সময়ের হিসাব রেখো — তোমার সাফল্য কামনা করি।",
    ],
    "সাধারণ": [
        "অনেক অনেক শুভেচ্ছা, {name}! তোমার দিনটা ভালো কাটুক, মনটা থাকুক হালকা আর খুশি। 🌼",
        "{name}, তোমার জন্য রইল আন্তরিক শুভকামনা — যা করছ, তাতে সাফল্য পাও, সুস্থ থাকো।",
        "শুভেচ্ছা রইল, {name}! ছোট এই বার্তাটা তোমার মুখে একটু হাসি ফোটালেই আমার সার্থক।",
    ],
}


def greeting_text(name, occasion="সাধারণ", for_date=None):
    """#143: warm Bangla greeting draft. 2-3 variants per occasion,
    rotated deterministically by day-of-year (same day = same draft).
    এটা খসড়া (template) — পাঠানোর আগে নিজের মতো বদলে নেওয়া যায়।"""
    name = str(name or "").strip()[:60] or "বন্ধু"
    occasion = str(occasion or "সাধারণ").strip()
    if occasion not in _GREETING_TEMPLATES:
        occasion = "সাধারণ"
    variants = _GREETING_TEMPLATES[occasion]
    d = for_date or date.today()
    try:
        idx = d.timetuple().tm_yday % len(variants)
    except Exception:
        idx = 0
    return variants[idx].format(name=name)


def greeting_parse(text):
    """'শুভেচ্ছা <নাম> <উপলক্ষ>' পার্স করে। উপলক্ষ চেনা না গেলে পুরো
    বাকি অংশটাই নাম ধরা হয় এবং উপলক্ষ হয় 'সাধারণ'।
    Returns (name, occasion) or None."""
    m = re.search(r"শুভেচ্ছা(?:\s+জানাও|\s+দাও)?[:\- ]+(.+)", text or "")
    if not m:
        return None
    rest = m.group(1).strip().rstrip("।").strip()
    if not rest:
        return None
    # উপলক্ষ সাধারণত শেষে থাকে: 'শুভেচ্ছা রহিম জন্মদিন'
    for occ in GREETING_OCCASIONS:
        if occ != "সাধারণ" and rest.endswith(occ):
            name = rest[: -len(occ)].strip(" ,-")
            if name:
                return name, occ
    # অথবা শুরুতে: 'শুভেচ্ছা জন্মদিনের রহিম' জাতীয় রূপ না মিললে সাধারণ
    return rest, "সাধারণ"


# ------------------------------------------- #740 প্রেরণা-ব্যাংক + #573 জয়
def _wins_load():
    items = load_json(DATA / "wins.json", [])
    if not isinstance(items, list):
        return []
    return [it for it in items if isinstance(it, dict)]


def wins_api(data):
    """POST /api/wins handler (#740)। Actions: list / add {text} /
    delete {id} (বোনাস — spec-এর বাইরে হলেও UI-পরিষ্কারের জন্য দরকারি)।"""
    data = data or {}
    action = str(data.get("action") or "list").strip()
    items = _wins_load()
    if action == "add":
        text = str(data.get("text") or "").strip()
        if not text:
            return {"ok": False, "error": "জয়ের কথাটা লিখে দাও।"}
        items.append({"id": _dl_next_id(items), "text": text[:300],
                      "date": str(date.today()), "ts": now_str()})
        save_json(DATA / "wins.json", items[-500:])
    elif action == "delete":
        try:
            want = int(data.get("id"))
        except Exception:
            return {"ok": False, "error": "জয়ের নম্বরটা ঠিক করে পাঠাও।"}
        items = [it for it in items if it.get("id") != want]
        save_json(DATA / "wins.json", items)
    elif action != "list":
        return {"ok": False, "error": "কী করতে হবে বুঝতে পারিনি — action ঠিক করে পাঠাও।"}
    return {"ok": True, "items": items, "count": len(items)}


def _dl_progress_line(progress):
    """progress: None | str | int/float | dict — যেভাবেই আসুক, এক লাইন।
    dict-এ সম্ভাব্য key: sessions/সেশন, minutes/মিনিট, percent/শতাংশ, text।"""
    if progress is None or progress == "":
        return ""
    if isinstance(progress, str):
        return progress.strip()
    if isinstance(progress, (int, float)):
        return f"এ পর্যন্ত {_dl_bn(progress)} বার পড়ার সেশন হয়েছে।"
    if isinstance(progress, dict):
        txt = str(progress.get("text") or "").strip()
        if txt:
            return txt
        parts = []
        for key, label in (("sessions", "পড়ার সেশন"), ("minutes", "মিনিট পড়া"),
                           ("percent", "সিলেবাস শেষ (%)"), ("mcq", "MCQ অনুশীলন")):
            if progress.get(key) not in (None, ""):
                parts.append(f"{label}: {_dl_bn(progress[key])}")
        return " · ".join(parts)
    return str(progress).strip()


def wins_text(progress=None):
    """#573 ছোট জয়ের হিসাব: জমা জয় + (দিলে) পড়ার অগ্রগতি মিলিয়ে
    উৎসাহমূলক হিসাব। progress integrator চাইলে study_progress_text()
    বা তার dict রূপ পাঠাবে — না দিলে শুধু জয়ের তালিকাই আসে (সৎভাবে,
    কোনো সংখ্যা বানানো হয় না)।"""
    items = _wins_load()
    lines = ["🏆 ছোট জয়ের হিসাব"]
    if not items:
        lines.append("এখনো কোনো জয় জমা হয়নি। ছোট্ট একটা ভালো কাজ হলেই "
                     "বলো: 'জয় যোগ করো আজ ২ ঘণ্টা পড়েছি' — আমি জমিয়ে রাখব।")
    else:
        lines.append(f"মোট জমা জয়: {_dl_bn(len(items))}টা। সাম্প্রতিকগুলো:")
        for it in items[-10:]:
            lines.append(f"• [{it.get('date', '')}] {it.get('text', '')}")
        lines.append("এই ছোট ছোট জয়গুলোই একদিন বড় সাফল্য হবে — চালিয়ে যাও! 💪")
    pline = _dl_progress_line(progress)
    if pline:
        lines.append("📚 পড়ার অগ্রগতি: " + pline)
    return "\n".join(lines)


# ------------------------------------- #450 দিনের শেষ লাইন + #572 লক্ষ্যের দৃশ্য
def day_end_text(interactions=None, wins_today=None, studied=None,
                 for_date=None):
    """#450: দিনের শেষ লাইন — শুধু যেসব সংখ্যা প্যারামিটার হিসেবে এসেছে
    সেগুলোই ব্যবহার করে (কিছু না দিলে সাধারণ, সৎ লাইন; সংখ্যা বানায় না)।
    interactions: আজ মোট কথা/কাজের সংখ্যা · wins_today: আজকের জয় সংখ্যা ·
    studied: True/False/str (পড়া হয়েছে কিনা / কতক্ষণ)।"""
    d = for_date or date.today()
    try:
        pick = d.toordinal() % 3
    except Exception:
        pick = 0
    facts = []
    if isinstance(interactions, (int, float)) and interactions > 0:
        facts.append(f"আজ আমরা {_dl_bn(int(interactions))} বার কথা বলেছি/কাজ করেছি")
    if isinstance(wins_today, (int, float)) and wins_today > 0:
        facts.append(f"আজ {_dl_bn(int(wins_today))}টা ছোট জয় জমা হয়েছে")
    if isinstance(studied, str) and studied.strip():
        facts.append(f"পড়া: {studied.strip()}")
    elif studied is True:
        facts.append("আজ পড়াশোনাও হয়েছে")
    closers = [
        "আজকের দিনটা এখানেই গুটিয়ে নাও — কাল আবার নতুন করে শুরু হবে। 🌙",
        "ভালো হোক বা মোটামুটি, দিনটা তুমি পার করেছ — এটাই অগ্রগতি। বিশ্রাম নাও। 🌙",
        "আজ যা হয়েছে যথেষ্ট; বাকিটা কালকের জন্য থাক। শুভরাত্রি! 🌙",
    ]
    if facts:
        return "🌙 দিনের শেষ লাইন: " + "; ".join(facts) + "। " + closers[pick]
    return "🌙 দিনের শেষ লাইন: " + closers[pick]


def goal_vision_text(goal=None):
    """#572 লক্ষ্যের দৃশ্য: goal-স্ট্রিং বসিয়ে একটি ছোট visualization
    অনুচ্ছেদ (template — কোনো ভবিষ্যদ্বাণী বা মিথ্যা প্রতিশ্রুতি নয়)।"""
    goal = str(goal or "").strip()[:120] or "সরকারি চাকরি"
    return (
        f"🎯 তোমার লক্ষ্যের দৃশ্য — {goal}\n"
        f"এক মিনিট চোখ বন্ধ করে ভাবো: সকালবেলা ঘুম থেকে উঠেছ, হাতে সেই চিঠিটা — "
        f"তোমার '{goal}' পাওয়ার খবর। বাসার সবার মুখে হাসি, এতদিনের কষ্টের "
        "মুখে একটা শান্ত বিজয়ের অনুভূতি। আজকের এই পড়ার টেবিল, এই রাতজাগা — "
        "সেই সকালটার দিকেই যাচ্ছে। প্রতিটা ছোট দিন সেই ছবিটাকে এক ধাপ "
        "কাছে টানে। এবার চোখ খোলো — আজকের ধাপটা নেওয়া যাক। 💪"
    )


# ------------------------------------------------------- chat dispatch
def daily_handle(text, low=None, progress=None):
    """handle_message-এ বসানোর জন্য একটাই entry point (rules_handle /
    fullforms_handle-এর ধাঁচ)। মিল না পেলে None ফেরত দেয়।
    progress: wins_text-এর জন্য integrator চাইলে পড়ার অগ্রগতি পাঠাবে।"""
    text = (text or "").strip()
    if not text:
        return None
    try:
        # #212 — বাজার (সঠিক/ছোট রূপগুলোই ধরা হয়, যাতে 'বাজারের খবর'
        # জাতীয় অন্য বাক্য ছিনতাই না হয়)
        stripped = text.rstrip("।!? ")
        if stripped in ("বাজার", "বাজার দেখাও", "বাজারের তালিকা",
                        "বাজার তালিকা", "আমার বাজার", "বাজার তালিকা দেখাও"):
            return bazaar_text()
        _bz = bazaar_parse_add(text)
        if _bz:
            return _bz
        # #334 + #324 — আজকের তথ্য
        if "আজকের তথ্য" in text or "আজকের কার্ড" in text or \
                "আজকের প্রবাদ" in text or "অজানা সত্য" in text:
            return daily_card_text()
        # #143 — শুভেচ্ছা
        if text.startswith("শুভেচ্ছা"):
            parsed = greeting_parse(text)
            if not parsed:
                return ("কার জন্য শুভেচ্ছা বানাব? এভাবে বলো: "
                        "'শুভেচ্ছা রহিম জন্মদিন' — উপলক্ষ হতে পারে: "
                        "জন্মদিন, ঈদ, বিয়ে, নতুন চাকরি, পরীক্ষা, সাধারণ।")
            name, occ = parsed
            draft = greeting_text(name, occ)
            return (f"✉️ {name}-এর জন্য {occ} উপলক্ষে শুভেচ্ছার খসড়া "
                    f"(পাঠানোর আগে নিজের মতো সাজিয়ে নিতে পারো):\n{draft}")
        # #740 — জয় যোগ
        m = re.search(r"জয় যোগ করো[:\- ]+(.+)", text)
        if m:
            r = wins_api({"action": "add", "text": m.group(1).strip()})
            if r.get("ok"):
                return ("🏆 জয়টা জমা রাখলাম! এই ছোট জয়গুলোই তোমার "
                        "প্রেরণা-ব্যাংক। সব দেখতে বলো: 'আমার জয়গুলো'।")
            return r.get("error", "জয় যোগ করা গেল না।")
        # #573 — জয়ের হিসাব
        if "আমার জয়গুলো" in text or "ছোট জয়ের হিসাব" in text or \
                "জয়ের হিসাব" in text or "প্রেরণা ব্যাংক" in text:
            return wins_text(progress)
        # #450 — দিনশেষ ('আমার লক্ষ্য:' সেট করার রূপটা fullforms আগে
        # ধরে — এখানে শুধু দেখার রূপগুলো)
        if stripped in ("দিনশেষ", "দিনের শেষ", "দিনের শেষ লাইন",
                        "আজকের দিন শেষ"):
            _wins_today = sum(1 for it in _wins_load()
                              if it.get("date") == str(date.today()))
            return day_end_text(wins_today=_wins_today)
        # #572 — লক্ষ্যের দৃশ্য
        if stripped in ("আমার লক্ষ্য", "আমার লক্ষ্য দেখাও", "লক্ষ্য দেখাও",
                        "লক্ষ্যের দৃশ্য", "আমার স্বপ্ন", "লক্ষ্য"):
            return goal_vision_text()
        m = re.search(r"লক্ষ্যের দৃশ্য[:\- ]+(.+)", text)
        if m:
            return goal_vision_text(m.group(1).strip())
        return None
    except Exception:
        return None


# ------------------------------------------- foundation (F3 / F5 / N14) — v1.1.0 full-forms
# Bridge protocol (N14/F5, Desktop side):
#   Desktop -> outside : data/bridge/outbox/<timestamp>.json
#   outside -> Desktop : data/bridge/inbox/<timestamp>.json
#   File body: {"kind": "note|task|message|...", "text": "...", "ts": "ISO"}
#   Remaining (Muse side): a Claude/WhatsApp-side worker must pick files
#   up from outbox/, act on them and drop result files into inbox/ in the
#   same format — Desktop already knows how to read those (bridge_sync_text).
BRIDGE_DIR = DATA / "bridge"
BRIDGE_OUTBOX = BRIDGE_DIR / "outbox"
BRIDGE_INBOX = BRIDGE_DIR / "inbox"


def _bridge_dirs():
    try:
        BRIDGE_OUTBOX.mkdir(parents=True, exist_ok=True)
        BRIDGE_INBOX.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def _bridge_count(folder):
    try:
        _bridge_dirs()
        return len([p for p in folder.glob("*.json") if p.is_file()])
    except Exception:
        return 0


def foundation_status():
    cfg = get_config()
    out_n = _bridge_count(BRIDGE_OUTBOX)
    in_n = _bridge_count(BRIDGE_INBOX)
    legacy_n = 0
    try:
        legacy_n = len(load_json(BRIDGE_QUEUE_FILE, []))
    except Exception:
        legacy_n = 0
    return {
        "computer_use_gui": bool(cfg.get("computer_use_enabled", False)),
        "bridge_enabled": bool(cfg.get("bridge_enabled", False)),
        "bridge_queue": legacy_n,
        "bridge_outbox": out_n,
        "bridge_inbox": in_n,
        "bridge_protocol": "file-json-v1 (outbox/inbox, {kind, text, ts})",
        "note": ("v1.1.0 full-forms: F3 GUI computer-use (শুধু Windows, "
                 "computer_use_enabled config + প্রতিটি কাজে আলাদা "
                 "confirmation) ও N14/F5 bridge outbox/inbox ফাইল-প্রোটোকল "
                 "এখন কার্যকর। বাকি শুধু Muse/WhatsApp-পক্ষের worker: "
                 "outbox থেকে ফাইল তুলে কাজ করে inbox-এ ফল রাখলেই Desktop "
                 "তা পড়তে পারবে।"),
    }


def bridge_enqueue(item):
    """Legacy queue (bridge-queue.json) + real outbox file (v1.1.0).
    item: str or {"kind": ..., "text": ...}. Returns legacy queue length
    (same return contract as v1.0)."""
    if isinstance(item, dict):
        kind = str(item.get("kind") or "note")[:40]
        text = str(item.get("text") or item.get("item") or "")[:2000]
    else:
        kind, text = "note", str(item)[:2000]
    payload = {"kind": kind, "text": text,
               "ts": datetime.now().isoformat(timespec="seconds")}
    q = load_json(BRIDGE_QUEUE_FILE, [])
    if not isinstance(q, list):
        q = []
    q.append({"item": text[:300], "ts": now_str()})
    save_json(BRIDGE_QUEUE_FILE, q[-100:])
    try:
        _bridge_dirs()
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        save_json(BRIDGE_OUTBOX / f"{stamp}.json", payload)
    except Exception:
        pass
    return len(q)



# ------------------------------------------------------------------ brain

def insights_text(mem):
    counts = mem.get("command_counts", {})
    if not counts:
        return "ভাইয়া, এখনো প্যাটার্ন বোঝার মতো যথেষ্ট কথা হয়নি। আরেকটু ব্যবহার করলেই আমি তোমার অভ্যাস বুঝতে শুরু করব।"
    top = sorted(counts.items(), key=lambda x: -x[1])[:3]
    lines = ["ভাইয়া, তোমার ব্যবহারের প্যাটার্ন যা বুঝলাম:"]
    for k, v in top:
        lines.append(f"• '{k}' — {v} বার")
    lines.append(f"মোট {mem['interaction_count']} বার কথা হয়েছে, মনে রেখেছি {len(mem['facts'])}টা তথ্য ও {len(mem['likes'])}টা পছন্দ।")
    return "\n".join(lines)




# -*- coding: utf-8 -*-
# =============================================================================
#  Desktop Sokhi v1.1.0 — FULL-FORMS ট্র্যাক (এই সেকশনটি নতুন)
#  F1 World Model · F2 Anticipatory · F3 GUI computer-use · F4 Projects ·
#  F6 Growth diary · F7 Nightly research · F8 Prediction · N10 Coding agent ·
#  N11 Documents/Research · N14/F5 Bridge (Desktop দিক)
# -----------------------------------------------------------------------------
#  সংযোগ (coordinator করবে — এই সেকশন handle_message/HTML/TTS ছোঁয় না):
#      handle_message-এ:   _ff = fullforms_handle(text, low)
#                          if _ff: return _ff
#      panels_data-তে:     result.update(fullforms_panels()) জাতীয় মার্জ
#
#  ⚠️ Muse-পক্ষে বাকি কাজ (N14/F5): এই ফাইল থেকে WhatsApp/Muse-পক্ষের
#  worker বানানো সম্ভব নয়। প্রোটোকল: কোনো Muse-পক্ষের worker যদি
#  data/bridge/outbox/ থেকে timestamp-নামের JSON ফাইল তুলে কাজ করে
#  ফলাফল data/bridge/inbox/-এ একই ফরম্যাটে রাখে —
#  {"kind": "...", "text": "...", "ts": "ISO"} — Desktop সেটা
#  bridge_sync_text() / 'ব্রিজের বার্তা পড়ো' দিয়ে পড়তে পারবে।
#  সব ফাইল DATA (data/) ফোল্ডারে; stdlib only; Windows-নির্ভর অংশে
#  OS-guard — Linux-এ crash নয়, পরিষ্কার বার্তা।
# =============================================================================

FF_WORLD_FILE = DATA / "world-model.json"
FF_PROJECTS_FILE = DATA / "projects.json"
FF_GROWTH_FILE = DATA / "growth-diary.json"
FF_RESEARCH_QUEUE_FILE = DATA / "research-queue.json"
FF_RESEARCH_NOTES_FILE = DATA / "research-notes.md"
FF_GUI_STEPS_FILE = DATA / "gui-steps.json"
FF_SANDBOX_DIR = DATA / "coding-sandbox"
FF_DOCS_DIR = DATA / "documents"

_ff_pending = {"action": None, "data": None}   # F3 confirmation gate (_n8 ধাঁচ)
_ff_gui_steps_mem = []


def _ff_ensure_dirs():
    for d in (FF_SANDBOX_DIR, FF_DOCS_DIR):
        try:
            d.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
    _bridge_dirs()


def _ff_today():
    return str(date.today())


def _ff_stamp():
    return datetime.now().isoformat(timespec="seconds")


def _ff_num(x):
    try:
        return _bn_num(x)
    except Exception:
        return str(x)


def _ff_norm(s):
    try:
        return _norm_num_text(s)
    except Exception:
        return str(s or "")


# ---------------------------------------------------------- F1: World Model
def _ff_world_load():
    wm = load_json(FF_WORLD_FILE, {})
    if not isinstance(wm, dict):
        wm = {}
    wm.setdefault("habits", {})
    wm.setdefault("people", {})
    wm.setdefault("goals", [])
    wm.setdefault("preferences", {})
    wm.setdefault("updated", "")
    return wm


def _ff_world_save(wm):
    try:
        wm["updated"] = _ff_stamp()
        save_json(FF_WORLD_FILE, wm)
    except Exception:
        pass


def world_model_update(key_path, value):
    """key-path ধরে world model আপডেট করে। যেমন:
    world_model_update('goals', 'সরকারি চাকরি পাওয়া'),
    world_model_update('people.রহিম.relation', 'বন্ধু'),
    world_model_update('habits.study_time', 'রাত ৯টা')।
    মাঝের নোড list হলে append, শেষ নোড list হলে append, নইলে set।"""
    wm = _ff_world_load()
    parts = [p.strip() for p in str(key_path or "").split(".") if p.strip()]
    if not parts:
        return wm
    node = wm
    for p in parts[:-1]:
        nxt = node.get(p) if isinstance(node, dict) else None
        if not isinstance(nxt, (dict, list)):
            nxt = {}
            node[p] = nxt
        node = nxt
    last = parts[-1]
    if isinstance(node, list):
        if value not in node:
            node.append(value)
    elif isinstance(node, dict):
        cur = node.get(last)
        if isinstance(cur, list):
            if value not in cur:
                cur.append(value)
        else:
            node[last] = value
    _ff_world_save(wm)
    return wm


def world_model_text():
    """প্রসঙ্গে ব্যবহারের মতো ছোট সারসংক্ষেপ।"""
    wm = _ff_world_load()
    goals = [g for g in wm.get("goals", []) if g]
    people = wm.get("people", {}) or {}
    habits = wm.get("habits", {}) or {}
    prefs = wm.get("preferences", {}) or {}
    if not goals and not people and not habits and not prefs:
        return ("আমার world model এখনো প্রায় খালি — তোমার লক্ষ্য, মানুষজন, "
                "অভ্যাস সম্পর্কে কথা হলেই আমি এখানে সাজিয়ে রাখব। "
                "যেমন বলতে পারো: 'লক্ষ্য যোগ করো: সরকারি চাকরি পাওয়া'।")
    lines = ["🌍 তোমার সম্পর্কে আমার world model:"]
    if goals:
        lines.append("লক্ষ্য: " + "; ".join(str(g) for g in goals[-5:]))
    if people:
        who = []
        for name, info in list(people.items())[:8]:
            rel = info.get("relation", "") if isinstance(info, dict) else ""
            who.append(f"{name} ({rel})" if rel else str(name))
        lines.append("মানুষজন: " + ", ".join(who))
    if habits:
        lines.append("অভ্যাস: " + "; ".join(
            f"{k}: {v}" for k, v in list(habits.items())[:5]))
    if prefs:
        pl = []
        for k, v in prefs.items():
            pl.append(f"{k}: {', '.join(map(str, v)) if isinstance(v, list) else v}")
        lines.append("পছন্দ: " + "; ".join(pl[:5]))
    if wm.get("updated"):
        lines.append(f"(সর্বশেষ হালনাগাদ: {wm['updated']})")
    return "\n".join(lines)


def _ff_world_learn(text):
    """learn_from_text-এর ধাঁচে হালকা নিয়ম-ভিত্তিক হুক (নীরব — উত্তর নয়)।
    নাম/লক্ষ্য/অভ্যাস/পছন্দ ধরলে world model-এ জমা হয়।"""
    try:
        changed = False
        m = re.search(r"আমার লক্ষ্য(?:টা)?(?: হলো| হচ্ছে)?[:\- ]+(.+)", text)
        if m:
            g = m.group(1).strip().rstrip("।.")
            wm = _ff_world_load()
            if g and g not in wm["goals"]:
                wm["goals"].append(g)
                _ff_world_save(wm)
            changed = True
        m = re.search(r"আমার (বন্ধু|ভাই|বোন|বাবা|মা|শিক্ষক|বান্ধবী) ([^\s,।:]+)", text)
        if m:
            rel, name = m.group(1), m.group(2).strip()
            wm = _ff_world_load()
            ent = wm["people"].get(name) or {}
            if ent.get("relation") != rel:
                ent["relation"] = rel
                wm["people"][name] = ent
                _ff_world_save(wm)
            changed = True
        m = re.search(r"আমার অভ্যাস[:\- ]+(.+)", text)
        if m:
            h = m.group(1).strip().rstrip("।.")
            wm = _ff_world_load()
            key = "অভ্যাস-" + str(len(wm["habits"]) + 1)
            if h and h not in wm["habits"].values():
                wm["habits"][key] = h
                _ff_world_save(wm)
            changed = True
        m = re.search(r"আমি (.+?) পছন্দ করি", text)
        if m:
            like = m.group(1).strip()
            wm = _ff_world_load()
            likes = wm["preferences"].get("পছন্দ")
            if not isinstance(likes, list):
                likes = []
            if like and like not in likes:
                likes.append(like)
                wm["preferences"]["পছন্দ"] = likes[-20:]
                _ff_world_save(wm)
            changed = True
        return changed
    except Exception:
        return False


# ------------------------------------------------------- F2: Anticipatory
def _ff_deadline_hints():
    """DATA-তে deadline/routine জাতীয় ফাইল থাকলে আগাম ইঙ্গিত বের করে।
    Desktop v1.0-তে এ ধরনের কোনো ফাইল থাকে না — থাকলে এখানে ধরা পড়বে।"""
    hints = []
    try:
        files = list(DATA.glob("*deadline*.json")) + list(DATA.glob("*routine*.json"))
    except Exception:
        files = []
    today = date.today()
    for f in files[:4]:
        try:
            data = load_json(f, None)
            items = data if isinstance(data, list) else (
                data.get("items", []) if isinstance(data, dict) else [])
            for it in items[:20]:
                if not isinstance(it, dict):
                    continue
                dstr = str(it.get("date") or it.get("deadline") or "")[:10]
                try:
                    d = date.fromisoformat(dstr)
                except Exception:
                    continue
                delta = (d - today).days
                title = str(it.get("title") or it.get("text") or "একটা কাজ")[:60]
                if delta == 1:
                    hints.append(f"কাল '{title}'-এর ডেডলাইন — আজই এগিয়ে রাখা ভালো।")
                elif delta == 0:
                    hints.append(f"আজই '{title}'-এর ডেডলাইন — সবার আগে এটা দেখো।")
                elif 2 <= delta <= 3:
                    hints.append(f"{_ff_num(delta)} দিন পর '{title}'-এর ডেডলাইন আসছে।")
        except Exception:
            continue
    # চলমান মক টেস্টের সময়সীমা
    try:
        exam = load_json(_EXAM_SESSION_FILE, None)
        if isinstance(exam, dict) and exam.get("deadline_ts"):
            if time.time() > float(exam["deadline_ts"]):
                hints.append("আগের মক টেস্টের সময় শেষ হয়ে গেছে — ফলটা দেখে নিলে ভালো হয়।")
    except Exception:
        pass
    return hints


def anticipatory_text():
    """আজকের প্রস্তুতির ২–৩ লাইন আগাম সাজেশন; তথ্য না থাকলে সৎ বার্তা।"""
    lines = []
    prog = load_json(_STUDY_PROGRESS_FILE, {})
    if not isinstance(prog, dict):
        prog = {}
    for h in _ff_deadline_hints():
        lines.append("• " + h)
    weak_all, last_topics, total_sessions = [], [], 0
    stale_subjects = []
    for subj, ent in prog.items():
        if not isinstance(ent, dict):
            continue
        total_sessions += int(ent.get("sessions", 0) or 0)
        for w in (ent.get("weak") or []):
            weak_all.append((subj, w))
        if ent.get("last_topic"):
            last_topics.append((subj, ent["last_topic"]))
        ld = str(ent.get("last_date") or "")
        if ld and ld != _ff_today():
            stale_subjects.append(subj)
    if weak_all:
        subj, w = weak_all[-1]
        lines.append(f"• দুর্বল জায়গা '{w}' ({subj}) — আজ একটু সময় এটার রিভিশনে দিলে পরীক্ষায় কাজে লাগবে।")
    if stale_subjects and last_topics:
        subj, topic = last_topics[-1]
        lines.append(f"• {subj}-এর '{topic}' যেখানে থেমেছিলে, আজ সেখান থেকেই আবার শুরু করলে ধারাবাহিকতা থাকবে।")
    elif last_topics:
        subj, topic = last_topics[-1]
        lines.append(f"• {subj}-এ শেষ পড়েছিলে '{topic}' — আজ তার পরের ধাপটা নিলে ভালো হয়।")
    if not lines:
        return ("আজকের প্রস্তুতির আগাম সাজেশন দেওয়ার মতো তথ্য এখনো জমেনি — "
                "পড়ার রেকর্ড, ডেডলাইন বা রুটিন কিছুই পাইনি। একটা পড়ার সেশন "
                "শুরু করলেই ('শেখাও' বললেই) কাল থেকে আমি নিজে থেকে সাজেশন দিতে পারব।")
    return "আজকের প্রস্তুতি (আগাম সাজেশন):\n" + "\n".join(lines[:3])


# ------------------------------------------------- F8: Prediction (গতি-ভিত্তিক)
def prediction_text():
    """study progress-এর গতি থেকে সংখ্যায় অনুমান। তথ্য অপর্যাপ্ত হলে
    সংখ্যা বানানো হয় না — সেটাই স্পষ্ট বলা হয়।"""
    prog = load_json(_STUDY_PROGRESS_FILE, {})
    if not isinstance(prog, dict) or not prog:
        return ("পূর্বাভাস দেওয়ার মতো পড়ার রেকর্ড এখনো নেই — আগে কয়েকটা "
                "পড়ার সেশন হলেই আমি গতি হিসাব করতে পারব। সংখ্যা বানিয়ে বলব না।")
    total_steps = sum(int(e.get("total_steps", 0) or 0)
                      for e in prog.values() if isinstance(e, dict))
    total_sessions = sum(int(e.get("sessions", 0) or 0)
                         for e in prog.values() if isinstance(e, dict))
    try:
        first = get_memory().get("first_day", "")
        elapsed = (date.today() - date.fromisoformat(str(first)[:10])).days
    except Exception:
        elapsed = 0
    if total_steps < 3 or elapsed < 1:
        return (f"পূর্বাভাসের জন্য তথ্য এখনো কম (মোট ধাপ {_ff_num(total_steps)}টা, "
                f"সেশন {_ff_num(total_sessions)}টা, হিসাবের সময়কাল {_ff_num(elapsed)} দিন)। "
                "আর কয়েকদিন নিয়মিত পড়লেই গতি ধরে সংখ্যায় বলতে পারব — "
                "এখন অনুমান বানিয়ে বলব না।")
    rate = total_steps / elapsed  # ধাপ/দিন
    remaining, known = 0, []
    try:
        lessons = OFFLINE_LESSONS
    except Exception:
        lessons = {}
    for subj, ent in prog.items():
        if subj in lessons and isinstance(ent, dict):
            total = len(lessons[subj])
            covered = min(int(ent.get("total_steps", 0) or 0), total)
            if total - covered > 0:
                remaining += total - covered
                known.append(subj)
    if not known:
        return ("যেসব বিষয়ে তুমি পড়ছ, সেগুলোর মোট পাঠের সংখ্যা আমার জানা "
                "পাঠক্রমে নেই — তাই 'বাকি কত' হিসাব করা যাচ্ছে না। গতি শুধু "
                f"এটুকু বলতে পারি: দিনে গড়ে প্রায় {_ff_num(round(rate, 1))} ধাপ এগোচ্ছ।")
    import math
    days = math.ceil(remaining / rate) if rate > 0 else 0
    return (f"এই গতিতে (দিনে গড়ে প্রায় {_ff_num(round(rate, 1))} ধাপ) জানা পাঠক্রমের "
            f"বাকি {_ff_num(remaining)}টা ধাপ ({', '.join(known)}) শেষ হতে আনুমানিক "
            f"{_ff_num(days)} দিন লাগতে পারে। এটা শুধু অফলাইন পাঠক্রমের হিসাব — "
            "আসল সিলেবাস এর চেয়ে বড় হলে সময়ও বেশি লাগবে।")



# ------------------------------------------------------------ F4: Projects
def _ff_projects_load():
    items = load_json(FF_PROJECTS_FILE, [])
    return items if isinstance(items, list) else []


def _ff_projects_save(items):
    try:
        save_json(FF_PROJECTS_FILE, items[-30:])
    except Exception:
        pass


def _ff_project_current(items):
    for p in reversed(items):
        if isinstance(p, dict) and p.get("title"):
            return p
    return None


def _ff_projects_text():
    items = _ff_projects_load()
    if not items:
        return "এখনো কোনো প্রকল্প নেই। শুরু করতে বলো: 'প্রকল্প শুরু করো: <নাম>'।"
    lines = ["📁 প্রকল্পের অবস্থা:"]
    for p in items[-5:]:
        steps = p.get("steps", []) or []
        done = sum(1 for s in steps if isinstance(s, dict) and s.get("done"))
        lines.append(f"• {p.get('title')}: ধাপ {_ff_num(done)}/{_ff_num(len(steps))} শেষ "
                     f"(শুরু: {p.get('created', '—')})")
        for i, s in enumerate(steps[:8], 1):
            if isinstance(s, dict):
                mark = "✅" if s.get("done") else "⬜"
                lines.append(f"   {_ff_num(i)}. {mark} {s.get('text', '')}")
    return "\n".join(lines)


def _ff_projects_public():
    out = []
    for p in _ff_projects_load()[-10:]:
        if not isinstance(p, dict):
            continue
        steps = [{"text": str(s.get("text", "")), "done": bool(s.get("done"))}
                 for s in (p.get("steps", []) or []) if isinstance(s, dict)]
        out.append({"title": str(p.get("title", "")), "created": str(p.get("created", "")),
                    "steps": steps,
                    "done": sum(1 for s in steps if s["done"]), "total": len(steps)})
    return out


# --------------------------------------------- F6: Growth diary + metrics
def _ff_growth_counts():
    try:
        mem = get_memory()
    except Exception:
        mem = {}
    rules_n = 0
    try:
        rules_n = len([ln for ln in rules_text().splitlines() if ln.strip()])
    except Exception:
        pass
    know_n = 0
    try:
        know_n = len(load_json(KNOW_FILE, {}))
    except Exception:
        pass
    return {"facts": len(mem.get("facts", []) or []),
            "likes": len(mem.get("likes", []) or []),
            "learned_notes": len(mem.get("learned_notes", []) or []),
            "rules": rules_n, "knowledge": know_n,
            "interactions": int(mem.get("interaction_count", 0) or 0)}


def _ff_growth_record():
    """আজকের তারিখ ধরে growth diary-তে এন্ট্রি আপডেট করে (একই দিনে আপডেট)।"""
    counts = _ff_growth_counts()
    diary = load_json(FF_GROWTH_FILE, [])
    if not isinstance(diary, list):
        diary = []
    today = _ff_today()
    entry = {"date": today, **counts}
    for i, e in enumerate(diary):
        if isinstance(e, dict) and e.get("date") == today:
            diary[i] = entry
            break
    else:
        diary.append(entry)
    try:
        save_json(FF_GROWTH_FILE, diary[-120:])
    except Exception:
        pass
    return entry, diary


def metrics_text():
    entry, diary = _ff_growth_record()
    first = diary[0] if diary else entry
    lines = ["📈 আমার বৃদ্ধির হিসাব:"]
    lines.append(f"• মনে থাকা তথ্য: {_ff_num(entry['facts'])}টা "
                 f"(শুরুতে {_ff_num(first.get('facts', 0))}টা)")
    lines.append(f"• শেখা নোট: {_ff_num(entry['learned_notes'])}টা, "
                 f"শেখা উত্তর: {_ff_num(entry['knowledge'])}টা")
    lines.append(f"• তোমার বসানো নিয়ম: {_ff_num(entry['rules'])}টা")
    lines.append(f"• মোট কথা হয়েছে: {_ff_num(entry['interactions'])} বার")
    lines.append(f"• ডায়েরিতে রেকর্ড আছে {_ff_num(len(diary))} দিনের "
                 f"({first.get('date', '—')} থেকে আজ পর্যন্ত)")
    return "\n".join(lines)


# ------------------------------------------ F7: Nightly research (daemon)
def _ff_research_load():
    q = load_json(FF_RESEARCH_QUEUE_FILE, [])
    return q if isinstance(q, list) else []


def _ff_research_worker():
    """প্রতি ঘণ্টায় একবার দেখে: রাত ১–৪টার মধ্যে queue-তে বিষয় থাকলে
    web_search দিয়ে সারসংক্ষেপ research-notes.md-তে জমা করে।"""
    while True:
        try:
            time.sleep(3600)
            hour = datetime.now().hour
            if not (1 <= hour < 4):
                continue
            q = _ff_research_load()
            pending = [it for it in q if isinstance(it, dict)
                       and it.get("status") in (None, "অপেক্ষায়")]
            if not pending:
                continue
            item = pending[0]
            topic = str(item.get("topic") or "")[:120]
            if not topic:
                item["status"] = "বাদ"
                save_json(FF_RESEARCH_QUEUE_FILE, q)
                continue
            found = web_search(topic, 5)
            summary = None
            try:
                summary = _gemini_or_none(
                    f"বিষয়: {topic}\nনিচের ওয়েব ফলাফলের ভিত্তিতে ৫-৬ লাইনে "
                    f"সহজ বাংলায় সারসংক্ষেপ লেখো:\n{found}")
            except Exception:
                summary = None
            body = summary or found
            try:
                with FF_RESEARCH_NOTES_FILE.open("a", encoding="utf-8") as f:
                    f.write(f"\n## {topic} — {_ff_stamp()}\n{body}\n")
            except Exception:
                pass
            item["status"] = "শেষ"
            item["done"] = _ff_today()
            try:
                save_json(FF_RESEARCH_QUEUE_FILE, q)
            except Exception:
                pass
            try:
                log_change(f"F7 রাতের গবেষণা শেষ: {topic[:60]}")
            except Exception:
                pass
        except Exception:
            try:
                time.sleep(600)
            except Exception:
                pass


_ff_research_started = {"on": False}
try:
    if not _ff_research_started["on"]:
        threading.Thread(target=_ff_research_worker, daemon=True).start()
        _ff_research_started["on"] = True
except Exception:
    pass



# ------------------------------------------- F3: GUI computer-use (Windows)
def _ff_is_win():
    return sys.platform.startswith("win")


def _ff_gui_log(step):
    rec = {"ts": _ff_stamp(), "step": str(step)[:200]}
    _ff_gui_steps_mem.append(rec)
    del _ff_gui_steps_mem[:-50]
    try:
        old = load_json(FF_GUI_STEPS_FILE, [])
        if not isinstance(old, list):
            old = []
        old.append(rec)
        save_json(FF_GUI_STEPS_FILE, old[-50:])
    except Exception:
        pass


def _ff_gui_steps_public():
    if _ff_gui_steps_mem:
        return list(_ff_gui_steps_mem[-10:])
    old = load_json(FF_GUI_STEPS_FILE, [])
    return old[-10:] if isinstance(old, list) else []


def _ff_gui_guard(action_label):
    """(চালানো যাবে কিনা, না গেলে বার্তা) — config + OS দুই গার্ড।"""
    try:
        enabled = bool(get_config().get("computer_use_enabled", False))
    except Exception:
        enabled = False
    if not enabled:
        return False, ("কম্পিউটার-নিয়ন্ত্রণ (F3) এখন বন্ধ আছে — config-তে "
                       "computer_use_enabled চালু না করলে আমি কোনো ক্লিক/টাইপ "
                       "করব না। এটা তোমার নিরাপত্তার জন্যই রাখা।")
    if not _ff_is_win():
        return False, ("এই কাজটা শুধু Windows-এ চলবে — GUI নিয়ন্ত্রণ "
                       "Windows-এর user32 দিয়ে করা হয়; এই মেশিনে সেটা নেই।")
    return True, ""


def gui_mouse_move(x, y):
    ok, msg = _ff_gui_guard("মাউস সরানো")
    if not ok:
        _ff_gui_log(f"মাউস সরানো আটকানো হলো: {msg[:80]}")
        return False, msg
    try:
        import ctypes
        ctypes.windll.user32.SetCursorPos(int(x), int(y))
        _ff_gui_log(f"মাউস সরানো হলো: ({x}, {y})")
        return True, f"মাউসটা ({_ff_num(x)}, {_ff_num(y)}) অবস্থানে সরিয়ে দিলাম।"
    except Exception as e:
        return False, f"মাউস সরাতে সমস্যা হলো: {e}"


def gui_click(x=None, y=None):
    ok, msg = _ff_gui_guard("ক্লিক")
    if not ok:
        _ff_gui_log(f"ক্লিক আটকানো হলো: {msg[:80]}")
        return False, msg
    try:
        import ctypes
        u = ctypes.windll.user32
        if x is not None and y is not None:
            u.SetCursorPos(int(x), int(y))
            time.sleep(0.15)
        u.mouse_event(0x0002, 0, 0, 0, 0)   # LEFTDOWN
        time.sleep(0.05)
        u.mouse_event(0x0004, 0, 0, 0, 0)   # LEFTUP
        where = f" ({x}, {y})-তে" if x is not None else ""
        _ff_gui_log(f"ক্লিক করা হলো{where}")
        return True, f"ক্লিক করে দিলাম{where}।"
    except Exception as e:
        return False, f"ক্লিক করতে সমস্যা হলো: {e}"


def gui_type_text(s):
    ok, msg = _ff_gui_guard("টাইপ")
    if not ok:
        _ff_gui_log(f"টাইপ আটকানো হলো: {msg[:80]}")
        return False, msg
    try:
        import ctypes

        class _KEYBDINPUT(ctypes.Structure):
            _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort),
                        ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong),
                        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

        class _MOUSEINPUT(ctypes.Structure):
            _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                        ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                        ("time", ctypes.c_ulong),
                        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

        class _U(ctypes.Union):
            _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT),
                        ("pad", ctypes.c_byte * 32)]

        class _INPUT(ctypes.Structure):
            _fields_ = [("type", ctypes.c_ulong), ("u", _U)]

        KEYEVENTF_UNICODE, KEYEVENTF_KEYUP = 0x0004, 0x0002
        send = ctypes.windll.user32.SendInput
        text = str(s)[:500]
        for ch in text:
            for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
                inp = _INPUT()
                inp.type = 1  # INPUT_KEYBOARD
                inp.u.ki.wVk = 0
                inp.u.ki.wScan = ord(ch)
                inp.u.ki.dwFlags = flags
                send(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))
            time.sleep(0.01)
        _ff_gui_log(f"টাইপ করা হলো: {text[:60]}")
        return True, f"টাইপ করে দিলাম: '{text[:60]}'"
    except Exception as e:
        return False, f"টাইপ করতে সমস্যা হলো: {e}"


def gui_screenshot(path=None):
    ok, msg = _ff_gui_guard("স্ক্রিনশট")
    if not ok:
        _ff_gui_log(f"স্ক্রিনশট আটকানো হলো: {msg[:80]}")
        return False, msg
    try:
        import ctypes
        import struct
        u, g = ctypes.windll.user32, ctypes.windll.gdi32
        w, h = u.GetSystemMetrics(0), u.GetSystemMetrics(1)
        hdc = u.GetDC(0)
        mem = g.CreateCompatibleDC(hdc)
        bmp = g.CreateCompatibleBitmap(hdc, w, h)
        g.SelectObject(mem, bmp)
        g.BitBlt(mem, 0, 0, w, h, hdc, 0, 0, 0x00CC0020)

        class _BIH(ctypes.Structure):
            _fields_ = [("biSize", ctypes.c_ulong), ("biWidth", ctypes.c_long),
                        ("biHeight", ctypes.c_long), ("biPlanes", ctypes.c_ushort),
                        ("biBitCount", ctypes.c_ushort),
                        ("biCompression", ctypes.c_ulong),
                        ("biSizeImage", ctypes.c_ulong),
                        ("biXPels", ctypes.c_long), ("biYPels", ctypes.c_long),
                        ("biClrUsed", ctypes.c_ulong), ("biClrImp", ctypes.c_ulong)]

        bih = _BIH()
        bih.biSize, bih.biWidth, bih.biHeight = 40, w, -h
        bih.biPlanes, bih.biBitCount = 1, 24
        row = ((w * 3 + 3) // 4) * 4
        buf = ctypes.create_string_buffer(row * h)
        g.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bih), 0)
        out = Path(path) if path else (DATA / f"screenshot-{datetime.now().strftime('%Y%m%d-%H%M%S')}.bmp")
        img_size = row * h
        header = b"BM" + struct.pack("<IHHI", 54 + img_size, 0, 0, 54)
        info = struct.pack("<IiiHHIIiiII", 40, w, -h, 1, 24, 0, img_size, 2835, 2835, 0, 0)
        out.write_bytes(header + info + buf.raw)
        try:
            g.DeleteObject(bmp)
            g.DeleteDC(mem)
            u.ReleaseDC(0, hdc)
        except Exception:
            pass
        _ff_gui_log(f"স্ক্রিনশট সেভ হলো: {out.name}")
        return True, f"স্ক্রিনশট নিয়ে সেভ করলাম: {out}"
    except Exception as e:
        return False, f"স্ক্রিনশট নিতে সমস্যা হলো: {e}"


def _ff_gui_run_pending():
    action, data = _ff_pending.get("action"), _ff_pending.get("data") or {}
    _ff_pending["action"], _ff_pending["data"] = None, None
    if action == "click":
        _, msg = gui_click(data.get("x"), data.get("y"))
        return msg
    if action == "move":
        _, msg = gui_mouse_move(data.get("x"), data.get("y"))
        return msg
    if action == "type":
        _, msg = gui_type_text(data.get("text", ""))
        return msg
    if action == "screenshot":
        _, msg = gui_screenshot()
        return msg
    return "কাজটা করা হলো।"


def _ff_gui_gate(text, low):
    stripped = (text or "").strip()
    if ("বাতিল" in text or stripped in ("না", "না থাক", "থাক", "no")
            or "cancel" in low):
        _ff_pending["action"], _ff_pending["data"] = None, None
        return "বাতিল করে দিলাম — কম্পিউটারে কিছু করা হয়নি।"
    if any(w in text for w in ("হ্যাঁ", "করো")) or any(
            w in low for w in ("yes", "confirm", "ok")):
        return _ff_gui_run_pending()
    _ff_pending["action"], _ff_pending["data"] = None, None
    return "বাতিল করে দিলাম — কম্পিউটারে কিছু করা হয়নি।"


def _ff_gui_ask(action, data, describe):
    """confirmation ছাড়া কোনো GUI কাজ হয় না: আগে জিজ্ঞেস, 'হ্যাঁ' এলে কাজ।"""
    ok, msg = _ff_gui_guard(describe)
    if not ok:
        _ff_gui_log(f"{describe} — অনুরোধ এলো কিন্তু গার্ডে আটকালো")
        return msg
    _ff_pending["action"], _ff_pending["data"] = action, data
    return (f"কম্পিউটারে এই কাজটা করতে যাচ্ছি: {describe}। "
            "নিশ্চিত করতে বলো 'হ্যাঁ' — অন্য কিছু বললেই বাতিল হয়ে যাবে।")


# ------------------------------------- N10: Coding agent (sandbox only)
def _ff_code_extract(raw):
    if not raw:
        return ""
    m = re.search(r"```(?:python|py)?\s*\n(.*?)```", raw, re.S)
    code = (m.group(1) if m else raw).strip()
    return code if ("def " in code or "print(" in code or "import " in code
                    or "=" in code) else ""


def _ff_code_compile(path):
    try:
        r = subprocess.run([sys.executable, "-m", "py_compile", str(path)],
                           capture_output=True, text=True, timeout=20)
        return r.returncode == 0, (r.stderr or "")[-400:]
    except Exception as e:
        return False, str(e)[:400]


def _ff_coding_do(brief):
    _ff_ensure_dirs()
    brief = (brief or "").strip()[:300]
    if not brief:
        return "কী বানাব সেটা বলো — যেমন: 'কোড বানাও: দুই সংখ্যার যোগ করার প্রোগ্রাম'।"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = FF_SANDBOX_DIR / f"code-{stamp}.py"
    code, used_gemini = "", False
    try:
        raw = _gemini_or_none(
            "শুধু Python কোড লিখো (stdlib only, অন্য কোনো ব্যাখ্যা নয়)। "
            f"কাজ: {brief}\nকোডটা ছোট, চালানো যায় এমন ও নিরাপদ হবে; "
            "শেষে if __name__ == '__main__': দিয়ে main() ডাকো।")
        code = _ff_code_extract(raw)
        used_gemini = bool(code)
    except Exception:
        code = ""
    if not code:
        safe_brief = brief.replace('"""', "")
        code = ('# -*- coding: utf-8 -*-\n'
                f'"""Sokhi coding agent (টেমপ্লেট) — কাজ: {safe_brief}"""\n\n\n'
                "def main():\n"
                f'    print("কাজ: {safe_brief}")\n'
                "    # TODO: মূল লজিক এখানে বসাতে হবে\n\n\n"
                "if __name__ == '__main__':\n"
                "    main()\n")
    try:
        path.write_text(code, encoding="utf-8")
    except Exception as e:
        return f"কোড ফাইল লিখতে পারলাম না: {e}"
    ok, err = _ff_code_compile(path)
    fixed_note = ""
    if not ok and used_gemini:
        try:
            raw2 = _gemini_or_none(
                "নিচের Python কোডে compile error আছে। শুধু ঠিক করা সম্পূর্ণ "
                f"কোডটাই ফেরত দাও, ব্যাখ্যা নয়।\nError: {err}\nকোড:\n{code}")
            code2 = _ff_code_extract(raw2)
            if code2:
                path.write_text(code2, encoding="utf-8")
                ok, err = _ff_code_compile(path)
                fixed_note = " একবার self-fix চেষ্টা করেছি।"
        except Exception:
            pass
    _ff_gui_log(f"কোড বানানো হলো (sandbox): {path.name} — compile {'ok' if ok else 'fail'}")
    if ok:
        src = "Gemini দিয়ে" if used_gemini else "টেমপ্লেট দিয়ে (Gemini key নেই/সাড়া দেয়নি)"
        return (f"কোড বানিয়ে sandbox-এ রাখলাম: data/coding-sandbox/{path.name} "
                f"({src})। py_compile যাচাই: ✅ পাস।{fixed_note} "
                "কোডটা নিজে থেকে চালাইনি — তুমি দেখে চালাতে পারো।")
    return (f"কোড ফাইল বানালাম (data/coding-sandbox/{path.name}) কিন্তু compile "
            f"যাচাইয়ে পাস করেনি:{fixed_note}\nশেষ error: {err[-200:]}")


# ------------------------------------------ N11: Documents / Research
def _ff_doc_slug(topic):
    # শুধু ফাইল-নামে নিষিদ্ধ অক্ষর ছাঁটা হয় — বাংলা স্বরচিহ্নসহ বাকি সব থাকে
    s = re.sub(r'[\\/:*?"<>|#\n\r\t]+', "", str(topic or "")).strip()
    s = re.sub(r"\s+", "-", s)[:40].strip("-")
    return s or "report"


def _ff_doc_make(topic):
    _ff_ensure_dirs()
    topic = (topic or "").strip()[:120]
    if not topic:
        return "কোন বিষয়ে রিপোর্ট বানাব? যেমন: 'রিপোর্ট বানাও: ধান চাষে আধুনিক পদ্ধতি'।"
    found = web_search(topic, 5)
    summary = None
    try:
        summary = _gemini_or_none(
            f"বিষয়: {topic}\nনিচের ওয়েব অনুসন্ধানের ফলের ভিত্তিতে সহজ "
            f"বাংলায় একটি ছোট রিপোর্ট লেখো (ভূমিকা, মূল তথ্য, উপসংহার):\n{found}")
    except Exception:
        summary = None
    body = summary or ("(Gemini সারসংক্ষেপ পাওয়া যায়নি — নিচে ওয়েব সার্চের "
                       "কাঁচা ফল রাখা হলো।)\n\n" + found)
    fname = f"{_ff_doc_slug(topic)}-{_ff_today()}.md"
    path = FF_DOCS_DIR / fname
    if path.exists():
        path = FF_DOCS_DIR / f"{_ff_doc_slug(topic)}-{datetime.now().strftime('%H%M%S')}.md"
    content = (f"# রিপোর্ট: {topic}\n\nতারিখ: {_ff_today()}\n"
               f"তৈরি: Sokhi Desktop v1.1.0 (N11)\n\n{body}\n")
    try:
        path.write_text(content, encoding="utf-8")
    except Exception as e:
        return f"রিপোর্ট ফাইল লিখতে পারলাম না: {e}"
    return (f"রিপোর্ট বানিয়ে রাখলাম: data/documents/{path.name} "
            f"({_ff_num(len(content))} অক্ষর)। খুঁজতে চাইলে বলো: 'নথি খোঁজো: <শব্দ>'।")


def _ff_doc_search(word):
    _ff_ensure_dirs()
    word = (word or "").strip()
    if not word:
        return "কোন শব্দ খুঁজব? যেমন: 'নথি খোঁজো: ধান'।"
    wl = word.lower()
    hits, scanned = [], 0
    seen = set()
    for base in (FF_DOCS_DIR, DATA):
        try:
            files = list(base.rglob("*.md")) + list(base.rglob("*.txt"))
        except Exception:
            files = []
        for f in files[:300]:
            try:
                if f in seen or f.stat().st_size > 300_000:
                    continue
                seen.add(f)
                scanned += 1
                for i, ln in enumerate(
                        f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                    if wl in ln.lower():
                        hits.append(f"• {f.name} (লাইন {_ff_num(i)}): {ln.strip()[:110]}")
                        if len(hits) >= 10:
                            break
            except Exception:
                continue
            if len(hits) >= 10:
                break
        if len(hits) >= 10:
            break
    if not hits:
        return (f"'{word}' শব্দটা কোনো নথিতে পেলাম না "
                f"({_ff_num(scanned)}টা .md/.txt ফাইল খুঁজেছি)।")
    return (f"'{word}' — {_ff_num(len(hits))}টা মিল পেলাম "
            f"({_ff_num(scanned)}টা ফাইলে খুঁজে):\n" + "\n".join(hits))


# ------------------------------------------ N14/F5: Bridge (Desktop side)
def bridge_sync_text():
    _bridge_dirs()
    try:
        enabled = bool(get_config().get("bridge_enabled", False))
    except Exception:
        enabled = False
    out_files = sorted(BRIDGE_OUTBOX.glob("*.json"))
    in_files = sorted(BRIDGE_INBOX.glob("*.json"))
    legacy = load_json(BRIDGE_QUEUE_FILE, [])
    legacy_n = len(legacy) if isinstance(legacy, list) else 0
    lines = ["🌉 Bridge-এর অবস্থা (Desktop দিক):"]
    lines.append(f"• bridge_enabled config: {'চালু' if enabled else 'বন্ধ'}")
    lines.append(f"• outbox-এ অপেক্ষমাণ ফাইল: {_ff_num(len(out_files))}টা "
                 f"(পুরনো queue: {_ff_num(legacy_n)}টা)")
    lines.append(f"• inbox-এ আসা ফাইল: {_ff_num(len(in_files))}টা")
    if in_files:
        last = load_json(in_files[-1], {})
        if isinstance(last, dict) and last:
            lines.append(f"• সর্বশেষ inbox বার্তা [{last.get('kind', '?')}]: "
                         f"{str(last.get('text', ''))[:120]}")
        lines.append("সব পড়তে বলো: 'ব্রিজের বার্তা পড়ো'।")
    else:
        lines.append("• inbox এখনো খালি — Muse/WhatsApp-পক্ষের worker "
                     "এখানে ফাইল রাখলেই আমি পড়তে পারব।")
    return "\n".join(lines)


def _ff_bridge_read_inbox():
    _bridge_dirs()
    in_files = sorted(BRIDGE_INBOX.glob("*.json"))
    if not in_files:
        return ("inbox-এ এখনো কিছু আসেনি। Muse/WhatsApp-পক্ষের worker "
                "এখানে {kind, text, ts} ফরম্যাটে ফাইল রাখলেই আমি পড়তে পারব।")
    lines = [f"inbox-এর সর্বশেষ {_ff_num(min(3, len(in_files)))}টা বার্তা:"]
    for f in in_files[-3:]:
        d = load_json(f, {})
        if isinstance(d, dict):
            lines.append(f"• [{d.get('kind', '?')} · {d.get('ts', '—')}] "
                         f"{str(d.get('text', ''))[:180]}")
        else:
            lines.append(f"• {f.name}: (পড়া যায়নি)")
    return "\n".join(lines)



# ------------------------------------------------------------- routing
def fullforms_handle(text, low):
    """v1.1.0 full-forms কমান্ড রাউটার। মিললে reply string, না মিললে None।
    কোনো অবস্থাতেই exception ছোড়ে না।"""
    try:
        text = (text or "").strip()
        if not text:
            return None
        low = low or text.lower()
        _ff_ensure_dirs()

        # ০) F3 pending confirmation — _n8 ধাঁচে আগে নিষ্পত্তি
        if _ff_pending.get("action"):
            return _ff_gui_gate(text, low)

        # হালকা world-model হুক (নীরব)
        _ff_world_learn(text)

        # ---- F1: World Model
        if "বিশ্ব মডেল" in text or "world model" in low or "আমার সম্পর্কে কী জানো" in text:
            return world_model_text()
        m = re.search(r"লক্ষ্য যোগ করো[:\- ]+(.+)", text)
        if m:
            g = m.group(1).strip().rstrip("।.")
            if g:
                world_model_update("goals", g)
                return f"লক্ষ্যটা world model-এ যোগ করে দিলাম: {g}"
            return "লক্ষ্য হিসেবে কী যোগ করব, সেটা বলো।"

        # ---- F2: Anticipatory
        if ("আজকের প্রস্তুতি" in text or "আগাম সাজেশন" in text
                or "আজ কী পড়ব" in text or "আজকের সাজেশন" in text):
            return anticipatory_text()

        # ---- F8: Prediction
        if ("শেষ হতে কতদিন" in text or "কত দিনে শেষ" in text
                or "কতদিন লাগবে" in text or "পূর্বাভাস" in text):
            return prediction_text()

        # ---- F6: Growth
        if ("কতটা বেড়েছ" in text or "বৃদ্ধির হিসাব" in text
                or "তোমার অগ্রগতি" in text):
            return metrics_text()

        # ---- N14/F5: Bridge
        m = re.search(r"ব্রিজে পাঠাও[:\- ]+(.+)", text, re.S)
        if m:
            n = bridge_enqueue(m.group(1).strip())
            return (f"বার্তাটা bridge outbox-এ রেখে দিলাম (queue-তে মোট "
                    f"{_ff_num(n)}টা)। Muse-পক্ষের worker নিলেই কাজ হবে।")
        if "ব্রিজের বার্তা পড়ো" in text or "ব্রিজের বার্তা দেখাও" in text:
            return _ff_bridge_read_inbox()
        if "ব্রিজের অবস্থা" in text or "bridge status" in low or "ব্রিজ স্ট্যাটাস" in text:
            return bridge_sync_text()

        # ---- F4: Projects
        m = re.search(r"প্রকল্প শুরু করো[:\- ]+(.+)", text)
        if m:
            title = m.group(1).strip()[:80]
            items = _ff_projects_load()
            items.append({"title": title, "steps": [], "created": _ff_today()})
            _ff_projects_save(items)
            return (f"প্রকল্প শুরু হলো: {title}। ধাপ যোগ করতে বলো: "
                    "'প্রকল্পের ধাপ যোগ করো: <ধাপ>'।")
        m = re.search(r"প্রকল্পের ধাপ যোগ করো[:\- ]+(.+)", text)
        if m:
            step = m.group(1).strip()[:160]
            items = _ff_projects_load()
            cur = _ff_project_current(items)
            if not cur:
                return "আগে একটা প্রকল্প শুরু করো: 'প্রকল্প শুরু করো: <নাম>'।"
            cur.setdefault("steps", []).append({"text": step, "done": False})
            _ff_projects_save(items)
            return f"'{cur.get('title')}' প্রকল্পে ধাপ যোগ হলো: {step}"
        m = re.search(r"ধাপ শেষ(?: করো)?[:\- ]*([০-৯0-9]+)", text)
        if m:
            try:
                n = int(_ff_norm(m.group(1)))
            except Exception:
                n = 0
            items = _ff_projects_load()
            cur = _ff_project_current(items)
            if not cur:
                return "কোনো প্রকল্পই নেই — ধাপ শেষ করার কিছু নেই।"
            steps = cur.get("steps", []) or []
            if not (1 <= n <= len(steps)):
                return (f"'{cur.get('title')}'-এ মোট {_ff_num(len(steps))}টা ধাপ আছে — "
                        f"{_ff_num(n)} নম্বর ধাপ নেই।")
            steps[n - 1]["done"] = True
            _ff_projects_save(items)
            done = sum(1 for s in steps if s.get("done"))
            return (f"ধাপ {_ff_num(n)} শেষ বলে চিহ্নিত করলাম ('{cur.get('title')}')। "
                    f"অগ্রগতি: {_ff_num(done)}/{_ff_num(len(steps))} ধাপ শেষ।")
        if "প্রকল্পের অবস্থা" in text or "প্রকল্প দেখাও" in text:
            return _ff_projects_text()

        # ---- F7: Research queue
        m = re.search(r"গবেষণার বিষয়[:\- ]+(.+)", text)
        if m:
            topic = m.group(1).strip()[:120]
            q = _ff_research_load()
            q.append({"topic": topic, "added": _ff_today(), "status": "অপেক্ষায়"})
            try:
                save_json(FF_RESEARCH_QUEUE_FILE, q[-30:])
            except Exception:
                pass
            return (f"গবেষণার বিষয় queue-তে রাখলাম: {topic}। রাত ১–৪টার মধ্যে "
                    "আমি নিজে গবেষণা করে research-notes-এ সারসংক্ষেপ রেখে দেব।")
        if "গবেষণার তালিকা" in text or "গবেষণার অবস্থা" in text:
            q = _ff_research_load()
            if not q:
                return "গবেষণার queue এখন খালি। বিষয় দিতে বলো: 'গবেষণার বিষয়: <বিষয়>'।"
            lines = ["🔬 গবেষণার queue:"]
            for it in q[-8:]:
                if isinstance(it, dict):
                    lines.append(f"• {it.get('topic', '')} — {it.get('status', 'অপেক্ষায়')}")
            return "\n".join(lines)

        # ---- N10: Coding agent
        m = re.search(r"কোড বানাও[:\- ]+(.+)", text, re.S)
        if m:
            return _ff_coding_do(m.group(1))

        # ---- N11: Documents / Research
        m = re.search(r"রিপোর্ট বানাও[:\- ]+(.+)", text)
        if m:
            return _ff_doc_make(m.group(1))
        m = re.search(r"নথি খোঁজো[:\- ]+(.+)", text)
        if m:
            return _ff_doc_search(m.group(1))

        # ---- F3: GUI computer-use (সবসময় আগে confirmation)
        if "স্ক্রিনশট" in text and ("নাও" in text or "তোলো" in text or "নিয়ে" in text):
            return _ff_gui_ask("screenshot", {}, "স্ক্রিনশট নেওয়া")
        m = re.search(r"কম্পিউটারে টাইপ করো[:\- ]+(.+)", text, re.S)
        if m:
            return _ff_gui_ask("type", {"text": m.group(1).strip()[:200]},
                               f"টাইপ করা: '{m.group(1).strip()[:60]}'")
        m = re.search(r"মাউস (?:সরাও|নাড়াও|নাও)[:\- ]*([০-৯0-9]+)[ ,]+([০-৯0-9]+)", text)
        if m:
            x, y = int(_ff_norm(m.group(1))), int(_ff_norm(m.group(2)))
            return _ff_gui_ask("move", {"x": x, "y": y}, f"মাউস সরানো ({x}, {y})-তে")
        if ("ক্লিক করো" in text or "কম্পিউটারে ক্লিক" in text) and (
                "কম্পিউটার" in text or "মাউস" in text or "স্ক্রিন" in text
                or "এখানে" in text):
            m = re.search(r"([০-৯0-9]+)[ ,]+([০-৯0-9]+)", text)
            if m:
                x, y = int(_ff_norm(m.group(1))), int(_ff_norm(m.group(2)))
                return _ff_gui_ask("click", {"x": x, "y": y}, f"ক্লিক করা ({x}, {y})-তে")
            return _ff_gui_ask("click", {"x": None, "y": None},
                               "মাউসের বর্তমান জায়গায় ক্লিক করা")
        return None
    except Exception:
        return None


def fullforms_panels():
    """Visual Hub-এর জন্য JSON-serializable dict। কখনো exception ছোড়ে না।"""
    try:
        counts = _ff_growth_counts()
    except Exception:
        counts = {}
    try:
        bridge = {"enabled": bool(get_config().get("bridge_enabled", False)),
                  "outbox": _bridge_count(BRIDGE_OUTBOX),
                  "inbox": _bridge_count(BRIDGE_INBOX)}
        try:
            legacy = load_json(BRIDGE_QUEUE_FILE, [])
            bridge["legacy_queue"] = len(legacy) if isinstance(legacy, list) else 0
        except Exception:
            bridge["legacy_queue"] = 0
    except Exception:
        bridge = {"enabled": False, "outbox": 0, "inbox": 0, "legacy_queue": 0}
    try:
        projects = _ff_projects_public()
    except Exception:
        projects = []
    try:
        gui_steps = _ff_gui_steps_public()
    except Exception:
        gui_steps = []
    try:
        wm = _ff_world_load()
        growth = dict(counts)
        growth["goals"] = len(wm.get("goals", []) or [])
        growth["people"] = len(wm.get("people", {}) or {})
        diary = load_json(FF_GROWTH_FILE, [])
        growth["diary_days"] = len(diary) if isinstance(diary, list) else 0
    except Exception:
        growth = dict(counts)
    return {"projects": projects, "gui_steps": gui_steps,
            "bridge": bridge, "growth": growth}

def handle_message(text):
    text = (text or "").strip()
    if not text:
        return "ভাইয়া, কিছু তো বলো — আমি শুনছি।"
    with _lock:
        mem = get_memory()
        mem["interaction_count"] += 1
        mem["last_seen"] = now_str()
        low = text.lower()

        # count command pattern (first two words)
        key = " ".join(low.split()[:2])
        mem["command_counts"][key] = mem["command_counts"].get(key, 0) + 1

        learned = learn_from_text(text, mem)
        save_json(MEMORY_FILE, mem)
        if learned:
            auto_evolve(mem)
            return learned

        # --- confirmation gate for risky actions
        if _pending_confirm["action"]:
            if any(w in low for w in ("হ্যাঁ করো", "confirm", "হ্যাঁ", "yes", "করো")):
                act = _pending_confirm["action"]
                _pending_confirm["action"] = None
                if act == "shutdown" and sys.platform.startswith("win"):
                    subprocess.Popen(["shutdown", "/s", "/t", "60"])
                    return "ঠিক আছে ভাইয়া, PC ৬০ সেকেন্ডে বন্ধ হবে। থামাতে চাইলে বলো 'বাতিল করো'।"
                return "কাজটা করা হলো ভাইয়া।"
            _pending_confirm["action"] = None
            return "বাতিল করে দিলাম ভাইয়া।"

        # --- call-name: Bhaiya himself decides what Sokhi calls him
        mm_name = re.search(r"আমাকে\s+(.+?)\s+বলে\s+ডাক", text)
        if mm_name:
            nm = mm_name.group(1).strip()[:40]
            cfg = get_config(); cfg["call_name"] = nm; save_config(cfg)
            return f"ঠিক আছে! আজ থেকে আমি তোমাকে '{nm}' বলেই ডাকব।"
        if "নামে ডাকবে না" in text or "কোনো নামে ডাক" in text:
            cfg = get_config(); cfg["call_name"] = ""; save_config(cfg)
            return "ঠিক আছে, আজ থেকে আর কোনো নামে ডাকব না — শুধু তুমি বলেই কথা বলব।"

        # --- auto self-upgrade commands
        if "অটো আপগ্রেড" in text and ("বন্ধ" in text or "off" in low):
            cfg = get_config(); cfg["auto_self_upgrade"] = False; save_config(cfg)
            return "ঠিক আছে ভাইয়া, নিজে নিজে আপগ্রেড করা বন্ধ করে দিলাম। তুমি বললে আবার চালু করব।"
        if "অটো আপগ্রেড" in text and ("চালু" in text or "on" in low):
            cfg = get_config(); cfg["auto_self_upgrade"] = True; save_config(cfg)
            return "চালু করে দিলাম ভাইয়া — এখন থেকে প্রতিদিন আমি নিজে নিজেকে একটু করে ভালো করব।"
        if "আপগ্রেড" in text and ("চেক" in text or "করো" in text or "নিজেকে" in text):
            notes = self_upgrade()
            core = check_core_update()
            parts = ["ভাইয়া, নিজের আপগ্রেড চেক শেষ:"]
            parts += ["• " + n for n in notes] if notes else ["• নতুন শেখার/মেরামতের কিছু পাইনি — সব ঠিক আছে"]
            parts.append("• " + core)
            return "\n".join(parts)
        if "কতটা শিখেছ" in text or "শেখা উত্তর" in text:
            know = load_json(KNOW_FILE, {})
            return (f"ভাইয়া, এখন পর্যন্ত আমি {len(know)}টা প্রশ্নের উত্তর শিখে নিজের কাছে রেখেছি — "
                    "সেগুলো এখন ইন্টারনেট ছাড়াও বলতে পারি। প্রতিদিনের স্ব-আপগ্রেডে এই সংখ্যা বাড়ে।")

        # --- N13: rules by talk + skill drafts (v1.0)
        _r13 = rules_handle(text, low) or selfmod_handle(text, low)
        if _r13:
            return _r13

        # --- v1.0 early: agent fleet + away-mode (must precede news/weather
        # triggers — an away-task like 'খবর সাজানো' contains the word খবর)
        _ag = agents_handle(text, low) or away_handle(text, low)
        if _ag:
            return _ag

        # --- plugins Sokhi built herself
        ctx = {"time": datetime.now().strftime("%I:%M %p"),
               "date": str(date.today()), "name": mem["user_name"]}
        for p in load_plugins():
            try:
                out = p["handle"](text, ctx)
                if out:
                    return out
            except Exception:
                continue

        # --- new skill creation (Sokhi writes her own code)
        m = re.search(r"(?:নতুন স্কিল|new skill|skill banao|স্কিল বানাও)[:\- ]*(.+)", text, re.I)
        if m:
            parts = [p.strip() for p in re.split(r"\|", m.group(1))]
            kv = {}
            for p in parts:
                if "=" in p:
                    k, v = p.split("=", 1)
                    kv[k.strip().lower()] = v.strip()
            if kv.get("নাম") or kv.get("name"):
                _, msg = create_plugin(kv.get("নাম") or kv.get("name"),
                                       kv.get("যখন") or kv.get("trigger") or "হ্যালো",
                                       kv.get("উত্তর") or kv.get("reply") or "হ্যালো ভাইয়া!")
                return msg
            return ("এভাবে বলো ভাইয়া: নতুন স্কিল: নাম=ghorir_somoy | যখন=somoy koto | উত্তর=এখন {time}, ভাইয়া। "
                    "আমি নিজে Python কোড লিখে, টেস্ট করে স্কিলটা বানিয়ে নেব — একদম ফ্রি।")

        # --- N8 PC command pack (v1.0) — before the allow-list open handler
        _n8 = n8_handle(text, low)
        if _n8:
            return _n8

        # --- v1.1 full-forms: F1 world model, F2 আগাম-প্রস্তুতি, F3 GUI
        # computer-use, F4 প্রকল্প, F6 growth, F7 গবেষণা, F8 prediction,
        # N10 কোডিং, N11 নথি/রিপোর্ট, bridge (Desktop দিক)
        _ff = fullforms_handle(text, low)
        if _ff:
            return _ff
        # --- v1.5.0 daily-life pack (#212/#334/#324/#143/#740/#573/#450/#572)
        _dl = daily_handle(text, low, progress=(study_progress_text() if ("জয়" in text or "প্রেরণা" in text) else None))
        if _dl:
            return _dl

        # --- PC commands (allow-list)
        if any(w in low for w in ("খোলো", "খুলে দাও", "open ", "open")) and len(low) < 60:
            return pc_open(text)
        if "ইউটিউবে" in text or "youtube" in low and ("চালাও" in text or "play" in low or "বাজাও" in text):
            q = re.sub(r".*(?:চালাও|বাজাও|play)[:\- ]*", "", text, flags=re.I).strip() or text
            webbrowser.open("https://www.youtube.com/results?search_query=" + urllib.parse.quote(q))
            return f"YouTube-এ চালিয়ে দিলাম ভাইয়া: {q}"
        if any(w in text for w in ("বন্ধ করো", "shutdown")) and "pc" in low or "কম্পিউটার বন্ধ" in text:
            _pending_confirm["action"] = "shutdown"
            return "ভাইয়া, PC বন্ধ করা বড় কাজ — নিশ্চিত করতে আরেকবার বলো 'হ্যাঁ করো'। না চাইলে অন্য কিছু বললেই বাতিল।"
        if "বাতিল করো" in text and sys.platform.startswith("win"):
            subprocess.Popen(["shutdown", "/a"])
            return "বন্ধ করা বাতিল করলাম ভাইয়া।"

        # --- online, real-time (all free, no key)
        if "আবহাওয়া" in text or "weather" in low:
            city = get_config().get("city", "Dhaka")
            mm = re.search(r"(?:in|এর|র)\s+([A-Za-z\u0980-\u09FF]+)\s*(?:আবহাওয়া|weather)?$", text)
            return get_weather(city)
        if "কেমন আছ" in text:
            return ("আলহামদুলিল্লাহ ভাইয়া, আমি ভালো আছি! তুমি কেমন আছ? "
                    "পড়া কেমন চলছে? কিছু জানতে চাইলে বা কাজ থাকলে শুধু বলো।")
        if text.strip().rstrip("?？") in ("কি খবর", "কী খবর", "কী অবস্থা", "কি অবস্থা"):
            return "এইতো ভাইয়া, সব ভালো চলছে! তোমার কী খবর? আজ কী করতে চাও?"
        if "খবর" in text or "news" in low:
            return get_news()
        m = re.search(r"(?:সার্চ করো|search|খুঁজে দাও|খোঁজো)[:\- ]+(.+)", text, re.I)
        if m:
            return web_search(m.group(1).strip())
        if "সময়" in text or "time" in low or "তারিখ" in text or "date" in low:
            return f"ভাইয়া, এখন {now_str()}।"

        # --- knowledge about herself
        if "ভার্সন" in text or "version" in low:
            ver = get_version()
            return f"ভাইয়া, আমার বর্তমান ভার্সন v{ver['version']}। প্রতিদিন একবার করে আমি শেখা জিনিস নিয়ে নতুন দৈনিক ভার্সন বের করি — আজকেরটা {'হয়ে গেছে' if ver['last_daily_release'] == str(date.today()) else 'এখনো বাকি'}।"
        if ("প্যাটার্ন" in text or "বিশ্লেষণ" in text or "insight" in low) and "ভুল বিশ্লেষণ" not in text and "প্রশ্ন বিশ্লেষণ" not in text:
            return insights_text(mem)
        if "কী কী মনে" in text or "কি মনে রেখেছ" in text or "what do you remember" in low:
            facts = mem["facts"]
            try:
                bump_fact_weights(list(facts))
            except Exception:
                pass
            if not facts:
                return "ভাইয়া, এখনো তেমন কিছু মনে রাখিনি। 'মনে রেখো: ...' বলে বললেই আমি সারাজীবন মনে রাখব, তোমার PC-তেই থাকবে।"
            return "ভাইয়া, যা যা মনে রেখেছি:\n" + "\n".join("• " + f for f in facts)
        if "git" in low:
            return git_status_text()
        if "সিস্টেম" in text or "pc" in low and "অবস্থা" in text or "system info" in low:
            return system_info()
        if any(w in low for w in ("হ্যালো", "হাই", "hello", "hi", "সালাম", "আসসালামু")):
            return f"ওয়ালাইকুম আসসালাম ভাইয়া! আমি Sokhi — তোমার ল্যাপটপেই আছি। পড়াশোনা, গান, খবর, আবহাওয়া — যা লাগবে বলো। এখন {now_str()}।"
        if "তুমি কে" in text or "তোমার নাম" in text or "who are you" in low:
            return "আমি Sokhi ভাইয়া — তোমার নিজের বানানো AI সঙ্গী। Stonic-এর মতো তোমার PC-র ভিতরে থাকি, কিন্তু আমি সম্পূর্ণ ফ্রি আর পুরোপুরি তোমার।"
        if "ধন্যবাদ" in text or "thank" in low:
            return "তুমি খুশি হলেই আমি খুশি, ভাইয়া। আর কিছু লাগবে?"

        # --- v1.0: teacher + mock test (agents/away handled earlier)
        _tch = teacher_handle(text, low)
        if _tch:
            return _tch
        # --- v1.9.0 #759 চাপ-সিমুলেশন: tighter clock on the host exam
        _pr = et_pressure_request(text, low)
        if _pr:
            return _pr["header"] + exam_start(
                _pr["subject"] or _detect_subject(text, low) or "গণিত",
                _pr["count"], _pr["minutes"])
        if "মক টেস্ট" in text or "mock test" in low:
            return exam_start(_detect_subject(text, low) or "গণিত", 10, 10)
        if "পরীক্ষার অবস্থা" in text:
            return exam_status_text()
        if "পড়ার অগ্রগতি" in text:
            return study_progress_text()
        # --- v1.5.0 study pack (Wave-2: #654/#655/#664/#697/#721/#725/#748/#759)
        if "মাস্টারি টেস্ট" in text and not exam_active():
            _msubj = _detect_subject(text, low)
            if _msubj:
                _mstart = mastery_start(_msubj)
                if _mstart:
                    return _mstart
        # --- v1.8.0 chart pack (#47): inline SVG charts/diagrams
        if not exam_active():
            _ch = chart_reply(text)
            if _ch:
                return _ch
        _sp = study_pack_handle(text, low)
        if _sp:
            return _sp

        # --- v1.9.0 elite planning pack (#766/#767/#769/#770/#781/#782/#783/#784)
        _ep = ep_planning_handle(text, low)
        if _ep:
            return _ep
        _ee = ee_engine_handle(text, low)
        if _ee:
            return _ee
        if ("সাপ্তাহিক রিপোর্ট" in text or "বোর্ড সভা" in text
                or "সাপ্তাহিক বোর্ড" in text):
            return board_text()
        if "নিজের ডাক্তার" in text or "স্বাস্থ্য পরীক্ষা" in text:
            return doctor_report()["text"]
        if not exam_active() and mastery_active():
            _ma = mastery_answer(text)
            if _ma:
                return _ma
        # --- v1.9.0 elite analysis pack (#763/#764/#765) ---
        _ea_campaign = None
        try:
            _ec = load_json(DATA / "elite-campaign.json", {})
            if isinstance(_ec, dict) and _ec.get("exam_date"):
                _ea_campaign = _ec
        except Exception:
            _ea_campaign = None
        if ("অভিক্ষেপ" in text or "শেষ হতে কত দিন" in text
                or "পরীক্ষার আগে শেষ হবে" in text):
            return ea_projection_text(
                campaign=_ea_campaign,
                first_day=mem.get("first_day", "") or None)
        _ea = ea_analysis_handle(text, low)
        if _ea:
            return _ea
        # --- v1.9.0 elite training pack (#755/#756) — session route:
        # after mastery, before jobprep; disabled during a live exam.
        if not exam_active():
            _et = et_training_handle(text, low)
            if _et:
                return _et
        # --- v1.9.0 study sweep pack (#667/#703/#716/#729/#753) ---
        if not exam_active():
            _es = es_handle(text, low)
            if _es:
                return _es
        # --- v1.6.0 jobprep knowledge packs (#787/#788/#789/#796/#836/#943/#944/#945/#946/#949/#922/#923)
        _jp = jobprep_handle(text)
        if _jp:
            return _jp
        if exam_active() and re.match(r"^\s*(ক|খ|গ|ঘ|a|b|c|d|১|২|৩|৪|1|2|3|4)\s*[).।]?\s*$", text):
            return exam_answer(text)

        # --- learned knowledge first (works even offline, instant)
        cached = knowledge_get(text)
        if cached:
            return cached.get("a", "")

        # --- smart brain (free Gemini) if key exists; learn the answer
        smart = ask_gemini(text, mem)
        if smart:
            knowledge_put(text, smart)
            auto_evolve(mem)
            _notice = (LAST_MODEL_NOTICE.get("text") or "").strip()
            if _notice:
                return smart + "\n\n" + _notice
            return smart
        log_unanswered(text)

        auto_evolve(mem)
        if get_config().get("gemini_api_key"):
            return ("ভাইয়া, স্মার্ট মাথা থেকে এই মুহূর্তে সাড়া পাইনি — ফ্রি সার্ভিসে মাঝে মাঝে "
                    "লিমিট/চাপে এমন হয়, বা নেট একটু ধীর হলে। একটু পরে একই প্রশ্নটা আবার বলো, "
                    "ঠিক হয়ে যাবে। ততক্ষণে আমার অফলাইন কাজগুলো চলছে: অ্যাপ/সাইট খোলা, গান চালানো, "
                    "সময়, আবহাওয়া, খবর, সার্চ, মনে রাখা, নতুন স্কিল বানানো।")
        return ("ভাইয়া, এই কথাটার উত্তর আমার অফলাইন মাথায় এখনো নেই। আমি যা যা পারি: "
                "অ্যাপ/সাইট খোলা, YouTube-এ গান চালানো, সময়-তারিখ, আবহাওয়া, আজকের খবর, "
                "ওয়েব সার্চ ('সার্চ করো: ...'), মনে রাখা ('মনে রেখো: ...'), নতুন স্কিল বানানো "
                "('নতুন স্কিল: ...'), প্যাটার্ন বিশ্লেষণ, সিস্টেমের অবস্থা। "
                "আর তুমি চাইলে ফ্রি Gemini key (AI Studio থেকে, কার্ড লাগে না) বসিয়ে দিলে আমি আরও স্মার্ট হয়ে যাব — key বসানোর ধাপ আমি শিখিয়ে দেব।")


# ------------------------------------------------------------------- UI
HTML = r"""<!DOCTYPE html>
<html lang="bn"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sokhi — তোমার PC-র সঙ্গী</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Hind+Siliguri:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{
 --accent:#3aa6d6; --accent2:#256f96; --deep:#12314a;
 --bg:#0a0e16; --panel:#121926; --panel2:#182233; --line:#263449;
 --txt:#e8eef6; --muted:#93a3b8;
 --radius:12px; --radius-sm:8px;
 --shadow:0 1px 2px rgba(0,0,0,.28),0 6px 20px rgba(0,0,0,.16);
}
body[data-theme="blue"]{--accent:#3aa6d6;--accent2:#256f96;--deep:#12314a;--bg:#0a0e16;--line:#263449}
body[data-theme="purple"]{--accent:#9b7ed0;--accent2:#6b4fa3;--deep:#2b1e47;--bg:#0e0a16;--line:#372e4d}
body[data-theme="gold"]{--accent:#c9a227;--accent2:#8a6d1a;--deep:#3d2f08;--bg:#100d06;--line:#3d3620}
body[data-theme="pink"]{--accent:#d67ba8;--accent2:#9c4a76;--deep:#3d1a2b;--bg:#120a10;--line:#40283a}
*{box-sizing:border-box}
html,body{height:100%;overflow:hidden}
body{margin:0;font-family:'Hind Siliguri','Segoe UI',sans-serif;background:var(--bg);color:var(--txt);height:100vh;display:flex;flex-direction:column;font-size:15px;line-height:1.55;transition:background .4s}
.tagline{flex:none;text-align:center;font-size:11px;letter-spacing:.03em;color:var(--muted);padding:8px 16px 0;line-height:1.5}
header{flex:none;text-align:center;padding:4px 16px 8px}
h1{margin:4px 0 0;font-size:20px;font-weight:600;letter-spacing:.14em}
.sub{color:var(--muted);font-size:13px}
#main{flex:1;min-height:0;min-width:0}
#layout{display:grid;grid-template-columns:288px minmax(0,1fr) 400px;gap:16px;height:100%;min-height:0;max-width:1560px;width:100%;margin:0 auto;padding:8px 16px 12px;align-items:stretch}
#leftcol,#centercol,#rightcol{min-height:0;min-width:0;display:flex;flex-direction:column}
#leftcol{overflow-y:auto;overflow-x:hidden;padding-right:2px}
#centercol{overflow-y:auto;overflow-x:hidden;padding:0 4px}
#rightcol{overflow:hidden}
@media(max-width:1080px){
 #layout{grid-template-columns:1fr;grid-template-rows:minmax(96px,26%) auto minmax(0,1fr)}
 #leftcol{max-height:100%}
 #centercol{max-height:300px}
 #rightcol{min-height:0}
}
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:16px;margin-bottom:12px;box-shadow:var(--shadow);flex:none;display:flex;flex-direction:column;min-height:0}
.card h3{margin:0 0 8px;font-size:11px;font-weight:600;letter-spacing:.09em;text-transform:uppercase;color:var(--muted)}
.card .body{font-size:13.5px;line-height:1.6;white-space:pre-wrap}
.small{font-size:12px;color:var(--muted)}
#weather,#news{overflow-y:auto;min-height:0;max-height:24vh}
#hubsteps{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12.5px;line-height:1.7;white-space:pre-wrap;overflow-y:auto;min-height:0;max-height:24vh}
#board{overflow-y:auto;min-height:0;max-height:18vh}
#orb{width:280px;height:300px;margin:8px auto 0;position:relative;cursor:pointer;flex:none}
#orb canvas{display:block;width:280px;height:300px}
#orb.talking{filter:brightness(1.2)}
.nodes{display:flex;gap:8px;justify-content:center;flex-wrap:wrap;margin:12px 0 4px;flex:none}
.nodes button{font-size:13px;padding:8px 14px;border-radius:999px}
#chat{display:flex;flex-direction:column;gap:8px;flex:1;min-height:0;overflow-y:auto;padding:2px 6px 8px 2px}
.msg{max-width:88%;padding:10px 14px;border-radius:var(--radius);white-space:pre-wrap;line-height:1.55;font-size:15px;display:flex;gap:8px;align-items:flex-start}
.me{align-self:flex-end;background:var(--accent2);color:#fff}
.sokhi{align-self:flex-start;background:var(--panel2);border:1px solid var(--line)}
.avatar{flex:0 0 auto;width:24px;height:24px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#ffffffcc,var(--accent) 55%,var(--deep));display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;color:#04101f;margin-top:1px}
#bar{flex:none;display:flex;gap:8px;align-items:center;width:100%;max-width:820px;margin:0 auto;padding:0 16px 12px;background:transparent;z-index:40}
input,button,select,textarea{font-family:inherit;font-size:15px;border-radius:var(--radius-sm);border:1px solid var(--line);background:#0d1524;color:var(--txt);padding:9px 12px}
input{flex:1;min-width:0}
button{cursor:pointer;background:var(--panel2);transition:border-color .15s,background .15s}
button:hover{border-color:var(--accent)}
textarea{width:100%;resize:vertical}
input[type=range]{flex:1;padding:0;accent-color:var(--accent)}
.quick{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;flex:none}
.quick button{font-size:13px;padding:7px 12px;border-radius:999px}
#pinbox{max-width:420px;margin:32px auto;background:var(--panel);padding:24px;border-radius:var(--radius);text-align:center;border:1px solid var(--line);box-shadow:var(--shadow)}
#gear{position:fixed;top:10px;right:10px;width:42px;height:42px;border-radius:50%;font-size:18px;padding:0;z-index:50;box-shadow:var(--shadow)}
#modal{display:none;position:fixed;inset:0;background:rgba(2,4,10,.72);z-index:60;overflow:hidden}
#modal .panel{max-width:480px;max-height:calc(100vh - 48px);overflow-y:auto;min-height:0;margin:24px auto;background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:24px;box-shadow:var(--shadow)}
#modal .panel h3{margin:0 0 12px;font-size:16px;font-weight:600}
#modal hr{border:none;border-top:1px solid var(--line);margin:16px 0}
#ruleslist{overflow-y:auto;min-height:0;max-height:30vh}
#livebtn.on{background:#8c1d33;border-color:#c94f6d;color:#fff}
.tabs{display:flex;gap:6px;margin-bottom:12px;flex-wrap:wrap;flex:none}
.tabs button{font-size:13.5px;padding:8px 14px;border-radius:999px;color:var(--muted)}
.tabs button.on{color:#04101f;background:var(--accent);border-color:var(--accent);font-weight:600}
.tabpane{display:none}
.tabpane.on{display:flex;flex-direction:column;flex:1;min-height:0}
#agentlist{flex:1;min-height:0;overflow-y:auto;padding-right:4px}
#noteslist,#tasklist{overflow-y:auto;min-height:0;flex:1;margin-top:8px;padding-right:4px}
.agentcard{border:1px solid var(--line);border-radius:var(--radius);padding:12px 14px;margin-bottom:8px;background:var(--panel);font-size:13.5px;box-shadow:var(--shadow)}
.agentcard .st{font-size:12px;color:var(--muted)}
.step{font-size:12.5px;color:var(--muted)}
.themebtns{display:flex;gap:8px;flex-wrap:wrap}
.themebtns button{font-size:13px;padding:7px 12px}
#examchip{display:none;align-items:center;gap:8px;background:#8c1d33;border:1px solid #c94f6d;border-radius:999px;padding:5px 12px;font-size:13.5px;width:max-content;margin:8px auto;flex:none}
#examform{display:none;margin-top:12px}
#examform .row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
#examform input[type=number]{flex:0 0 84px}
#idle{display:none;position:fixed;inset:0;background:rgba(2,4,10,.96);z-index:90;text-align:center;padding-top:14vh;cursor:pointer}
#idle .clock{font-size:84px;font-weight:700;letter-spacing:2px}
#idle .date{font-size:22px;color:var(--muted);margin-top:8px}
#idle .wx{font-size:16px;color:var(--muted);margin-top:16px;white-space:pre-wrap}
.listitem{border-bottom:1px solid var(--line);padding:8px 0;font-size:14px;white-space:pre-wrap}
.secttl{font-size:14px;font-weight:600;margin-bottom:4px}
.statline{font-size:13px;color:var(--muted);margin-bottom:8px}
.hint{font-size:12px;color:var(--muted);margin-top:6px;line-height:1.5}
/* v1.2 fe1 */
#bar{flex-wrap:wrap;align-items:flex-end}
#bar textarea#text{flex:1;width:auto;min-width:0;resize:none;max-height:132px;overflow-y:auto;line-height:1.45}
#suggest{display:flex;flex-wrap:wrap;gap:6px;flex:0 0 100%;justify-content:center}
#suggest:empty{display:none}
.chip{font-size:12.5px;padding:6px 12px;border-radius:999px;background:var(--panel2)}
#stopbtn{background:#8c1d33;border-color:#c94f6d;color:#fff}
#scrollbtn{position:fixed;right:18px;bottom:88px;z-index:45;border-radius:999px;padding:8px 14px;font-size:13px;box-shadow:var(--shadow);background:var(--accent2);color:#fff;border:1px solid var(--line)}
.msg-main{flex:1;min-width:0;display:flex;flex-direction:column;gap:3px}
.me .msg-main{align-items:flex-end}
.msg-body{white-space:pre-wrap;word-break:break-word;min-width:0}
.msg-body.md{white-space:normal}
.msg-meta{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.me .msg-meta{flex-direction:row-reverse}
.ts{font-size:11px;color:var(--muted);opacity:.85}
.msg-actions{display:inline-flex;gap:4px;flex-wrap:wrap}
.msg-actions button{font-size:11px;padding:2px 8px;border-radius:999px;line-height:1.5}
.msg-actions button.rated{background:var(--accent);color:#04101f;border-color:var(--accent)}
.msg.thinking{opacity:.92}
.thinkdots span{animation:thinkblink 1.2s infinite;display:inline-block}
.thinkdots span:nth-child(2){animation-delay:.2s}
.thinkdots span:nth-child(3){animation-delay:.4s}
@keyframes thinkblink{0%,60%,100%{opacity:.15}30%{opacity:1}}
.mdline{margin:1px 0}
.mdgap{height:8px}
.mdh{font-weight:700;font-size:16px;margin:6px 0 3px}
.mdlist{margin:4px 0 4px 18px;padding:0}
.mdlist li{margin:2px 0}
.msg-body code{background:rgba(0,0,0,.35);padding:1px 5px;border-radius:5px;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:13px}
.mdcode{position:relative;margin:8px 0;background:#0a101d;border:1px solid var(--line);border-radius:8px}
.mdcode pre{margin:0;padding:10px 12px;overflow-x:auto}
.mdcode pre code{background:transparent;padding:0;font-size:13px;white-space:pre}
.mdcode .codecopy{position:absolute;top:6px;right:6px;font-size:11px;padding:2px 8px;border-radius:999px}
.msg-body a{color:var(--accent);text-decoration:underline}
.msg-body.folded{max-height:170px;overflow:hidden}
.chartbox{margin-top:10px;background:#0d1524;border:1px solid var(--line);border-radius:var(--radius-sm);padding:10px 12px;overflow-x:auto;font-size:13px;color:var(--muted)}
.chartbox svg{max-width:100%;height:auto;display:block}
.msg-body .chartbox{white-space:normal}
</style></head><body data-theme="blue">
<div class="tagline">Sokhi is the world's first Sci-Fi AI Desktop Experience — built for those who grew up dreaming of JARVIS, and refused to settle for boring software.</div>
<header>
<div class="sub" id="status">তোমার Windows ল্যাপটপের নিজের AI সঙ্গী — সম্পূর্ণ ফ্রি</div>
</header>

<button id="gear" title="সেটিংস" onclick="openSettings()">⚙️</button>
<div id="modal" onclick="if(event.target===this)this.style.display='none'">
 <div class="panel">
  <h3>সেটিংস</h3>
  <div class="secttl">স্মার্ট মাথা (Gemini ফ্রি key)</div>
  <div id="keystat" class="statline">key-র অবস্থা জানা যাচ্ছে…</div>
  <input id="apikey" type="password" placeholder="Gemini key বসাও (শুধু এই ল্যাপটপেই থাকবে)" style="width:100%;margin-bottom:8px">
  <div style="display:flex;gap:6px;flex-wrap:wrap">
   <button onclick="saveKey()">সেভ করো</button>
   <button onclick="testKey()">টেস্ট করো</button>
   <button onclick="clearKey()">key মোছো</button>
  </div>
  <div id="keymsg" style="font-size:13px;margin-top:8px"></div>
  <div class="hint">key কাউকে পাঠাবে না — এই ঘরে বসালেই শুধু এই ল্যাপটপে সেভ থাকে।</div>
  <hr>
  <div class="secttl">আমাকে যে নামে ডাকবে</div>
  <div style="display:flex;gap:6px">
   <input id="callname" type="text" placeholder="যেমন: সোনা / জান (ফাঁকা রাখলে নাম ছাড়া)" style="flex:1">
   <button onclick="saveCall()">সেভ</button>
  </div>
  <div class="hint">চ্যাটে বললেও হবে: "আমাকে সোনা বলে ডাকো"। Sokhi আর ভাইয়া বলে ডাকবে না।</div>
  <hr>
  <div class="secttl">গলা (ভয়েস)</div>
  <div id="voicestat" class="statline">গলার অবস্থা জানা যাচ্ছে…</div>
  <div id="voiceengine" class="statline"></div>
  <button onclick="testVoice()">গলা টেস্ট করো</button>
  <div style="font-size:13px;margin-top:12px">গলার টোন:
   <select id="tonepreset" onchange="saveTone()"><option>মিষ্টি</option><option>স্বাভাবিক</option><option>প্রাণবন্ত</option></select>
  </div>
  <div style="font-size:13px;margin-top:12px">
   <label for="voicerate">গলার গতি: <span id="voicerateval">1.00×</span></label>
   <div style="display:flex;align-items:center;gap:8px;margin-top:6px">
    <span class="small">ধীর</span>
    <input id="voicerate" type="range" min="0.8" max="1.2" step="0.05" value="1" oninput="voiceRateInput()" onchange="saveVoiceRate()">
    <span class="small">দ্রুত</span>
   </div>
  </div>
  <hr>
  <div class="secttl" style="margin-bottom:6px">রঙের থিম</div>
  <div class="themebtns">
   <button onclick="setTheme('blue')">নীল</button>
   <button onclick="setTheme('purple')">বেগুনি</button>
   <button onclick="setTheme('gold')">সোনালি</button>
   <button onclick="setTheme('pink')">গোলাপি</button>
  </div>
  <hr>
  <div class="secttl">GitHub — নিজে আপডেটের ঠিকানা</div>
  <div id="ghstat" class="statline">…</div>
  <div style="display:flex;gap:6px">
   <input id="updateurl" type="text" placeholder="raw manifest.json-এর লিংক বসাও" style="flex:1">
   <button onclick="saveUrl()">সেভ</button>
  </div>
  <div class="hint">লিংক বসালেই Sokhi GitHub থেকে নিজে নতুন ভার্সন এনে বসাতে পারবে। ধাপগুলো Saba-র গাইডে আছে।</div>
  <hr>
  <div class="secttl">নিজে নিজে আপগ্রেড</div>
  <div id="autostat" class="statline">…</div>
  <button onclick="document.getElementById('modal').style.display='none';quick('আপগ্রেড চেক করো')">এখনই স্ব-আপগ্রেড চেক করো</button>
  <hr>
  <div id="rulesec">
  <div class="secttl">আমার নিয়ম (N13)</div>
  <div class="small" style="margin-bottom:6px">তুমি যে নিয়ম দেবে, Sokhi সবসময় মেনে চলবে। নতুন নিয়ম যোগ করলে সেটা সেভ হয়ে থাকবে।</div>
  <div id="ruleslist" style="font-size:13.5px;white-space:pre-wrap;margin-bottom:8px">নিয়ম লোড হচ্ছে…</div>
  <div style="display:flex;gap:6px">
   <input id="newrule" type="text" placeholder="নতুন নিয়ম লেখো…" style="flex:1">
   <button onclick="addRule()">নিয়ম যোগ করো</button>
  </div>
  </div>
  <button style="float:right;margin-top:14px" onclick="document.getElementById('modal').style.display='none'">বন্ধ করো</button>
  <div style="clear:both"></div>
 </div>
</div>

<div id="pinbox" style="display:none">
 <p>ভাইয়া, প্রথমবার PIN দাও (ল্যাপটপে Sokhi চালালে স্ক্রিনে PIN দেখাবে)</p>
 <input id="pin" inputmode="numeric" placeholder="PIN" style="width:140px;text-align:center">
 <button onclick="savePin()">ঢোকো</button></div>

<div id="main" style="display:none">
<div id="layout">

 <div id="leftcol">
  <div class="card"><h3>আবহাওয়া</h3><div class="body" id="weather">লোড হচ্ছে…</div></div>
  <div class="card"><h3>আজকের headlines</h3><div class="body" id="news">লোড হচ্ছে…</div></div>
  <div class="card"><h3>Visual Hub</h3><div class="small" style="margin-bottom:6px">চলমান agent কাজের ধাপ</div><div id="hubsteps">এখন কোনো কাজ চলছে না।</div></div>
  <div class="card"><h3>Whiteboard</h3><div class="body" id="board">বোর্ড খালি।</div>
   <button style="margin-top:8px;font-size:13px" onclick="clearBoard()">বোর্ড মোছো</button></div>
 </div>

 <div id="centercol">
  <div id="orb" title="কথা থামাতে চাপ দাও"><canvas id="pcanvas" width="280" height="300"></canvas></div>
  <h1 style="text-align:center">SOKHI</h1>
  <div class="nodes">
   <button onclick="quick('কী কী মনে রেখেছ?')">Memory</button>
   <button onclick="quick('প্যাটার্ন বিশ্লেষণ করো')">Soul</button>
   <button id="skillsnode" onclick="quick('তোমার স্কিলগুলো কী কী?')">Skills</button>
   <button onclick="openSettings()">Settings</button>
  </div>
  <div id="examchip"><span id="examtimer">⏳ 00:00</span><button style="font-size:12.5px;padding:4px 10px" onclick="finishExam()">শেষ করো</button></div>
  <div class="quick">
   <button onclick="quick('আজকের খবর দাও')">খবর</button>
   <button onclick="quick('আবহাওয়া কেমন?')">আবহাওয়া</button>
   <button onclick="quick('ইউটিউব খোলো')">YouTube</button>
   <button onclick="quick('প্যাটার্ন বিশ্লেষণ করো')">আমার প্যাটার্ন</button>
   <button onclick="quick('কী কী মনে রেখেছ?')">স্মৃতি</button>
   <button onclick="quick('তোমার ভার্সন কত?')">ভার্সন</button>
   <button onclick="quick('সিস্টেমের অবস্থা দেখাও')">PC-র অবস্থা</button>
   <button onclick="quick('আমাকে গণিত শেখাও')">শেখাও</button>
   <button onclick="quick('কতদূর হলো?')">কতদূর হলো</button>
   <button onclick="toggleExamForm()">মক টেস্ট</button>
   <button onclick="openRules()">নিয়ম</button>
  </div>
  <div id="examform" class="card">
   <h3>মক টেস্ট শুরু করো</h3>
   <div class="row">
    <select id="examsubject"><option>বাংলা সাহিত্য</option><option>বাংলা ব্যাকরণ</option><option>গণিত</option><option>ইংরেজি</option><option>সাধারণ জ্ঞান</option><option>ICT</option></select>
    <input id="examcount" type="number" value="10" min="1" max="100" title="প্রশ্ন সংখ্যা">
    <input id="examminutes" type="number" value="10" min="1" max="180" title="মিনিট">
    <button onclick="startExam()">শুরু করো ▶</button>
   </div>
   <div class="small" style="margin-top:6px">বিষয়, প্রশ্ন সংখ্যা আর সময় (মিনিট) বেছে শুরু করো। উত্তরগুলো নিচের লেখার ঘরে লিখে পাঠালেই পরীক্ষায় জমা হবে।</div>
  </div>
 </div>

 <div id="rightcol">
  <div class="tabs">
   <button id="tabbtn-chat" class="on" onclick="showTab('chat')">চ্যাট</button>
   <button id="tabbtn-agents" onclick="showTab('agents')">এজেন্ট</button>
   <button id="tabbtn-notes" onclick="showTab('notes')">নোট</button>
   <button id="tabbtn-tasks" onclick="showTab('tasks')">টাস্ক</button>
  </div>
  <div class="tabpane on" id="pane-chat"><div id="chat"></div></div>
  <div class="tabpane" id="pane-agents"><div id="agentlist"><div class="small">কোনো agent কাজ নেই।</div></div></div>
  <div class="tabpane" id="pane-notes">
   <textarea id="notetext" rows="4" placeholder="নোট লেখো…"></textarea>
   <button style="margin-top:6px" onclick="saveNote()">নোট সেভ করো</button>
   <div id="noteslist" style="margin-top:8px"></div>
  </div>
  <div class="tabpane" id="pane-tasks">
   <div style="display:flex;gap:6px"><input id="newtask" type="text" placeholder="নতুন টাস্ক লেখো…" style="flex:1"><button onclick="addTask()">যোগ করো</button></div>
   <div id="tasklist" style="margin-top:8px"></div>
  </div>
 </div>

</div>
</div>

<div id="bar">
 <div id="suggest"></div>
 <textarea id="text" rows="1" placeholder="Sokhi-কে বলো... (বাংলা/Banglish)"></textarea>
 <button onclick="mic()">🎤</button>
 <button id="livebtn" onclick="toggleLive()">লাইভ</button>
 <button id="stopbtn" onclick="stopAll()" style="display:none">⏹ থামাও</button>
 <button onclick="send()">পাঠাও</button>
 <button id="scrollbtn" onclick="scrollChatToBottom()" style="display:none">⬇ সর্বশেষ</button>
</div>

<div id="idle">
 <div class="clock" id="idleclock">--:--</div>
 <div class="date" id="idledate"></div>
 <div class="wx" id="idlewx"></div>
 <div class="small" style="margin-top:22px">যেকোনো জায়গায় চাপ দিলেই Sokhi ফিরে আসবে</div>
</div>

<script>
const PINKEY='sokhi_pin';
function pin(){return localStorage.getItem(PINKEY)||''}
function savePin(){localStorage.setItem(PINKEY,document.getElementById('pin').value.trim());location.reload()}
async function api(path,body){
 const r=await fetch(path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json','X-PIN':pin()},body:body?JSON.stringify(body):undefined});
 if(r.status===403){document.getElementById('pinbox').style.display='block';document.getElementById('main').style.display='none';throw 'pin'}
 return r.json()}
async function apiGet(path){
 const r=await fetch(path,{headers:{'X-PIN':pin()}});
 if(!r.ok)throw 'bad';
 return r.json()}
function setTheme(name){
 document.body.dataset.theme=name;
 try{localStorage.setItem('sokhi_theme',name)}catch(e){}
 drawMoodBase();}
try{const savedTheme=localStorage.getItem('sokhi_theme');if(savedTheme)document.body.dataset.theme=savedTheme}catch(e){}
function openSettings(){document.getElementById('modal').style.display='block';loadRules()}
function openRules(){openSettings();setTimeout(()=>{const el=document.getElementById('rulesec');if(el)el.scrollIntoView({behavior:'smooth',block:'center'})},80)}
function showTab(name){
 for(const n of ['chat','agents','notes','tasks']){
  document.getElementById('pane-'+n).classList.toggle('on',n===name);
  document.getElementById('tabbtn-'+n).classList.toggle('on',n===name)}
 if(name==='notes')loadNotes();
 if(name==='tasks')loadTasks();
 if(name==='agents')pollAgents()}
window.voiceRate=window.voiceRate||1;
function chatDistFromBottom(){
 const c=document.getElementById('chat');if(!c)return 0;
 return c.scrollHeight-c.scrollTop-c.clientHeight}
function scrollChatToBottom(){
 const c=document.getElementById('chat');if(!c)return;
 c.scrollTop=c.scrollHeight;
 requestAnimationFrame(()=>{c.scrollTop=c.scrollHeight})}
function add(t,who,opts){
 opts=opts||{};
 const c=document.getElementById('chat');if(!c)return null;
 const distBefore=chatDistFromBottom();
 const d=document.createElement('div');d.className='msg '+who;
 const idx=(typeof opts.idx==='number')?opts.idx:msgSeq;
 d.dataset.idx=idx;msgSeq=Math.max(msgSeq,idx+1);
 d._full=String(t==null?'':t);
 if(opts.err)d.dataset.err='1';
 const main=document.createElement('div');main.className='msg-main';
 const body=document.createElement('div');body.className='msg-body';main.appendChild(body);
 const meta=document.createElement('div');meta.className='msg-meta';
 const tsEl=document.createElement('span');tsEl.className='ts';tsEl.textContent=fmtTs(opts.ts);meta.appendChild(tsEl);
 const act=document.createElement('span');act.className='msg-actions';meta.appendChild(act);
 main.appendChild(meta);
 if(who==='sokhi'){
  const av=document.createElement('span');av.className='avatar';av.textContent='স';d.appendChild(av);
  d.appendChild(main);
  d.style.cursor='pointer';d.title='শুনতে চাপ দাও';
  if(!opts.noActions)buildSokhiActions(d,act);
  body.addEventListener('click',e=>{
   if(e.target.closest('button')||e.target.closest('a'))return;
   if(activeReveal&&activeReveal.msgEl===d){finishReveal();return}
   speak(d._full)});
  if(opts.reveal)startReveal(d,d._full);else renderFinalBody(d,d._full)}
 else{
  d.appendChild(main);
  body.textContent=d._full;
  if(!opts.noActions)buildMeActions(d,act)}
 c.appendChild(d);
 if(who==='me'||distBefore<=120)scrollChatToBottom();
 if(who==='sokhi')refreshRegenButtons();
 return d}
let edgeOk=null, speakingNow=false, currentAudio=null, speakToken=0;
function stopSpeak(){speakToken++;try{speechSynthesis.cancel()}catch(e){} if(currentAudio){try{currentAudio.pause()}catch(e){} currentAudio=null} speakingNow=false;document.getElementById('orb').classList.remove('talking');setMood('calm');try{echoNoteEnd()}catch(e){}}
function chunksOf(t){
 const clean=t.replace(/[•\*\#]/g,' ').replace(/\n+/g,'। ');
 const parts=clean.split(/(?<=[।!?…])\s*/).map(s=>s.trim()).filter(Boolean);
 const out=[];let cur='';
 for(const s of parts){if((cur+' '+s).length>200){if(cur)out.push(cur);cur=s}else cur=cur?cur+' '+s:s}
 if(cur)out.push(cur);return out.length?out:[clean]}
async function edgeSpeak(text,rate){
 const r=await fetch('/api/tts',{method:'POST',headers:{'Content-Type':'application/json','X-PIN':pin()},body:JSON.stringify(rate?{text,rate}:{text})});
 if(!r.ok)throw 'noedge';
 const blob=await r.blob();const url=URL.createObjectURL(blob);
 return new Promise(res=>{const a=new Audio(url);currentAudio=a;a.onended=()=>{URL.revokeObjectURL(url);if(currentAudio===a)currentAudio=null;res()};a.onerror=()=>res();a.play().catch(()=>res())})}
function synthSpeak(text,rate){
 return new Promise(res=>{
 try{const u=new SpeechSynthesisUtterance(text);u.lang='bn-BD';u.rate=(rate?.8:.92)*(window.voiceRate||1);u.pitch=1.05;
 const vs=speechSynthesis.getVoices();
 const fe8chosen=window.browserVoiceName?vs.find(v=>v.name===window.browserVoiceName):null;
 const f=fe8chosen||vs.find(v=>/google/i.test(v.name)&&/bn|বাংলা/i.test(v.lang+v.name))||vs.find(v=>/bn/i.test(v.lang)&&/female|নাবনিতা|nabanita/i.test(v.name))||vs.find(v=>/bn/i.test(v.lang))||vs.find(v=>/female/i.test(v.name));
 if(f)u.voice=f;u.onend=()=>res();u.onerror=()=>res();speechSynthesis.speak(u)}catch(e){res()}})}
async function speak(t,rate){
 t=String(t==null?'':t).replace(/\[\[CHART:[^\]]*\]\]/g,'').replace(/\n{3,}/g,'\n\n'); // #47: চার্ট-মার্কার কখনো পড়া হবে না
 if(!t.trim())return; // #47: শুধু মার্কার থাকলে বলার কিছু নেই
 echoNoteSpoken(t); /* v1.9.1 echo guard: যা বলা হচ্ছে মনে রাখো */
 const my=++speakToken;speakingNow=true;setMood('speaking');const orb=document.getElementById('orb');orb.classList.add('talking');
 const chunks=(t&&t.length<180)?[t]:chunksOf(t);
 try{for(const c of chunks){
  if(my!==speakToken)break;
  if(edgeOk!==false){try{await edgeSpeak(c,rate);edgeOk=true;continue}catch(e){edgeOk=false}}
  if(my!==speakToken)break;
  await synthSpeak(c,rate)}}catch(e){}
 if(my===speakToken){orb.classList.remove('talking');speakingNow=false;setMood(liveOn?'listening':'calm');echoNoteEnd()}}
/* ---------- v1.9.1 echo guard: নিজের কণ্ঠ চেনা ----------
   বাগ: লাইভ মোডে স্পিকার থেকে Sokhi-র নিজের বলা কথা মাইকে ফিরে এসে
   আবার ইনপুট হয়ে যেত — Sokhi নিজে নিজেকেই উত্তর দিত (loop)।
   সমাধান: speak() যা বলছে তা মনে রাখা হয় (echoNoteSpoken); বলা শেষের
   ECHO_TAIL_MS (800ms) পর্যন্ত জানালা খোলা থাকে (echoNoteEnd)।
   recognition থেকে আসা লেখা dispatch-এর আগে isEchoOfSpeech() যাচাই করে —
   মিললে নীরবে ফেলে দেওয়া হয় (শুধু status line-এ নোট, chat-এ নয়)।
   মিলের নিয়ম (echoNorm: ছোট হাতের, যতিচিহ্ন ছাড়া, বাংলা সংখ্যা→ASCII):
     (ক) containment: শোনা লেখা (≥৬ অক্ষর) বলা কথার অংশ, অথবা বলা কথা
         (≥৬ অক্ষর) শোনা লেখার অংশ (echo + বাড়তি শব্দ);
     (খ) টোকেন-overlap: |A∩B| / min(|A|,|B|) ≥ 0.6 (ECHO_OVERLAP_MIN)
         এবং মেলা আলাদা টোকেন ≥ ২;
     (গ) একটিমাত্র লম্বা শব্দ (≥৪ অক্ষর) হুবহু মিললে।
   সম্পূর্ণ আলাদা কথা (আসল barge-in) কখনো আটকায় না — ওপরে কোনো নিয়মেই
   মিলবে না। জানালার বাইরে (বলা শেষের 800ms পর) একই কথা বললেও আসল ইনপুট।
   টগল: সেটিংসের echo_guard (ডিফল্ট চালু); বন্ধ = v1.9.0 আচরণ। */
let echoGuardOn=true;
try{echoGuardOn=localStorage.getItem('sokhi_echoguard')!=='0'}catch(e){}
let echoSpoken={norm:'',tokens:[],until:0};
const ECHO_TAIL_MS=800,ECHO_OVERLAP_MIN=0.6;
function echoNorm(s){
 return String(s==null?'':s).toLowerCase()
  .replace(/[০-৯]/g,function(d){return '০১২৩৪৫৬৭৮৯'.indexOf(d)})
  .replace(/[\u200B-\u200D\uFEFF]/g,'')
  .replace(/[।॥,.!?;:'"“”‘’«»()\[\]{}<>|/\\@#$%^&*_+=~`\-–—•·…]/g,' ')
  .replace(/\s+/g,' ').trim()}
function echoNoteSpoken(t){
 const n=echoNorm(t);
 echoSpoken={norm:n,tokens:n?n.split(' '):[],until:Date.now()+86400000}}
function echoNoteEnd(){
 if(echoSpoken.norm)echoSpoken.until=Date.now()+ECHO_TAIL_MS}
function isEchoOfSpeech(txt){
 try{
  if(!echoGuardOn)return false;
  if(!echoSpoken.norm||!echoSpoken.tokens.length)return false;
  if(!speakingNow&&Date.now()>echoSpoken.until)return false;
  const n=echoNorm(txt);if(!n)return false;
  const sp=echoSpoken.norm;
  if(n.length>=6&&sp.indexOf(n)>=0)return true;
  if(sp.length>=6&&n.indexOf(sp)>=0)return true;
  const tt=n.split(' '),st=new Set(echoSpoken.tokens),seen=new Set();let inter=0;
  for(const w of tt){if(st.has(w)&&!seen.has(w)){seen.add(w);inter++}}
  if(inter>=2&&inter/Math.min(tt.length,echoSpoken.tokens.length)>=ECHO_OVERLAP_MIN)return true;
  if(tt.length===1&&inter===1&&tt[0].length>=4)return true;
  return false}catch(e){return false}}
let liveOn=false, recog=null;
function setStatus(x){document.getElementById('status').textContent=x}
function toggleLive(){liveOn?stopLive():startLive()}
function startLive(){
 const R=window.SpeechRecognition||window.webkitSpeechRecognition;
 if(!R){alert('এই ব্রাউজারে লাইভ কথা হবে না ল্যাপটপের Chrome-এ খোলো');return}
 liveOn=true;setMood('listening');document.getElementById('livebtn').classList.add('on');document.getElementById('livebtn').textContent='লাইভ চালু';
 add('লাইভ মোড চালু — এখন শুধু কথা বলো, আমি শুনে উত্তর দেব। থামাতে বলো: লাইভ বন্ধ।','sokhi');
 listen()}
function stopLive(){liveOn=false;setMood('calm');const b=document.getElementById('livebtn');b.classList.remove('on');b.textContent='লাইভ';
 document.getElementById('orb').classList.remove('listening');try{recog&&recog.abort()}catch(e){}setStatus('লাইভ বন্ধ')}
function listen(){
 if(speakingNow)try{stopSpeak()}catch(e){} /* v1.4 #113 barge-in: live শোনা শুরু হলেই বলা থামবে */
 if(!liveOn||speakingNow)return;
 const R=window.SpeechRecognition||window.webkitSpeechRecognition;if(!R)return;
 recog=new R();recog.lang='bn-BD';recog.interimResults=false;
 document.getElementById('orb').classList.add('listening');setMood('listening');setStatus('🎧 শুনছি…');
 recog.onresult=async e=>{
  document.getElementById('orb').classList.remove('listening');
  const txt=e.results[0][0].transcript.trim();if(!txt){listen();return}
  if(isEchoOfSpeech(txt)){try{console.debug('echo guard: নিজের কণ্ঠ ফেলে দেওয়া হলো')}catch(e){} setStatus('🔇 নিজের কণ্ঠ ফেলে দেওয়া হলো');listen();return}
  if(/লাইভ বন্ধ|থামো|স্টপ/.test(txt)){add(txt,'me');stopLive();add('লাইভ বন্ধ করলাম।','sokhi');return}
  add(txt,'me');setStatus('🤔 ভাবছি…');setMood('thinking');
  try{const j=await api('/api/chat',{message:txt});add(j.reply,'sokhi');setStatus('🗣️ বলছি…');await speak(j.reply,moodRate(txt))}catch(err){}
  if(liveOn)listen()};
 recog.onerror=e=>{document.getElementById('orb').classList.remove('listening');
  if(e.error==='not-allowed'){stopLive();alert('মাইকের অনুমতি লাগবে Chrome-এর ঠিকানার পাশে 🔒 চেপে Microphone Allow করো');return}
  if(liveOn&&!speakingNow)setTimeout(listen,700)};
 recog.onend=()=>{document.getElementById('orb').classList.remove('listening');if(liveOn&&!speakingNow)setTimeout(listen,350)};
 try{recog.start()}catch(e){}}
function moodRate(t){return /ক্লান্ত|মন খারাপ|ভালো লাগছে না|টেনশন|দুঃখ|কষ্ট হচ্ছে/.test(t)?'-16%':null}
let examActive=false, examEndAt=0, examTimerId=null;
async function send(speakIt){
 const el=document.getElementById('text');const t=el.value.trim();if(!t)return;el.value='';autoGrowText();
 lastUserText=t;
 if(pendingEditIdx!==null){
  const keep=pendingEditIdx;pendingEditIdx=null;
  if(!examActive){
   try{await api('/api/convos',{action:'truncate',keep:keep})}catch(e){}
   document.querySelectorAll('#chat .msg').forEach(m=>{const ix=parseInt(m.dataset.idx,10);if(!isNaN(ix)&&ix>=keep)m.remove()});
   msgSeq=keep;clearSuggestions()}}
 add(t,'me');
 if(examActive){
  try{const j=await api('/api/exam',{action:'answer',answer:t});
   if(j&&j.reply)add(j.reply,'sokhi');
   if(j&&(j.done||j.finished||j.ended))endExamUi();
  }catch(e){}
  return}
 await fetchReply(t,speakIt)}
function quick(t){const el=document.getElementById('text');el.value=t;autoGrowText();send()}
/* ---------- v1.2 fe1: chat experience (ideas 1-14, 34, 40) ---------- */
let msgSeq=0, activeReveal=null, thinkingEl=null, thinkingTimer=null, thinkingStart=0;
let lastFailedText='', lastUserText='', pendingEditIdx=null, stopRequested=false, suggRotate=0;
function bnDigits(s){return String(s).replace(/[0-9]/g,d=>'০১২৩৪৫৬৭৮৯'[+d])}
function fmtTs(ts){
 let d;
 if(ts==null||ts==='')d=new Date();
 else if(typeof ts==='number')d=new Date(ts<1e12?ts*1000:ts);
 else if(typeof ts==='string'&&/^\d+$/.test(ts.trim())){const n=+ts;d=new Date(n<1e12?n*1000:n)}
 else{d=new Date(ts);if(isNaN(d.getTime()))d=new Date()}
 const h=d.getHours();
 const period=h<4?'রাত':h<6?'ভোর':h<12?'সকাল':h<17?'দুপুর':h<19?'বিকেল':h<21?'সন্ধ্যা':'রাত';
 let h12=h%12;if(h12===0)h12=12;
 return period+' '+bnDigits(h12)+':'+bnDigits(String(d.getMinutes()).padStart(2,'0'))}
function escapeHtml(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
function mdInline(esc){
 let s=esc;
 s=s.replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g,'<a href="$2" target="_blank" rel="noopener">$1</a>');
 s=s.replace(/(^|[\s(])(https?:\/\/[^\s<]+)/g,'$1<a href="$2" target="_blank" rel="noopener">$2</a>');
 s=s.replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>');
 s=s.replace(/(^|[^*])\*([^\*\n]+)\*/g,'$1<em>$2</em>');
 return s}
function mdInlineCode(line){
 const parts=line.split(/`([^`]+)`/);
 return parts.map((p,i)=>i%2===1?'<code>'+p+'</code>':mdInline(p)).join('')}
function renderMarkdown(src){
 const text=String(src==null?'':src);
 const blocks=text.split(/```(?:\w+)?\n?/);
 let html='';
 for(let bi=0;bi<blocks.length;bi++){
  if(bi%2===1){
   const code=blocks[bi].replace(/\n$/,'');
   html+='<div class="mdcode"><button type="button" class="codecopy">📋 কপি</button><pre><code>'+escapeHtml(code)+'</code></pre></div>';
   continue}
  const seg=escapeHtml(blocks[bi]);
  const lines=seg.split('\n');let inList=false;
  const closeList=()=>{if(inList){html+='</ul>';inList=false}};
  for(const line of lines){
   const h=line.match(/^(#{1,3})\s+(.*)$/);
   if(h){closeList();html+='<div class="mdh">'+mdInlineCode(h[2])+'</div>';continue}
   const li=line.match(/^\s*[-•]\s+(.*)$/);
   if(li){if(!inList){html+='<ul class="mdlist">';inList=true}html+='<li>'+mdInlineCode(li[1])+'</li>';continue}
   closeList();
   if(line.trim()===''){html+='<div class="mdgap"></div>';continue}
   html+='<div class="mdline">'+mdInlineCode(line)+'</div>'}
  closeList()}
 return html||'<div class="mdline"></div>'}
async function attachCharts(body, markers){
 if(!body||!markers||!markers.length)return;
 for(const m of markers){
  if(!m||!m.kind)continue;
  const box=document.createElement('div');
  box.className='chartbox';
  box.textContent='📊 চার্ট আঁকছি…';
  body.appendChild(box);
  let url='/api/chart?kind='+encodeURIComponent(m.kind);
  if(m.kind==='concept'&&m.subject)url+='&subject='+encodeURIComponent(m.subject);
  try{
   const r=await fetch(url,{headers:{'X-PIN':pin()}});
   const j=await r.json().catch(()=>null);
   if(r.ok&&j&&j.ok&&j.svg){box.innerHTML=j.svg}
   else{box.textContent=(j&&j.error)?j.error:'চার্ট আনা গেল না — এই মুহূর্তে ডেটা নেই বা সার্ভার সাড়া দেয়নি।'}
  }catch(e){
   box.textContent='চার্ট আনা গেল না — সংযোগে সমস্যা হয়েছে, একটু পরে আবার চেষ্টা করো।'}
 }
 if(typeof scrollChatToBottom==='function')scrollChatToBottom();
}

function renderFinalBody(d,full){
 const body=d.querySelector('.msg-body');if(!body)return;
 // #47: extract [[CHART:...]] markers BEFORE markdown rendering
 const chartMarkers=[]; // #47
 const chartRe=/\[\[CHART:([^\]]+)\]\]/g; // #47
 let cleaned=String(full==null?'':full).replace(chartRe,function(_m,inner){ // #47
  inner=String(inner).trim(); // #47
  if(inner.indexOf('concept:')===0)chartMarkers.push({kind:'concept',subject:inner.slice('concept:'.length).trim()}); // #47
  else if(inner)chartMarkers.push({kind:inner}); // #47
  return ''}); // #47
 cleaned=cleaned.replace(/\n{3,}/g,'\n\n'); // #47: collapse the gap the marker left
 if(d.classList.contains('sokhi')){body.innerHTML=renderMarkdown(cleaned);body.classList.add('md')}
 else body.textContent=cleaned;
 if(d.classList.contains('sokhi')&&chartMarkers.length)attachCharts(body,chartMarkers); // #47
 const act=d.querySelector('.msg-actions');
 if(act){const old=act.querySelector('.foldbtn');if(old)old.remove()}
 body.classList.remove('folded');
 if(cleaned&&cleaned.length>700&&act){
  body.classList.add('folded');
  const fb=document.createElement('button');fb.type='button';fb.className='foldbtn';fb.textContent='আরও দেখাও';
  fb.onclick=e=>{e.stopPropagation();const nowFolded=body.classList.toggle('folded');fb.textContent=nowFolded?'আরও দেখাও':'কম দেখাও';if(!nowFolded)scrollChatToBottom()};
  act.appendChild(fb)}
 refreshRegenButtons()}
function startReveal(d,full){
 finishReveal();
 const body=d.querySelector('.msg-body');if(!body)return;
 body.classList.remove('md','folded');body.style.whiteSpace='pre-wrap';body.textContent='';
 const state={msgEl:d,full:full,pos:0,done:false,raf:0};
 const disp=String(full).replace(/\[\[CHART:[^\]]*\]\]/g,''); // #47: reveal-এ মার্কার দেখাবে না
 activeReveal=state;updateStopBtn();
 const step=()=>{
  if(state.done)return;
  const inc=Math.max(3,Math.ceil(disp.length/70));
  state.pos=Math.min(disp.length,state.pos+inc);
  body.textContent=disp.slice(0,state.pos);
  if(chatDistFromBottom()<=180)scrollChatToBottom();
  if(state.pos<disp.length)state.raf=requestAnimationFrame(step);
  else completeReveal(state)};
 state.raf=requestAnimationFrame(step)}
function completeReveal(state){
 if(!state||state.done)return;
 state.done=true;cancelAnimationFrame(state.raf);
 if(activeReveal===state)activeReveal=null;
 const body=state.msgEl.querySelector('.msg-body');if(body)body.style.whiteSpace='';
 renderFinalBody(state.msgEl,state.full);
 updateStopBtn()}
function finishReveal(){if(activeReveal)completeReveal(activeReveal)}
async function copyText(txt,btn){
 let ok=false;
 try{await navigator.clipboard.writeText(txt);ok=true}
 catch(e){
  try{const ta=document.createElement('textarea');ta.value=txt;ta.style.position='fixed';ta.style.opacity='0';document.body.appendChild(ta);ta.select();ok=document.execCommand('copy');ta.remove()}catch(e2){}}
 if(btn){const old=btn.textContent;btn.textContent=ok?'✓ কপি হয়েছে':'কপি হয়নি';setTimeout(()=>{btn.textContent=old},1400)}
 return ok}
function mkActBtn(label,title,fn){
 const b=document.createElement('button');b.type='button';b.textContent=label;if(title)b.title=title;
 b.onclick=e=>{e.stopPropagation();fn(b)};return b}
function buildMeActions(d,act){
 act.appendChild(mkActBtn('📋','কপি করো',b=>copyText(d._full,b)));
 act.appendChild(mkActBtn('✏️','বদলে আবার পাঠাও',()=>startEdit(d)));
 act.appendChild(mkActBtn('📌','Pin করো',b=>{if(window.fe3PinMessage)window.fe3PinMessage(d,b)}))}
function buildSokhiActions(d,act){
 act.appendChild(mkActBtn('📋','কপি করো',b=>copyText(d._full,b)));
 act.appendChild(mkActBtn('👍','ভালো লেগেছে',b=>rateMsg(d,'up',b)));
 act.querySelectorAll('button')[1].classList.add('ratebtn');
 const dn=mkActBtn('👎','ভালো লাগেনি',b=>rateMsg(d,'down',b));dn.classList.add('ratebtn');act.appendChild(dn);
 act.appendChild(mkActBtn('📌 নোটে রাখো','নোটে রাখো',b=>saveToNote(d,b)));
 act.appendChild(mkActBtn('📌','Pin করো',b=>{if(window.fe3PinMessage)window.fe3PinMessage(d,b)}))}
function refreshRegenButtons(){
 document.querySelectorAll('#chat .regenbtn').forEach(b=>b.remove());
 const msgs=[...document.querySelectorAll('#chat .msg.sokhi')].filter(m=>!m.dataset.err);
 const last=msgs[msgs.length-1];if(!last)return;
 const act=last.querySelector('.msg-actions');if(!act)return;
 const b=document.createElement('button');b.type='button';b.className='regenbtn';b.textContent='↻ আবার উত্তর দাও';
 b.onclick=e=>{e.stopPropagation();regenerate(b)};
 act.appendChild(b)}
async function regenerate(btn){
 const msgs=[...document.querySelectorAll('#chat .msg.sokhi')].filter(m=>!m.dataset.err);
 const last=msgs[msgs.length-1];if(!last)return;
 if(btn){btn.disabled=true;btn.textContent='ভাবছি…'}
 updateStopBtn();
 try{
  const j=await api('/api/chat',{regenerate:true});
  if(j&&typeof j.reply==='string'&&j.reply){
   last._full=j.reply;
   const tsEl=last.querySelector('.ts');if(tsEl)tsEl.textContent=fmtTs();
   if(btn){btn.disabled=false;btn.textContent='↻ আবার উত্তর দাও'}
   startReveal(last,j.reply);
   showSuggestions(j.reply)}
  else{if(btn){btn.disabled=false;btn.textContent='↻ আবার উত্তর দাও'}setStatus('নতুন উত্তর পাইনি — আবার চেষ্টা করো')}}
 catch(e){if(btn){btn.disabled=false;btn.textContent='↻ আবার উত্তর দাও'}setStatus('নতুন উত্তর আনা গেল না')}
 updateStopBtn()}
async function rateMsg(d,rating,btn){
 try{await api('/api/feedback',{rating:rating,text:d._full})}catch(e){}
 d.querySelectorAll('.ratebtn').forEach(b=>b.classList.remove('rated'));
 if(btn)btn.classList.add('rated');
 setStatus(rating==='up'?'ধন্যবাদ! 👍 তোমার পছন্দ মনে রাখলাম':'ধন্যবাদ 👎 — আরও ভালো উত্তর দেওয়ার চেষ্টা করব')}
async function saveToNote(d,btn){
 try{
  let cur='';
  try{const j=await apiGet('/api/notes');
   if(j&&typeof j.text==='string')cur=j.text;
   else if(Array.isArray(j))cur=j.map(n=>typeof n==='string'?n:(n.text||'')).join('\n');
   else if(j&&Array.isArray(j.notes))cur=j.notes.map(n=>typeof n==='string'?n:(n.text||'')).join('\n')}catch(e){}
  const combined=(cur&&cur.trim()?cur.replace(/\s+$/,'')+'\n\n':'')+d._full;
  await api('/api/notes',{text:combined});
  if(btn){const old=btn.textContent;btn.textContent='✓ নোটে রাখা হয়েছে';setTimeout(()=>{btn.textContent=old},1500)}
  const pane=document.getElementById('pane-notes');if(pane&&pane.classList.contains('on'))loadNotes()}
 catch(e){setStatus('নোটে রাখা গেল না — আবার চেষ্টা করো')}}
function startEdit(d){
 const idx=parseInt(d.dataset.idx,10);
 const el=document.getElementById('text');if(!el)return;
 el.value=d._full||'';pendingEditIdx=isNaN(idx)?null:idx;
 autoGrowText();el.focus();
 setStatus('✏️ বার্তাটা বদলে পাঠাও — পাঠালেই এই জায়গা থেকে নতুন করে কথোপকথন শুরু হবে')}
function showThinking(){
 hideThinking();stopRequested=false;setMood('thinking');
 const c=document.getElementById('chat');if(!c)return;
 const d=document.createElement('div');d.className='msg sokhi thinking';
 const av=document.createElement('span');av.className='avatar';av.textContent='স';d.appendChild(av);
 const main=document.createElement('div');main.className='msg-main';
 const body=document.createElement('div');body.className='msg-body';
 body.innerHTML='Sokhi ভাবছি<span class="thinkdots"><span>.</span><span>.</span><span>.</span></span> (<span class="thinksec">০</span> সে.)';
 main.appendChild(body);d.appendChild(main);
 thinkingEl=d;c.appendChild(d);scrollChatToBottom();
 thinkingStart=Date.now();
 thinkingTimer=setInterval(()=>{
  if(!thinkingEl)return;
  const s=Math.floor((Date.now()-thinkingStart)/1000);
  const sp=thinkingEl.querySelector('.thinksec');if(sp)sp.textContent=bnDigits(s)},500);
 updateStopBtn()}
function hideThinking(){
 if(thinkingTimer){clearInterval(thinkingTimer);thinkingTimer=null}
 if(thinkingEl){thinkingEl.remove();thinkingEl=null}
 if(!speakingNow)setMood('calm');
 updateStopBtn()}
function anythingActive(){return !!thinkingEl||!!activeReveal||speakingNow}
function updateStopBtn(){const b=document.getElementById('stopbtn');if(b)b.style.display=anythingActive()?'':'none'}
function stopAll(){
 stopRequested=true;finishReveal();
 try{stopSpeak()}catch(e){}
 hideThinking();updateStopBtn()}
function updateScrollBtn(){const b=document.getElementById('scrollbtn');if(b)b.style.display=chatDistFromBottom()>160?'':'none'}
const SUGG_POOL=['আজকের খবর দাও','আবহাওয়া কেমন?','কী কী মনে রেখেছ?','আমাকে গণিত শেখাও','তোমার স্কিলগুলো কী কী?','প্যাটার্ন বিশ্লেষণ করো','সিস্টেমের অবস্থা দেখাও','তোমার ভার্সন কত?'];
function showSuggestions(reply){
 const box=document.getElementById('suggest');if(!box)return;
 box.innerHTML='';
 const r=String(reply||'');const picks=[];
 if(/পরীক্ষা|মক টেস্ট|mock/i.test(r))picks.push('একটা মক টেস্ট দাও');
 else if(/খবর|সংবাদ/.test(r))picks.push('আরও খবর দাও');
 else if(/আবহাওয়া|বৃষ্টি|তাপমাত্রা/.test(r))picks.push('আবহাওয়া কেমন?');
 else if(/গণিত|অঙ্ক|শেখাও|পড়া/.test(r))picks.push('আরেকটা উদাহরণ দাও');
 else if(/মনে রেখেছ|স্মৃতি/.test(r))picks.push('কী কী মনে রেখেছ?');
 let guard=0;
 while(picks.length<3&&guard<24){const cand=SUGG_POOL[suggRotate%SUGG_POOL.length];suggRotate++;guard++;if(!picks.includes(cand))picks.push(cand)}
 picks.slice(0,3).forEach(p=>{
  const b=document.createElement('button');b.type='button';b.className='chip';b.textContent=p;
  b.onclick=()=>quick(p);box.appendChild(b)})}
function clearSuggestions(){const box=document.getElementById('suggest');if(box)box.innerHTML=''}
function resolveSpeak(speakIt){
 if(speakIt!==undefined)return !!speakIt;
 try{return localStorage.getItem('sokhi_autospeak')==='1'}catch(e){return false}}
function maybeSpeak(reply,origText,speakIt){
 if(!resolveSpeak(speakIt))return;
 if(window.sokhiQuietNow&&window.sokhiQuietNow()){setStatus('🔇 এখন quiet hours — তাই গলায় বললাম না');return}
 speak(reply,moodRate(origText||''))}
function addErrorBubble(){
 const d=add('উত্তর আনতে পারলাম না — নেট বা key-র সমস্যা হতে পারে।','sokhi',{instant:true,err:true});
 if(d){
  const act=d.querySelector('.msg-actions');
  if(act){const b=document.createElement('button');b.type='button';b.textContent='আবার চেষ্টা';
   b.onclick=async e=>{e.stopPropagation();d.remove();if(lastFailedText)await fetchReply(lastFailedText,undefined)};
   act.appendChild(b)}}
 refreshRegenButtons()}
async function fetchReply(t,speakIt){
 showThinking();
 const body={message:t};
 if(window.pendingImageData){body.image=window.pendingImageData;window.pendingImageData=null}
 let j=null;
 try{j=await api('/api/chat',body)}catch(e){j=null}
 hideThinking();
 if(!j||typeof j.reply!=='string'){
  lastFailedText=t;addErrorBubble();return}
 const reply=j.reply;
 if(stopRequested){stopRequested=false;add(reply,'sokhi',{instant:true});showSuggestions(reply);return}
 add(reply,'sokhi',{reveal:true});
 if(window.v14TaskDetect)window.v14TaskDetect(t); /* v1.4 #75 */
 maybeSpeak(reply,t,speakIt);
 showSuggestions(reply)}
function autoGrowText(){
 const el=document.getElementById('text');if(!el||el.tagName!=='TEXTAREA')return;
 el.style.height='auto';el.style.height=Math.min(el.scrollHeight,132)+'px'}
function addReplyInternal(t,ts){return add(t,'sokhi',{ts:ts,reveal:true})}
window.SokhiChat={
 clear(){
  finishReveal();hideThinking();clearSuggestions();
  const c=document.getElementById('chat');if(c)c.innerHTML='';
  msgSeq=0;pendingEditIdx=null;lastFailedText=''},
 loadMessages(msgs){
  window.SokhiChat.clear();
  (msgs||[]).forEach((m,i)=>{
   if(!m)return;
   const role=m.who||m.role||m.sender||'sokhi';
   const text=(m.text!=null?m.text:(m.content!=null?m.content:(m.message!=null?m.message:m.reply)));
   if(text==null)return;
   const ts=(m.ts!=null?m.ts:(m.timestamp!=null?m.timestamp:(m.time!=null?m.time:m.created_at)));
   const who=(role==='me'||role==='user')?'me':'sokhi';
   add(String(text),who,{ts:ts,idx:i,instant:true})});
  scrollChatToBottom()},
 addUser(t,ts){return add(t,'me',{ts:ts})},
 addReply(t,ts){return add(t,'sokhi',{ts:ts,reveal:true})}};
(function initFe1(){
 const chatEl=document.getElementById('chat');
 if(chatEl){
  chatEl.addEventListener('scroll',updateScrollBtn);
  chatEl.addEventListener('click',e=>{
   const cb=e.target.closest('.codecopy');
   if(cb){e.stopPropagation();const pre=cb.parentElement?cb.parentElement.querySelector('code'):null;if(pre)copyText(pre.textContent,cb)}})}
 const el=document.getElementById('text');
 if(el){
  el.addEventListener('keydown',e=>{
   if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}
   else if(e.key==='ArrowUp'&&el.value===''&&el.selectionStart===0){
    const mine=document.querySelectorAll('#chat .msg.me');
    if(mine.length){e.preventDefault();startEdit(mine[mine.length-1])}}});
  el.addEventListener('input',autoGrowText);el.addEventListener('input',function(){if(speakingNow)try{stopSpeak()}catch(e){}})} /* v1.4 #113 barge-in: লিখতে শুরু করলেই বলা থামবে */
 document.addEventListener('keydown',e=>{
  if((e.ctrlKey||e.metaKey)&&(e.key==='k'||e.key==='K')){e.preventDefault();const t2=document.getElementById('text');if(t2)t2.focus()}
  else if(e.key==='Escape'){stopAll()}});
 setInterval(()=>{updateStopBtn();updateScrollBtn()},600)})();
function toggleExamForm(){const f=document.getElementById('examform');f.style.display=f.style.display==='block'?'none':'block'}
async function startExam(){
 const subject=document.getElementById('examsubject').value;
 const count=parseInt(document.getElementById('examcount').value,10)||10;
 const minutes=parseInt(document.getElementById('examminutes').value,10)||10;
 try{const j=await api('/api/exam',{action:'start',subject:subject,count:count,minutes:minutes});
  examActive=true;examEndAt=Date.now()+minutes*60000;
  document.getElementById('examform').style.display='none';
  document.getElementById('examchip').style.display='flex';
  showTab('chat');
  add('📝 মক টেস্ট শুরু হলো — বিষয়: '+subject+', প্রশ্ন: '+count+'টা, সময়: '+minutes+' মিনিট। উত্তর লিখে পাঠাও।','sokhi');
  if(j&&j.reply)add(j.reply,'sokhi');
  if(j&&j.question)add(j.question,'sokhi');
  clearInterval(examTimerId);
  examTimerId=setInterval(tickExam,500);tickExam();
 }catch(e){add('মক টেস্ট শুরু করা গেল না — আবার চেষ্টা করো।','sokhi')}}
function tickExam(){
 const left=Math.max(0,examEndAt-Date.now());
 const s=Math.ceil(left/1000),mm=String(Math.floor(s/60)).padStart(2,'0'),ss=String(s%60).padStart(2,'0');
 document.getElementById('examtimer').textContent='⏳ '+mm+':'+ss;
 if(left<=0&&examActive)finishExam()}
function endExamUi(){examActive=false;clearInterval(examTimerId);document.getElementById('examchip').style.display='none'}
async function finishExam(){
 if(!examActive)return;
 endExamUi();
 try{const j=await api('/api/exam',{action:'finish'});
  add('✅ মক টেস্ট শেষ হলো।','sokhi');
  if(j&&j.reply)add(j.reply,'sokhi');
  if(j&&j.result)add(String(j.result),'sokhi');
 }catch(e){}}
async function saveKey(){
 const k=document.getElementById('apikey').value.trim();
 if(!k){document.getElementById('keymsg').textContent='ঘর ফাঁকা ছিল আগের key-ই থাকল, কিছু বদলাইনি।';return}
 const j=await api('/api/settings',{gemini_api_key:k});
 document.getElementById('apikey').value='';
 document.getElementById('keymsg').textContent=j.key_set?'সেভ হয়ে গেছে! এবার টেস্ট করো বোতাম চাপো।':'সেভ হয়নি — আবার চেষ্টা করো।';
 document.getElementById('keystat').textContent=j.key_set?'✅ key বসানো আছে — স্মার্ট মাথা চালু':'❌ key বসানো নেই — অফলাইন মাথায় চলছে';}
async function saveCall(){
 const v=document.getElementById('callname').value.trim();
 await api('/api/settings',{call_name:v});
 alert(v?('এখন থেকে Sokhi তোমাকে "'+v+'" বলে ডাকবে'):'এখন থেকে Sokhi কোনো নামে ডাকবে না');}
async function saveTone(){
 const v=document.getElementById('tonepreset').value;
 await api('/api/settings',{tts_preset:v});edgeOk=null;
 document.getElementById('voicestat').textContent='টোন বদলেছে: '+v+' — টেস্ট করে শোনো';}
function voiceRateInput(){
 const el=document.getElementById('voicerate');if(!el)return;
 const v=parseFloat(el.value)||1;window.voiceRate=v;
 const lbl=document.getElementById('voicerateval');if(lbl)lbl.textContent=v.toFixed(2)+'×'}
async function saveVoiceRate(){
 const el=document.getElementById('voicerate');if(!el)return;
 const v=parseFloat(el.value)||1;window.voiceRate=v;
 const lbl=document.getElementById('voicerateval');if(lbl)lbl.textContent=v.toFixed(2)+'×';
 try{await api('/api/settings',{voice_rate:v})}catch(e){}}
async function saveUrl(){
 const v=document.getElementById('updateurl').value.trim();
 const j=await api('/api/settings',{update_url:v});
 document.getElementById('ghstat').textContent=j.update_url_set?'✅ ঠিকানা বসানো আছে — এখন চ্যাটে "আপগ্রেড চেক করো" বললেই GitHub থেকে যাচাই হবে':'ঠিকানা মোছা হয়েছে';}
async function clearKey(){
 if(!confirm('key মুছে ফেলবে?'))return;
 const j=await api('/api/settings',{clear_key:true});
 document.getElementById('keymsg').textContent='key মুছে ফেলা হয়েছে।';
 document.getElementById('keystat').textContent='❌ key বসানো নেই — অফলাইন মাথায় চলছে';}
async function testVoice(){
 document.getElementById('voicestat').textContent='গলা টেস্ট হচ্ছে…';
 const j=await api('/api/tts_test',{});
 if(j.ok){document.getElementById('voicestat').textContent='ভালো গলা চলছে: '+j.engine;const ve2=document.getElementById('voiceengine');if(ve2&&j.engine)ve2.textContent='গলা: '+j.engine;speak('আসসালামু আলাইকুম, আমি সখী। আমার গলা এখন এমন শোনাবে।')}
 else{document.getElementById('voicestat').textContent='❌ ভালো গলা আসেনি — ব্রাউজারের গলা চলবে। কারণ: '+j.error}}
async function testKey(){
 document.getElementById('keymsg').textContent='টেস্ট হচ্ছে… একটু অপেক্ষা করো';
 const j=await api('/api/testkey',{});
 document.getElementById('keymsg').textContent=j.message;}
function mic(){
 try{stopSpeak()}catch(e){} /* v1.4 #113 barge-in: মাইক শুরু হলেই বলা থামবে */
 const R=window.SpeechRecognition||window.webkitSpeechRecognition;
 if(!R){alert('এই ব্রাউজারে গলা-শোনা নেই Chrome ব্যবহার করো');return}
 const r=new R();r.lang='bn-BD';r.onresult=e=>{const _et=e.results[0][0].transcript;if(isEchoOfSpeech(_et)){setStatus('🔇 নিজের কণ্ঠ ফেলে দেওয়া হলো');return}document.getElementById('text').value=_et;send(true)};r.start()}

/* ---------- panels: weather + news (5 min) ---------- */
let lastWeather='';
async function pollPanels(){
 try{const j=await apiGet('/api/panels');
  if(j.weather_text){document.getElementById('weather').textContent=j.weather_text;lastWeather=j.weather_text}
  if(j.news_text)document.getElementById('news').textContent=j.news_text;
 }catch(e){}}
/* ---------- agents (8 s) + Visual Hub ---------- */
const seenDone={};
async function pollAgents(){
 let j;try{j=await apiGet('/api/agents')}catch(e){return}
 const jobs=(j&&j.jobs)||[];
 const list=document.getElementById('agentlist');
 if(!jobs.length){list.innerHTML='';const d=document.createElement('div');d.className='small';d.textContent='কোনো agent কাজ নেই।';list.appendChild(d)}
 else{
  list.innerHTML='';
  for(const job of jobs){
   const card=document.createElement('div');card.className='agentcard';
   const head=document.createElement('div');
   head.textContent='🤖 '+(job.agent||'agent')+' — '+(job.title||job.id||'');
   card.appendChild(head);
   const st=document.createElement('div');st.className='st';
   const steps=job.steps||[],done=job.done_steps||0;
   st.textContent='অবস্থা: '+(job.status||'')+' • ধাপ '+done+'/'+steps.length;
   card.appendChild(st);
   steps.forEach((s,i)=>{
    const sd=document.createElement('div');sd.className='step';
    sd.textContent=(i<done?'✔ ':'… ')+s;card.appendChild(sd)});
   if(job.result){const rd=document.createElement('div');rd.className='step';rd.textContent='ফল: '+job.result;card.appendChild(rd)}
   list.appendChild(card)}}
 const running=jobs.filter(x=>x.status&&x.status!=='done'&&x.status!=='failed');
 const hub=document.getElementById('hubsteps');
 if(running.length){
  hub.textContent=running.map(job=>{
   const steps=job.steps||[],done=job.done_steps||0;
   const bar='['+'█'.repeat(done)+'░'.repeat(Math.max(0,steps.length-done))+']';
   return '◆ '+(job.title||job.agent||job.id)+'\n  '+bar+' '+done+'/'+steps.length+' ধাপ\n'+steps.map((s,i)=>'  '+(i<done?'✔':'…')+' '+s).join('\n')}).join('\n\n')}
 else{hub.textContent='এখন কোনো কাজ চলছে না।'}
 for(const job of jobs){
  if((job.status==='done'||job.status==='failed')&&job.id&&!seenDone[job.id]){
   seenDone[job.id]=1;
   add('🤖 '+(job.agent||'Agent')+'-এর কাজ শেষ: '+(job.title||'')+(job.result?('\n'+job.result):''),'sokhi');
   try{await api('/api/agents',{action:'ack',id:job.id})}catch(e){}}}}
/* ---------- notes ---------- */
async function loadNotes(){
 try{const j=await apiGet('/api/notes');
  const items=Array.isArray(j)?j:(j.notes||[]);
  const box=document.getElementById('noteslist');box.innerHTML='';
  items.forEach(n=>{
   const d=document.createElement('div');d.className='listitem';
   d.textContent=(typeof n==='string')?n:(n.text||JSON.stringify(n));box.appendChild(d)});
 }catch(e){}}
async function saveNote(){
 const t=document.getElementById('notetext').value.trim();if(!t)return;
 try{await api('/api/notes',{text:t});document.getElementById('notetext').value='';loadNotes()}catch(e){}}
/* ---------- tasks ---------- */
async function loadTasks(){
 try{const j=await apiGet('/api/tasks');
  const items=(j&&j.tasks)||[];
  const box=document.getElementById('tasklist');box.innerHTML='';
  items.forEach(n=>{
   const d=document.createElement('div');d.className='listitem';
   const done=n&&(n.done||n.status==='done');
   d.textContent=(done?'✅ ':'⬜ ')+((typeof n==='string')?n:(n.text||JSON.stringify(n)));box.appendChild(d)});
 }catch(e){}}
async function addTask(){
 const t=document.getElementById('newtask').value.trim();if(!t)return;
 try{await api('/api/tasks',{text:t});document.getElementById('newtask').value='';loadTasks()}catch(e){}}
/* ---------- whiteboard ---------- */
async function pollBoard(){
 try{const j=await apiGet('/api/whiteboard');
  const lines=(j&&j.lines)||[];
  document.getElementById('board').textContent=lines.length?lines.join('\n'):'বোর্ড খালি।';
 }catch(e){}}
async function clearBoard(){
 try{await api('/api/whiteboard',{action:'clear'});document.getElementById('board').textContent='বোর্ড খালি।'}catch(e){}}
/* ---------- rules (N13) ---------- */
async function loadRules(){
 try{const j=await apiGet('/api/rules');
  document.getElementById('ruleslist').textContent=(j&&j.text)?j.text:'এখনো কোনো নিয়ম নেই।';
 }catch(e){document.getElementById('ruleslist').textContent='নিয়ম লোড করা গেল না।'}}
async function addRule(){
 const el=document.getElementById('newrule');const v=el.value.trim();if(!v)return;
 try{await api('/api/rules',{rule:v});el.value='';loadRules()}catch(e){}}
/* ---------- particle character ---------- */
let moodName='calm';
const MOODS={calm:null,listening:'#2effa8',thinking:'#b06cf0',speaking:'#ffffff'};
let moodColor='#22b8f0';
function themeAccent(){
 const cs=getComputedStyle(document.body);
 return (cs.getPropertyValue('--accent')||'#22b8f0').trim()||'#22b8f0'}
function drawMoodBase(){if(moodName==='calm')moodColor=themeAccent()}
function setMood(name){
 moodName=name;
 moodColor=(name==='calm')?themeAccent():(MOODS[name]||themeAccent())}
const P_COUNT=900;
const particles=[];
(function initParticles(){
 const cx=140,headCy=92,headR=52;
 for(let i=0;i<P_COUNT;i++){
  const r=Math.random();
  let tx,ty,zone;
  if(r<0.38){ /* head: filled circle */
   const a=Math.random()*Math.PI*2,rad=headR*Math.sqrt(Math.random());
   tx=cx+Math.cos(a)*rad;ty=headCy+Math.sin(a)*rad*1.12;zone='head'}
  else if(r<0.78){ /* shoulders: wide ellipse arc below head */
   const a=Math.PI*(0.05+Math.random()*0.9),rad=46+Math.random()*52;
   tx=cx+Math.cos(a)*rad*1.55;ty=196+Math.sin(a)*rad*0.52-58;zone='body';
   if(ty<140)ty=140+Math.random()*20}
  else{ /* soft outer halo ring */
   const a=Math.random()*Math.PI*2,rad=104+Math.random()*26;
   tx=cx+Math.cos(a)*rad;ty=140+Math.sin(a)*rad*1.08;zone='halo'}
  const mouth=(Math.abs(tx-(cx+2))<17&&Math.abs(ty-(headCy+24))<8);
  particles.push({tx:tx,ty:ty,x:cx+(Math.random()-0.5)*260,y:140+(Math.random()-0.5)*260,
   s:0.8+Math.random()*1.7,ph:Math.random()*Math.PI*2,zone:zone,mouth:mouth})}})();
function hexRgb(h){h=h.replace('#','');if(h.length===3)h=h.split('').map(c=>c+c).join('');const n=parseInt(h,16);return [n>>16&255,n>>8&255,n&255]}
function tickParticles(ts){
 const cv=document.getElementById('pcanvas');if(!cv)return;
 const ctx=cv.getContext('2d');if(!ctx)return;
 const t=ts/1000;
 const breath=1+Math.sin(t*1.4)*0.022;
 const cx=140,cy=140;
 ctx.clearRect(0,0,cv.width,cv.height);
 const rgb=hexRgb(moodColor);
 for(const p of particles){
  let tx=cx+(p.tx-cx)*breath,ty=cy+(p.ty-cy)*breath;
  if(speakingNow){
   if(p.mouth){ty+=Math.sin(t*22+p.ph)*3.2;tx+=Math.sin(t*17+p.ph)*1.6}
   else if(p.zone==='head'){tx+=Math.sin(t*9+p.ph)*0.7;ty+=Math.cos(t*11+p.ph)*0.7}}
  p.x+=(tx-p.x)*0.06;p.y+=(ty-p.y)*0.06;
  const tw=0.55+0.45*Math.sin(t*2.2+p.ph);
  const bright=speakingNow?1:0.8;
  ctx.beginPath();
  ctx.fillStyle='rgba('+rgb[0]+','+rgb[1]+','+rgb[2]+','+(0.35+0.6*tw*bright).toFixed(3)+')';
  ctx.arc(p.x,p.y,p.s*(speakingNow&&p.mouth?1.5:1),0,Math.PI*2);
  ctx.fill()}
 requestAnimationFrame(tickParticles)}
requestAnimationFrame(tickParticles);
setMood('calm');
/* ---------- idle screen (90 s) ---------- */
let idleTimer=null;
function armIdle(){clearTimeout(idleTimer);idleTimer=setTimeout(showIdle,90000)}
function showIdle(){
 const ov=document.getElementById('idle');ov.style.display='block';
 const now=new Date();
 document.getElementById('idleclock').textContent=now.toLocaleTimeString('bn-BD',{hour:'2-digit',minute:'2-digit'});
 try{document.getElementById('idledate').textContent=now.toLocaleDateString('bn-BD',{weekday:'long',day:'numeric',month:'long',year:'numeric'})}catch(e){document.getElementById('idledate').textContent=now.toDateString()}
 document.getElementById('idlewx').textContent=lastWeather||'';
 setTimeout(()=>{if(ov.style.display==='block')showIdle()},20000)}
function hideIdle(){document.getElementById('idle').style.display='none';armIdle()}
for(const ev of ['click','keydown','mousemove','touchstart']){
 window.addEventListener(ev,()=>{if(document.getElementById('idle').style.display==='block')hideIdle();else armIdle()},{passive:true})}
armIdle();
/* ---------- boot / status (v0.5 behaviour) ---------- */
(async()=>{
 if(!pin()){document.getElementById('pinbox').style.display='block';return}
 try{const s=await api('/api/status');document.getElementById('main').style.display='block';
 document.getElementById('status').textContent='ভার্সন v'+s.version+' • স্কিল '+s.skills+'টা • কথা হয়েছে '+s.interactions+' বার • সম্পূর্ণ ফ্রি';
 document.getElementById('skillsnode').textContent='Skills '+s.skills+'টা';
 document.getElementById('keystat').textContent=s.key_set?'✅ key বসানো আছে — স্মার্ট মাথা চালু':'❌ key বসানো নেই — অফলাইন মাথায় চলছে';
 document.getElementById('voicestat').textContent=s.voice_engine?('ভালো গলা চলছে: '+s.voice_engine):(s.voice_edge?'ভালো গলা বসানো আছে — টেস্ট করে দেখো':'ভালো গলার টুল এখনো বসেনি — Sokhi আবার চালালে পেছনে বসবে; টেস্ট বোতামে আসল গলা যাচাই হবে');
 const ve=document.getElementById('voiceengine');if(ve)ve.textContent=s.voice_engine?('গলা: '+s.voice_engine):'';
 if(s.voice_rate!=null){const vr=parseFloat(s.voice_rate);if(!isNaN(vr)){window.voiceRate=vr;const vel=document.getElementById('voicerate');if(vel)vel.value=vr;const vlbl=document.getElementById('voicerateval');if(vlbl)vlbl.textContent=vr.toFixed(2)+'×'}}
 document.getElementById('callname').value=s.call_name||'';
 document.getElementById('tonepreset').value=s.tts_preset||'মিষ্টি';
 if(s.update_url)document.getElementById('updateurl').value=s.update_url;
 document.getElementById('ghstat').textContent=s.update_url_set?'✅ GitHub ঠিকানা বসানো আছে':'❌ এখনো বসানো হয়নি — Saba-র গাইড দেখে বসাও';
 document.getElementById('orb').onclick=()=>{if(speakingNow)stopSpeak()};
 document.getElementById('autostat').textContent=(s.auto_upgrade?'✅ চালু আছে':'❌ বন্ধ আছে')+' • শেখা উত্তর: '+s.knowledge+'টা • প্রতিদিন নিজে নিজে একটু করে ভালো হয়';
 document.getElementById('status').textContent+=' • শেখা উত্তর '+s.knowledge+'টা';
 const hh=new Date().getHours();const greet=hh<5?'অনেক রাত হয়েছে':hh<12?'শুভ সকাল':hh<17?'শুভ দুপুর':hh<20?'শুভ বিকেল':'শুভ সন্ধ্যা';
 const care=hh<12?'নাশতা হয়েছে তো?':hh<17?'দুপুরের খাবারটা ঠিকমতো খেয়ে নিয়ো।':hh<22?'পড়া কেমন চলছে?':'রাত জাগবে না বেশি, ঘুমও দরকার।';
 add('আসসালামু আলাইকুম'+(s.call_name?' '+s.call_name:'')+'! '+greet+'। আমি Sokhi — তোমার ল্যাপটপেই আছি। '+care+' গলায় বললে গলায় উত্তর দেব, লিখলে লিখে উত্তর দেব।','sokhi');
 pollPanels();setInterval(pollPanels,300000);
 pollAgents();setInterval(pollAgents,8000);
 pollBoard();setInterval(pollBoard,8000);
 loadTasks();loadNotes();
 }catch(e){}})();
speechSynthesis && speechSynthesis.getVoices();
</script>
<style>
/* v1.2 fe2 — কথোপকথন-বার, স্মৃতি ট্যাব, আরাম ও সাহায্য (worker-2) */
:root{--fs:1}
body{font-size:calc(15px * var(--fs,1))}
.msg{font-size:calc(15px * var(--fs,1))}
body[data-theme="soft"]{--accent:#86b8a8;--accent2:#4f7f70;--deep:#1e332d;--bg:#141917;--panel:#1c2320;--panel2:#242e2a;--line:#33423c;--txt:#e7edea;--muted:#a9bab2}
#convowrap{flex:none;margin-bottom:10px;position:relative}
#convobar{display:flex;align-items:center;gap:6px;flex-wrap:wrap;background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:8px 10px;box-shadow:var(--shadow)}
#convobar .ttl{flex:1;min-width:120px;font-size:13.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#convobar button{font-size:12.5px;padding:6px 10px;flex:none}
#convopanel{margin-top:6px;background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:10px;box-shadow:var(--shadow);max-height:330px;display:flex;flex-direction:column}
#convopanel[hidden]{display:none}
#convosearch{width:100%;flex:none;margin-bottom:8px}
#convolist{overflow-y:auto;min-height:0}
.convoitem{display:flex;gap:6px;align-items:center;padding:8px 6px;border-bottom:1px solid var(--line);cursor:pointer;border-radius:6px}
.convoitem:hover,.convoitem.active{background:var(--panel2)}
.convoitem .info{flex:1;min-width:0}
.convoitem .t{font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.convoitem .m{font-size:12px;color:var(--muted);white-space:pre-wrap}
.convoitem button{flex:none;padding:4px 7px;font-size:12px}
#pane-memory{overflow:hidden}
#fe2memscroll{overflow-y:auto;min-height:0;flex:1;padding-right:4px}
.fe2memrow{display:flex;gap:6px;align-items:flex-start;padding:7px 0;border-bottom:1px solid var(--line);font-size:14px}
.fe2memrow span{flex:1;min-width:0;white-space:pre-wrap}
.fe2memrow button{flex:none;padding:3px 8px;font-size:12px}
#brainbadge{display:inline-block;margin-top:4px;margin-left:8px;font-size:12px;padding:3px 10px;border-radius:999px;background:var(--panel2);border:1px solid var(--line);color:var(--muted);vertical-align:middle}
#focusbtn{position:fixed;top:10px;right:62px;width:42px;height:42px;border-radius:50%;font-size:17px;padding:0;z-index:50;box-shadow:var(--shadow)}
#focusbtn.on{border-color:var(--accent);background:var(--accent2);color:#fff}
body.focus #leftcol,body.focus #centercol{display:none!important}
body.focus #layout{grid-template-columns:minmax(0,1fr);max-width:980px}
#imgchip{display:flex;gap:8px;align-items:center;width:fit-content;max-width:calc(100% - 32px);margin:0 auto 6px;padding:6px 12px;background:var(--panel2);border:1px solid var(--line);border-radius:999px;font-size:13px}
#imgchip button{padding:2px 8px;font-size:12px;flex:none}
#cmdpalette{flex:none;width:100%;max-width:820px;margin:0 auto 6px;padding:6px;background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);max-height:264px;overflow-y:auto;z-index:45}
#cmdpalette[hidden]{display:none}
.cmditem{padding:9px 12px;cursor:pointer;font-size:14px;border-radius:6px}
.cmditem.sel{background:var(--accent2);color:#fff}
.fe2modal{display:none;position:fixed;inset:0;background:rgba(2,4,10,.72);z-index:80;overflow:hidden}
.fe2modal .panel{max-width:480px;max-height:calc(100vh - 48px);overflow-y:auto;min-height:0;margin:24px auto;background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:24px;box-shadow:var(--shadow)}
.fe2modal .panel h3{margin:0 0 12px;font-size:16px;font-weight:600}
.fe2modal hr{border:none;border-top:1px solid var(--line);margin:16px 0}
.fe2modal ul{margin:6px 0 6px 18px;padding:0;font-size:14px;line-height:1.7}
#fe2onboard{z-index:120}
#fe2helpbtn{position:fixed;left:12px;bottom:84px;width:44px;height:44px;border-radius:50%;font-size:18px;font-weight:700;padding:0;z-index:55;box-shadow:var(--shadow)}
#fe2settings input[type="checkbox"]{flex:none;width:auto;padding:0}
#fe2settings input[type="time"]{flex:none;width:auto}
#fe2settings select{max-width:100%}
#fe2attachbtn{flex:none}
/* v1.3 fe3 — পিন ট্যাব, সেটিংসের বাড়তি ঘর */
#pane-pins{overflow:hidden}
#fe3pinscroll{overflow-y:auto;min-height:0;flex:1;padding-right:4px}
.fe3pinrow{display:flex;gap:6px;align-items:flex-start;padding:7px 0;border-bottom:1px solid var(--line);font-size:14px}
.fe3pinrow .tx{flex:1;min-width:0;white-space:pre-wrap;word-break:break-word}
.fe3pinrow .tx .m{font-size:12px;color:var(--muted);margin-top:2px;white-space:pre-wrap}
.fe3pinrow button{flex:none;padding:3px 8px;font-size:12px}
#fe2settings input[type="checkbox"]{flex:none}
.fe3filelabel{cursor:pointer;border:1px solid var(--line);background:var(--panel2);border-radius:8px;padding:6px 10px;font-size:13px;display:inline-flex;align-items:center}
/* v1.2 fe2 — মোবাইল আরাম (আইডিয়া ৪১) */
@media (max-width:1080px){
 .tabs{flex-wrap:nowrap;overflow-x:auto;overflow-y:hidden;padding-bottom:4px;-webkit-overflow-scrolling:touch}
 .tabs button{flex:none;min-height:44px;padding:10px 16px}
 #bar{gap:6px;padding:0 8px 10px}
 #bar button{min-width:48px;min-height:48px;padding:10px 12px}
 #bar input{min-height:48px}
 #convobar button{min-height:44px;padding:10px 14px}
 .convoitem{padding:12px 8px}
 .convoitem button{min-width:40px;min-height:40px}
 #gear,#focusbtn{width:48px;height:48px}
 #focusbtn{right:70px}
 #fe2helpbtn{width:48px;height:48px;bottom:76px}
 .cmditem{padding:13px 12px}
 .fe2memrow button{min-width:40px;min-height:36px}
}

</style>
<script>
/* v1.2 fe2 — worker-2: কথোপকথন (১৫–২১), স্মৃতি (২২–২৪), আরাম/সাহায্য (২৫–৪১) */
/* আইডিয়া ৩২: mic() পুনর্সংজ্ঞা — এই appended script-এর ঘোষণা আগেরটিকে বদলে দেয়।
   interimResults=true: বলতে বলতেই আংশিক লেখা composer-এ দেখা যাবে, final এলে send(true)। */
function mic(){
 try{stopSpeak()}catch(e){} /* v1.4 #113 barge-in: মাইক শুরু হলেই বলা থামবে */
 const R=window.SpeechRecognition||window.webkitSpeechRecognition;
 if(!R){alert('এই ব্রাউজারে গলা-শোনা নেই — Chrome ব্যবহার করো');return}
 const r=new R();r.lang='bn-BD';r.interimResults=true;r.continuous=false;
 const el=document.getElementById('text');
 r.onresult=function(e){
  let interim='',finalTxt='';
  for(let i=0;i<e.results.length;i++){
   const res=e.results[i];
   if(res.isFinal)finalTxt+=res[0].transcript;else interim+=res[0].transcript}
  if(el)el.value=finalTxt||interim;
  if(finalTxt){if(isEchoOfSpeech(finalTxt)){if(el)el.value='';setStatus('🔇 নিজের কণ্ঠ ফেলে দেওয়া হলো')}else send(true)}};
 try{r.start()}catch(err){}}
(function(){
'use strict';
const $=function(id){return document.getElementById(id)};
window.pendingImageData=window.pendingImageData||null;
/* ---------- বার্তার আকার বোঝা (BE/FE-1-এর নানা ফরম্যাট সহনশীল) ---------- */
function msgText(m){
 if(m==null)return '';
 if(typeof m==='string')return m;
 return String(m.t!=null?m.t:(m.text||m.content||m.message||m.reply||''))}
function msgWho(m){
 if(m&&typeof m==='object'){
  const w=String(m.r||m.who||m.role||m.sender||m.type||'');
  if(w==='me'||w==='user'||w==='human')return 'me'}
 return 'sokhi'}
function msgTs(m){
 if(m&&typeof m==='object'){const v=m.ts!=null?m.ts:(m.time||m.timestamp||m.created||'');return typeof v==='number'?fmtDate(v):String(v)}
 return ''}
function normalizeMsgs(msgs){
 return (msgs||[]).map(function(m){
  if(typeof m==='string')return {who:'sokhi',text:m};
  return {who:msgWho(m),text:msgText(m),ts:(m&&typeof m==='object')?(m.ts!=null?m.ts:(m.timestamp!=null?m.timestamp:m.time)):undefined}}).filter(function(m){return m.text})}
/* FE-1 window.SokhiChat দেবে; না থাকলে add()-ভিত্তিক নিরাপদ fallback (একই আচরণ)। */
if(!window.SokhiChat){
 window.SokhiChat={
  clear:function(){const c=$('chat');if(c)c.innerHTML=''},
  loadMessages:function(msgs){(msgs||[]).forEach(function(m){const t=msgText(m);if(t&&typeof add==='function')add(t,msgWho(m))})},
  addUser:function(t){if(typeof add==='function')add(t,'me')},
  addReply:function(t){if(typeof add==='function')add(t,'sokhi')}}}
function convoMsgs(j){
 if(!j)return [];
 if(Array.isArray(j.messages))return j.messages;
 if(j.conversation&&Array.isArray(j.conversation.messages))return j.conversation.messages;
 if(j.convo&&Array.isArray(j.convo.messages))return j.convo.messages;
 return []}
function fmtDate(v){
 if(v==null||v==='')return '';
 let d=null;
 if(typeof v==='number')d=new Date(v<1e12?v*1000:v);
 else{const p=Date.parse(v);if(!isNaN(p))d=new Date(p)}
 if(d){try{return d.toLocaleDateString('bn-BD')+' '+d.toLocaleTimeString('bn-BD',{hour:'2-digit',minute:'2-digit'})}catch(e){return d.toLocaleString()}}
 return String(v)}
/* ================= ১৫–২১: কথোপকথন-বার ================= */
let activeId=null,activeTitle='';
function setConvoTitle(t){activeTitle=t||'';const el=$('convotitle');if(el)el.textContent=activeTitle||'নতুন কথোপকথন'}
async function convoPost(body){return await api('/api/convos',body)}
function renderConvoList(items){
 const box=$('convolist');if(!box)return;box.innerHTML='';
 if(!items||!items.length){const d=document.createElement('div');d.className='small';d.textContent='কোনো কথোপকথন পাওয়া যায়নি।';box.appendChild(d);return}
 items=items.slice().sort(function(a,b){return ((b&&b.pinned)?1:0)-((a&&a.pinned)?1:0)});
 items.forEach(function(raw){
  const it=raw||{};
  const id=it.id||it.convo_id||it.conversation_id||'';
  const title=it.title||it.name||'কথোপকথন';
  const row=document.createElement('div');row.className='convoitem'+(String(id)===String(activeId)?' active':'');
  const info=document.createElement('div');info.className='info';
  const tt=document.createElement('div');tt.className='t';tt.textContent=(it.pinned?'📌 ':'')+title;info.appendChild(tt);
  const meta=document.createElement('div');meta.className='m';
  const bits=[];
  if(it.count!=null)bits.push(it.count+'টি বার্তা');
  else if(it.message_count!=null)bits.push(it.message_count+'টি বার্তা');
  const dt=fmtDate(it.updated||it.updated_at||it.time);if(dt)bits.push(dt);
  meta.textContent=bits.join(' • ');info.appendChild(meta);
  if(it.snippet){const sn=document.createElement('div');sn.className='m';sn.textContent=String(it.snippet);info.appendChild(sn)}
  row.appendChild(info);
  const mk=function(label,titleTxt,fn){const b=document.createElement('button');b.textContent=label;b.title=titleTxt;b.addEventListener('click',function(ev){ev.stopPropagation();fn()});return b};
  row.appendChild(mk('📌',it.pinned?'Pin তোলো':'Pin করো',function(){api('/api/convos',{action:'pin',id:id,pinned:!it.pinned}).then(function(){refreshConvos()}).catch(function(){})}));
  row.appendChild(mk('✏️','নাম বদলাও',function(){renameConvo(id,title)}));
  row.appendChild(mk('⬇','Export (.txt)',function(){exportConvo(id,title)}));
  row.appendChild(mk('🗑','মোছো',function(){deleteConvo(id,title)}));
  row.addEventListener('click',function(){switchConvo(id)});
  box.appendChild(row)})}
async function refreshConvos(){
 try{
  const j=await apiGet('/api/convos');
  const items=(j&&(j.items||j.convos))||[];
  let act=(j&&j.active)||null;
  if(act&&typeof act==='object'){activeId=act.id||activeId;setConvoTitle(act.title||act.name)}
  else if(act!=null){activeId=act}
  if(activeId!=null){const found=items.find(function(x){return String(x.id||x.convo_id||'')===String(activeId)});if(found)setConvoTitle(found.title||found.name)}
  renderConvoList(items);
  return {j:j,items:items}
 }catch(e){return {j:null,items:[]}}}
async function loadActiveIntoChat(){
 /* বুট-ইতিহাস: FE-1-এর SokhiChat.loadMessages() নিজেই প্রথমে clear() করে,
    তাই সরাসরি ডাকলে আগে আসা greeting মুছে যেত। পদ্ধতি: ইতিহাস আনার পর,
    loadMessages ডাকার ঠিক আগে chat-এর বিদ্যমান নোডগুলো (greeting) একটি
    DocumentFragment-এ তুলে রাখি (একই নোড — listener-সহ অক্ষত), তারপর
    loadMessages ইতিহাস বসালে সেই নোডগুলো শেষে আবার append করি।
    ফল: ইতিহাস আগে, greeting শেষে; greeting পরে এলে এমনিতেই শেষে বসে।
    capture→load অংশটা synchronous, তাই মাঝখানে অন্য add() ঢুকতে পারে না। */
 const info=await refreshConvos();
 let msgs=[];
 try{const g=await convoPost(activeId!=null?{action:'get',id:activeId}:{action:'get'});msgs=convoMsgs(g);
  if(g&&(g.title||g.name))setConvoTitle(g.title||g.name)}catch(e){}
 if(!msgs.length)return;
 const chatEl=$('chat');if(!chatEl)return;
 const norm=normalizeMsgs(msgs);
 const holder=document.createDocumentFragment();
 Array.prototype.slice.call(chatEl.children).forEach(function(n){holder.appendChild(n)});
 if(window.SokhiChat&&typeof window.SokhiChat.loadMessages==='function')window.SokhiChat.loadMessages(norm);
 else norm.forEach(function(m){add(m.text,m.who)});
 if(holder.childNodes.length)chatEl.appendChild(holder);
 if(typeof scrollChatToBottom==='function')scrollChatToBottom()}
async function switchConvo(id){
 if(id==null||id==='')return;
 try{
  await convoPost({action:'switch',id:id});
  activeId=id;
  const g=await convoPost({action:'get',id:id});
  const msgs=convoMsgs(g);
  if(window.SokhiChat){window.SokhiChat.clear();window.SokhiChat.loadMessages(normalizeMsgs(msgs))}
  if(g&&(g.title||g.name))setConvoTitle(g.title||g.name);
  const p=$('convopanel');if(p)p.hidden=true;
  refreshConvos();
 }catch(e){add('কথোপকথন বদলানো গেল না — আবার চেষ্টা করো।','sokhi')}}
async function newConvo(){
 try{
  const j=await convoPost({action:'create'});
  if(j&&(j.id||(j.item&&j.item.id))){activeId=j.id||j.item.id;setConvoTitle(j.title||(j.item&&j.item.title)||'নতুন কথোপকথন')}
  else setConvoTitle('নতুন কথোপকথন');
  if(window.SokhiChat)window.SokhiChat.clear();
  const p=$('convopanel');if(p)p.hidden=true;
  refreshConvos();
 }catch(e){add('নতুন কথোপকথন তৈরি করা গেল না — আবার চেষ্টা করো।','sokhi')}}
function renameConvo(id,title){
 const nt=prompt('কথোপকথনের নতুন নাম লেখো',title||'');
 if(nt==null||!nt.trim())return;
 convoPost({action:'rename',id:id,title:nt.trim()}).then(function(){if(String(id)===String(activeId))setConvoTitle(nt.trim());refreshConvos()}).catch(function(){})}
function deleteConvo(id,title){
 if(!confirm('"'+(title||'কথোপকথন')+'" মুছে ফেলবে?'))return;
 const wasActive=String(id)===String(activeId);
 convoPost({action:'delete',id:id}).then(async function(){
  if(wasActive){if(window.SokhiChat)window.SokhiChat.clear();activeId=null;setConvoTitle('');await loadActiveIntoChat()}
  else refreshConvos()}).catch(function(){})}
async function exportConvo(id,title){
 try{
  const g=await convoPost({action:'get',id:id});
  const msgs=convoMsgs(g);
  const lines=[(title||g.title||'Sokhi কথোপকথন'),''];
  msgs.forEach(function(m){const t=msgText(m);if(!t)return;const ts=msgTs(m);lines.push((msgWho(m)==='me'?'আমি':'Sokhi')+(ts?' ('+ts+')':'')+': '+t)});
  const blob=new Blob([lines.join('\n')],{type:'text/plain;charset=utf-8'});
  const url=URL.createObjectURL(blob);
  const a=document.createElement('a');a.href=url;
  a.download=String(title||g.title||'sokhi-chat').replace(/[\\/:*?"<>|]+/g,' ').trim().slice(0,60)+'.txt';
  document.body.appendChild(a);a.click();a.remove();
  setTimeout(function(){URL.revokeObjectURL(url)},2000);
 }catch(e){alert('Export করা গেল না — আবার চেষ্টা করো।')}}
let searchTimer=null;
function onConvoSearch(){
 const q=($('convosearch')?$('convosearch').value:'').trim();
 clearTimeout(searchTimer);
 if(!q){refreshConvos();return}
 searchTimer=setTimeout(async function(){
  try{const j=await convoPost({action:'search',q:q});
   renderConvoList((j&&(j.items||j.results||j.matches))||[])}
  catch(e){}},260)}
function buildConvoBar(){
 const right=$('rightcol');if(!right)return;
 const wrap=document.createElement('div');wrap.id='convowrap';
 const bar=document.createElement('div');bar.id='convobar';
 const ttl=document.createElement('span');ttl.className='ttl';ttl.innerHTML='💬 কথোপকথন: <b id="convotitle">…</b>';bar.appendChild(ttl);
 const bNew=document.createElement('button');bNew.textContent='নতুন';bNew.addEventListener('click',newConvo);bar.appendChild(bNew);
 const bList=document.createElement('button');bList.textContent='তালিকা ▾';
 const panel=document.createElement('div');panel.id='convopanel';panel.hidden=true;
 bList.addEventListener('click',function(){panel.hidden=!panel.hidden;if(!panel.hidden)refreshConvos()});bar.appendChild(bList);
 const bClear=document.createElement('button');bClear.textContent='পরিষ্কার';
 bClear.addEventListener('click',function(){
  if(!confirm('বর্তমান কথোপকথনের সব বার্তা পরিষ্কার করবে?'))return;
  convoPost(activeId!=null?{action:'clear',id:activeId}:{action:'clear'}).catch(function(){});
  if(window.SokhiChat)window.SokhiChat.clear()});bar.appendChild(bClear);
 wrap.appendChild(bar);
 const search=document.createElement('input');search.id='convosearch';search.type='text';search.placeholder='কথোপকথন খোঁজো… (শিরোনাম বা বার্তা)';
 search.addEventListener('input',onConvoSearch);panel.appendChild(search);
 const list=document.createElement('div');list.id='convolist';panel.appendChild(list);
 wrap.appendChild(panel);
 const tabs=right.querySelector('.tabs');
 if(tabs)right.insertBefore(wrap,tabs);else right.insertBefore(wrap,right.firstChild)}
/* ================= ২২–২৪: স্মৃতি ট্যাব ================= */
function memItemText(n){
 if(typeof n==='string')return n;
 if(n&&typeof n==='object')return String(n.text||n.fact||n.note||n.value||JSON.stringify(n));
 return String(n||'')}
function renderMemList(box,items,kind){
 if(!box)return;box.innerHTML='';
 if(!items||!items.length){const d=document.createElement('div');d.className='small';d.textContent='কিছু নেই।';box.appendChild(d);return}
 items.forEach(function(n,idx){
  const row=document.createElement('div');row.className='fe2memrow';
  const s=document.createElement('span');s.textContent=memItemText(n);row.appendChild(s);
  const b=document.createElement('button');b.textContent='✕';b.title='মোছো';
  b.addEventListener('click',function(){deleteMemory(kind,idx)});row.appendChild(b);
  box.appendChild(row)})}
async function loadMemory(){
 try{
  const j=await apiGet('/api/memory');
  renderMemList($('fe2facts'),(j&&j.facts)||[],'fact');
  renderMemList($('fe2notes'),(j&&(j.learned_notes||j.learnedNotes))||[],'note');
  const msg=$('fe2memmsg');if(msg)msg.textContent='';
 }catch(e){const msg=$('fe2memmsg');if(msg)msg.textContent='স্মৃতি লোড করা গেল না।'}}
async function deleteMemory(kind,idx){
 try{await api('/api/memory',kind==='fact'?{action:'delete_fact',index:idx}:{action:'delete_note',index:idx})}catch(e){}
 loadMemory()}
function fe2Tab(name){
 if(name==='pins'){
  ['chat','agents','notes','tasks'].forEach(function(n){
   const p=$('pane-'+n);if(p)p.classList.remove('on');
   const b=$('tabbtn-'+n);if(b)b.classList.remove('on')});
  const mp=$('pane-memory');if(mp)mp.classList.remove('on');
  const mb=$('tabbtn-memory');if(mb)mb.classList.remove('on');
  const p=$('pane-pins');if(p)p.classList.add('on');
  const b=$('tabbtn-pins');if(b)b.classList.add('on');
  loadPins();return}
 if(name==='memory'){
  ['chat','agents','notes','tasks'].forEach(function(n){
   const p=$('pane-'+n);if(p)p.classList.remove('on');
   const b=$('tabbtn-'+n);if(b)b.classList.remove('on')});
  const pp=$('pane-pins');if(pp)pp.classList.remove('on');
  const pb=$('tabbtn-pins');if(pb)pb.classList.remove('on');
  const p=$('pane-memory');if(p)p.classList.add('on');
  const b=$('tabbtn-memory');if(b)b.classList.add('on');
  loadMemory();return}
 const p=$('pane-memory');if(p)p.classList.remove('on');
 const b=$('tabbtn-memory');if(b)b.classList.remove('on');
 const pp=$('pane-pins');if(pp)pp.classList.remove('on');
 const pb=$('tabbtn-pins');if(pb)pb.classList.remove('on');
 if(typeof showTab==='function')showTab(name)}
window.fe2Tab=fe2Tab;
function buildMemoryPane(){
 const right=$('rightcol');if(!right)return;
 const tabs=right.querySelector('.tabs');
 if(tabs){const b=document.createElement('button');b.id='tabbtn-memory';b.textContent='স্মৃতি';b.addEventListener('click',function(){fe2Tab('memory')});tabs.appendChild(b)}
 ['chat','agents','notes','tasks'].forEach(function(n){
  const b=$('tabbtn-'+n);if(!b)return;
  b.addEventListener('click',function(){const p=$('pane-memory');if(p)p.classList.remove('on');const mb=$('tabbtn-memory');if(mb)mb.classList.remove('on')})});
 const pane=document.createElement('div');pane.className='tabpane';pane.id='pane-memory';
 const scroll=document.createElement('div');scroll.id='fe2memscroll';
 const head=document.createElement('div');head.style.cssText='display:flex;gap:6px;align-items:center;margin-bottom:8px';
 const h=document.createElement('div');h.className='secttl';h.style.flex='1';h.textContent='Sokhi যা মনে রেখেছে';head.appendChild(h);
 const rb=document.createElement('button');rb.textContent='🔄 রিফ্রেশ';rb.style.fontSize='13px';rb.addEventListener('click',loadMemory);head.appendChild(rb);
 scroll.appendChild(head);
 const msg=document.createElement('div');msg.id='fe2memmsg';msg.className='small';scroll.appendChild(msg);
 const ft=document.createElement('div');ft.className='secttl';ft.textContent='মনে রাখা তথ্য';scroll.appendChild(ft);
 const facts=document.createElement('div');facts.id='fe2facts';scroll.appendChild(facts);
 const nt=document.createElement('div');nt.className='secttl';nt.style.marginTop='14px';nt.textContent='শেখা নোট';scroll.appendChild(nt);
 const notes=document.createElement('div');notes.id='fe2notes';scroll.appendChild(notes);
 const addRow=document.createElement('div');addRow.style.cssText='display:flex;gap:6px;margin-top:14px';
 const inp=document.createElement('input');inp.id='fe2newfact';inp.type='text';inp.placeholder='নতুন তথ্য লেখো…';inp.style.flex='1';addRow.appendChild(inp);
 const ab=document.createElement('button');ab.textContent='যোগ করো';
 ab.addEventListener('click',async function(){
  const v=inp.value.trim();if(!v)return;
  try{await api('/api/memory',{action:'add_fact',text:v});inp.value='';loadMemory()}
  catch(e){const m=$('fe2memmsg');if(m)m.textContent='তথ্য যোগ করা গেল না।'}});
 addRow.appendChild(ab);scroll.appendChild(addRow);
 pane.appendChild(scroll);
 const chatPane=$('pane-chat');
 if(chatPane&&chatPane.parentNode===right)right.insertBefore(pane,chatPane.nextSibling);
 else right.appendChild(pane)}
/* ================= ২৫, ২৬, ৩৩, ৩৬: সেটিংসের নতুন বিভাগ ================= */
function applyFont(v,save){
 const n=Math.min(1.25,Math.max(0.9,parseFloat(v)||1));
 document.documentElement.style.setProperty('--fs',String(n));
 const lbl=$('fe2fontval');if(lbl)lbl.textContent=n.toFixed(2)+'×';
 const sl=$('fe2font');if(sl)sl.value=n;
 if(save){try{localStorage.setItem('sokhi_fontscale',String(n))}catch(e){}}}
function quietMirror(){
 try{return JSON.parse(localStorage.getItem('sokhi_quiet')||'{}')}catch(e){return {}}}
window.sokhiQuietNow=function(){
 const q=quietMirror();
 const en=q.enabled!=null?q.enabled:!!(q.quiet_start&&q.quiet_end);
 if(!en)return false;
 const s=q.quiet_start||q.start||'',e=q.quiet_end||q.end||'';
 if(!s||!e||s===e)return false;
 const now=new Date(),cur=now.getHours()*60+now.getMinutes();
 const sm=parseInt(s.split(':')[0],10)*60+(parseInt(s.split(':')[1],10)||0);
 const em=parseInt(e.split(':')[0],10)*60+(parseInt(e.split(':')[1],10)||0);
 if(sm<em)return cur>=sm&&cur<em;
 return cur>=sm||cur<em};
async function saveQuiet(){
 const on=$('fe2quieton')?$('fe2quieton').checked:false;
 const s=on&&$('fe2quietstart')?$('fe2quietstart').value:'';
 const e=on&&$('fe2quietend')?$('fe2quietend').value:'';
 const sv=$('fe2quietstart')?$('fe2quietstart').value:'';
 const ev=$('fe2quietend')?$('fe2quietend').value:'';
 try{localStorage.setItem('sokhi_quiet',JSON.stringify({enabled:on,quiet_start:sv,quiet_end:ev,start:sv,end:ev}))}catch(err){}
 try{await api('/api/settings',{quiet_start:s,quiet_end:e})}catch(err){}}
function buildSettingsExtras(){
 const panel=document.querySelector('#modal .panel');if(!panel)return;
 /* ২৭: soft থিম বোতাম — বিদ্যমান themebtns সারিতে */
 const tb=panel.querySelector('.themebtns');
 if(tb){const sb=document.createElement('button');sb.textContent='নরম (চোখের আরাম)';sb.addEventListener('click',function(){if(typeof setTheme==='function')setTheme('soft')});tb.appendChild(sb)}
 const closeBtn=Array.prototype.slice.call(panel.querySelectorAll('button')).find(function(b){return b.textContent.trim()==='বন্ধ করো'});
 const box=document.createElement('div');box.id='fe2settings';
 box.innerHTML=
  '<hr><div class="secttl">উত্তরের ধরন</div>'+
  '<div style="font-size:13px;margin-top:6px">কতটা লম্বা উত্তর চাও: '+
  '<select id="fe2replystyle"><option value="সংক্ষেপ">সংক্ষেপ</option><option value="স্বাভাবিক">স্বাভাবিক</option><option value="বিস্তারিত">বিস্তারিত</option></select></div>'+
  '<hr><div class="secttl">অক্ষরের আকার (চোখের আরাম)</div>'+
  '<div style="display:flex;align-items:center;gap:8px;margin-top:6px"><span class="small">ছোট</span>'+
  '<input id="fe2font" type="range" min="0.9" max="1.25" step="0.05" value="1" style="flex:1">'+
  '<span class="small">বড়</span><span id="fe2fontval" class="small">1.00×</span></div>'+
  '<hr><div class="secttl">গলায় উত্তর (Auto-speak)</div>'+
  '<label style="font-size:13px;display:flex;gap:8px;align-items:center;margin-top:6px"><input id="fe2autospeak" type="checkbox"> লিখে পাঠালেও উত্তরের গলা শোনাও</label>'+
  '<div class="hint">ডিফল্ট বন্ধ — চালু করলে লিখে পাঠানো প্রশ্নের উত্তরও গলায় শুনবে।</div>'+
  '<hr><div class="secttl">শান্ত সময় (Quiet hours)</div>'+
  '<label style="font-size:13px;display:flex;gap:8px;align-items:center;margin-top:6px"><input id="fe2quieton" type="checkbox"> শান্ত সময় চালু</label>'+
  '<div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-top:8px;font-size:13px">শুরু <input id="fe2quietstart" type="time" value="22:00"> শেষ <input id="fe2quietend" type="time" value="07:00"> <button id="fe2quietsave" type="button">সেভ</button></div>'+
  '<div class="hint">এই সময়ে Sokhi নিজে থেকে গলায় বলবে না — ঘুম/নামাজের সময় বিঘ্ন হবে না।</div>'+
  '<hr><div class="secttl">উত্তরের ভাষা</div>'+
  '<div style="font-size:13px;margin-top:6px">উত্তরের ভাষা: '+
  '<select id="fe3lang"><option value="বাংলা">বাংলা</option><option value="Banglish">Banglish</option><option value="English">English</option></select></div>'+
  '<div class="hint">Smart (Gemini) উত্তরের ভাষা বদলাবে; অফলাইন উত্তর আপাতত বাংলাতেই থাকে।</div>'+
  '<hr><div class="secttl">Wake word</div>'+
  '<label style="font-size:13px;display:flex;gap:8px;align-items:center;margin-top:6px"><input id="fe3wake" type="checkbox"> নাম ধরে ডাকলে জাগবে ("সখি" / "Sokhi")</label>'+
  '<div class="hint">Chrome-এ মাইকের অনুমতি লাগবে, ট্যাব খোলা থাকতে হবে; শুনতে পেলেই লাইভ মোড চালু হবে।</div>'+
  '<hr><div class="secttl">নিজের কণ্ঠ চেনা (Echo guard)</div>'+
  '<label style="font-size:13px;display:flex;gap:8px;align-items:center;margin-top:6px"><input id="fe3echoguard" type="checkbox" checked> 🔇 নিজের কণ্ঠ চেনা (echo guard)</label>'+
  '<div class="hint">চালু থাকলে স্পিকার থেকে Sokhi-র নিজের বলা কথা মাইকে ফিরে এলেও তা ইনপুট হবে না — লাইভ মোডে Sokhi নিজে নিজেকে উত্তর দেবে না। আসল বাধা (barge-in) আগের মতোই চলবে। হেডফোন ছাড়া লাইভ চালালে চালু রাখাই ভালো।</div>'+
  '<hr><div class="secttl">রাতের Auto-dim</div>'+
  '<label style="font-size:13px;display:flex;gap:8px;align-items:center;margin-top:6px"><input id="fe3dimon" type="checkbox"> রাতে স্ক্রিন নিজে থেকে ম্লান হবে</label>'+
  '<div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-top:8px;font-size:13px">শুরু <input id="fe3dimstart" type="time" value="21:00"> শেষ <input id="fe3dimend" type="time" value="06:00"></div>'+
  '<div style="display:flex;align-items:center;gap:8px;margin-top:8px"><span class="small">ম্লান</span>'+
  '<input id="fe3dimlevel" type="range" min="0.3" max="1" step="0.05" value="0.6" style="flex:1">'+
  '<span class="small">উজ্জ্বল</span><span id="fe3dimlevelval" class="small">৬০%</span></div>'+
  '<div style="margin-top:8px"><button id="fe3dimsave" type="button">সেভ</button></div>'+
  '<div class="hint">বসানো সময়ে স্ক্রিনের উজ্জ্বলতা নিজে থেকে কমে যাবে — রাতে চোখের আরাম।</div>'+
  '<hr><div class="secttl">ব্যাকআপ / রিস্টোর / Sync</div>'+
  '<div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:8px;align-items:center"><button id="fe3backupdl" type="button">⬇ ব্যাকআপ নাও (.json)</button>'+
  '<button id="fe3syncdl" type="button">🔄 Sync ফাইল নাও</button>'+
  '<label class="fe3filelabel" for="fe3restorefile">⬆ রিস্টোর করো</label>'+
  '<input id="fe3restorefile" type="file" accept=".json,application/json" style="display:none"></div>'+
  '<div id="fe3backupmsg" class="small" style="margin-top:6px"></div>'+
  '<div class="hint">ব্যাকআপ ফাইলে Gemini key থাকে না। Sync ফাইল একই — অন্য ডিভাইসে (ফোন/ল্যাপটপ) এই ফাইল রিস্টোর করলেই কথোপকথন ও স্মৃতি মিলে যাবে; cloud-এ নিজে থেকে sync হয় না। একই Wi-Fi-তে ফোন থেকে খুললে এমনিতেই একই তথ্য দেখা যায়।</div>';
 if(closeBtn)panel.insertBefore(box,closeBtn);else panel.appendChild(box);
 const rs=$('fe2replystyle');
 if(rs)rs.addEventListener('change',function(){api('/api/settings',{reply_style:rs.value}).catch(function(){})});
 const fs=$('fe2font');
 if(fs)fs.addEventListener('input',function(){applyFont(fs.value,true)});
 try{const savedFs=localStorage.getItem('sokhi_fontscale');if(savedFs)applyFont(savedFs,false)}catch(e){}
 const as=$('fe2autospeak');
 if(as){try{as.checked=localStorage.getItem('sokhi_autospeak')==='1'}catch(e){}
  as.addEventListener('change',function(){try{localStorage.setItem('sokhi_autospeak',as.checked?'1':'0')}catch(e){}})}
 try{const q=quietMirror();
  if(q&&(q.quiet_start||q.start)){const qi=$('fe2quieton');if(qi)qi.checked=q.enabled!=null?!!q.enabled:true;
   const qs=$('fe2quietstart');if(qs)qs.value=q.quiet_start||q.start;
   const qe=$('fe2quietend');if(qe)qe.value=q.quiet_end||q.end||''}
 }catch(e){}
 const qb=$('fe2quietsave');if(qb)qb.addEventListener('click',saveQuiet);
 const qo=$('fe2quieton');if(qo)qo.addEventListener('change',saveQuiet);
 /* v1.3 fe3: ভাষা / wake word / auto-dim / ব্যাকআপের তারজোড় */
 const lg=$('fe3lang');
 if(lg)lg.addEventListener('change',function(){api('/api/settings',{reply_language:lg.value}).catch(function(){})});
 const wk=$('fe3wake');
 if(wk){try{wk.checked=localStorage.getItem('sokhi_wake')==='1'}catch(e){}
  wk.addEventListener('change',function(){fe3SetWake(wk.checked)})}
 const eg=$('fe3echoguard');
 if(eg){eg.checked=echoGuardOn;eg.addEventListener('change',function(){fe3SetEchoGuard(eg.checked)})}
 try{const dm=fe3DimMirror();
  if(dm&&(dm.start||dm.end||dm.level!=null||dm.enabled!=null)){
   const don=$('fe3dimon');if(don)don.checked=!!dm.enabled;
   const ds=$('fe3dimstart');if(ds&&dm.start)ds.value=dm.start;
   const de=$('fe3dimend');if(de&&dm.end)de.value=dm.end;
   const dl=$('fe3dimlevel');if(dl&&dm.level!=null)dl.value=dm.level}
 }catch(e){}
 fe3DimLevelLabel();
 const dlv=$('fe3dimlevel');if(dlv)dlv.addEventListener('input',fe3DimLevelLabel);
 const dsv=$('fe3dimsave');if(dsv)dsv.addEventListener('click',saveDim);
 const bk=$('fe3backupdl');if(bk)bk.addEventListener('click',function(){fe3ExportBackup('backup')});
 const sy=$('fe3syncdl');if(sy)sy.addEventListener('click',function(){fe3ExportBackup('sync')});
 const rf=$('fe3restorefile');if(rf)rf.addEventListener('change',function(){if(rf.files&&rf.files[0])fe3ImportBackup(rf.files[0]);rf.value=''})}
/* ================= ২৮: Focus মোড ================= */
function toggleFocus(){
 const on=document.body.classList.toggle('focus');
 const b=$('focusbtn');if(b)b.classList.toggle('on',on);
 try{localStorage.setItem('sokhi_focus',on?'1':'0')}catch(e){}}
window.fe2ToggleFocus=toggleFocus;
function buildFocusButton(){
 const b=document.createElement('button');b.id='focusbtn';b.title='ফোকাস মোড — শুধু চ্যাট বড় করে';b.textContent='⛶';
 b.addEventListener('click',toggleFocus);document.body.appendChild(b);
 try{if(localStorage.getItem('sokhi_focus')==='1'){document.body.classList.add('focus');b.classList.add('on')}}catch(e){}}
/* ================= ৩৫: Brain badge ================= */
function setBrain(txt){const b=$('brainbadge');if(b)b.textContent=txt}
async function updateBrain(){
 if(!navigator.onLine){setBrain('📴 নেট নেই');return}
 try{
  const s=await apiGet('/api/status');
  if(s){
   if(s.reply_style){const rs=$('fe2replystyle');if(rs&&Array.prototype.slice.call(rs.options).some(function(o){return o.value===s.reply_style}))rs.value=s.reply_style}
   if(s.quiet_start||s.quiet_end){
    const qs=$('fe2quietstart');if(qs&&s.quiet_start)qs.value=s.quiet_start;
    const qe=$('fe2quietend');if(qe&&s.quiet_end)qe.value=s.quiet_end;
    const qo=$('fe2quieton');if(qo)qo.checked=!!(s.quiet_start&&s.quiet_end);
    try{localStorage.setItem('sokhi_quiet',JSON.stringify({enabled:!!(s.quiet_start&&s.quiet_end),quiet_start:s.quiet_start||'',quiet_end:s.quiet_end||'',start:s.quiet_start||'',end:s.quiet_end||''}))}catch(e){}}
   if(s.reply_language){const lg=$('fe3lang');if(lg&&Array.prototype.slice.call(lg.options).some(function(o){return o.value===s.reply_language}))lg.value=s.reply_language}
   if(s.wake_word!=null){const wk2=$('fe3wake');if(wk2)wk2.checked=!!s.wake_word;wakeOn=!!s.wake_word;try{localStorage.setItem('sokhi_wake',wakeOn?'1':'0')}catch(e){}if(wakeOn)setTimeout(startWake,1200)}
   if(s.echo_guard!=null){echoGuardOn=!!s.echo_guard;try{localStorage.setItem('sokhi_echoguard',echoGuardOn?'1':'0')}catch(e){}const eg3=$('fe3echoguard');if(eg3)eg3.checked=echoGuardOn}
   if(s.dim_start||s.dim_end||s.dim_level!=null){
    const dm2={enabled:!!(s.dim_start&&s.dim_end),start:s.dim_start||'21:00',end:s.dim_end||'06:00',level:s.dim_level!=null?parseFloat(s.dim_level):0.6};
    try{localStorage.setItem('sokhi_dim',JSON.stringify(dm2))}catch(e){}
    const don=$('fe3dimon');if(don)don.checked=dm2.enabled;
    const ds=$('fe3dimstart');if(ds&&s.dim_start)ds.value=s.dim_start;
    const de=$('fe3dimend');if(de&&s.dim_end)de.value=s.dim_end;
    const dl=$('fe3dimlevel');if(dl&&s.dim_level!=null)dl.value=s.dim_level;
    fe3DimLevelLabel();applyDim()}
   if(s.brain==='smart')setBrain('🧠 স্মার্ট মাথা');
   else if(s.brain==='offline')setBrain('📴 অফলাইন মাথা');
   else setBrain(s.key_set?'🧠 স্মার্ট মাথা':'📴 অফলাইন মাথা');
   return}
 }catch(e){}
 setBrain('📴 অফলাইন মাথা')}
function buildBrainBadge(){
 const st=$('status');if(!st||!st.parentNode)return;
 const sp=document.createElement('span');sp.id='brainbadge';sp.textContent='… মাথা';
 st.parentNode.insertBefore(sp,st.nextSibling);
 window.addEventListener('online',updateBrain);
 window.addEventListener('offline',function(){setBrain('📴 নেট নেই')});
 updateBrain();setInterval(updateBrain,60000)}
/* ================= ২৯, ৩০: সংযুক্তি (📎 / drag-drop / paste) ================= */
function clearImage(){
 window.pendingImageData=null;
 const c=$('imgchip');if(c)c.remove()}
window.fe2ClearImage=clearImage;
function showImageChip(){
 clearImageChipOnly();
 const bar=$('bar');if(!bar||!bar.parentNode)return;
 const chip=document.createElement('div');chip.id='imgchip';
 const s=document.createElement('span');s.textContent='🖼 ছবি যুক্ত হয়েছে';chip.appendChild(s);
 const b=document.createElement('button');b.textContent='✕';b.title='ছবি বাতিল';
 b.addEventListener('click',clearImage);chip.appendChild(b);
 bar.parentNode.insertBefore(chip,bar)}
function clearImageChipOnly(){const c=$('imgchip');if(c)c.remove()}
function handleFile(file){
 if(!file)return;
 const name=file.name||'';
 if(file.type&&file.type.indexOf('image/')===0){
  const rd=new FileReader();
  rd.onload=function(){window.pendingImageData=String(rd.result||'');showImageChip()};
  rd.readAsDataURL(file);return}
 const isText=/\.(txt|md|csv|json)$/i.test(name)||(file.type&&file.type.indexOf('text/')===0)||file.type==='application/json';
 if(isText){
  const rd=new FileReader();
  rd.onload=function(){
   let content=String(rd.result||'');
   if(content.length>4000)content=content.slice(0,4000);
   const el=$('text');if(el){el.value='[ফাইল: '+name+']\n'+content;el.focus()}};
  rd.readAsText(file);return}
 alert('এই ধরনের ফাইল এখন পড়তে পারি না — .txt/.md/.csv/.json লেখা-ফাইল বা ছবি দাও।')}
function buildAttach(){
 const bar=$('bar');if(!bar)return;
 const btn=document.createElement('button');btn.id='fe2attachbtn';btn.type='button';btn.title='ফাইল বা ছবি যোগ করো';btn.textContent='📎';
 const inp=document.createElement('input');inp.type='file';inp.id='fe2file';inp.accept='.txt,.md,.csv,.json,image/*';inp.style.display='none';
 btn.addEventListener('click',function(){inp.click()});
 inp.addEventListener('change',function(){if(inp.files&&inp.files[0])handleFile(inp.files[0]);inp.value=''});
 bar.insertBefore(btn,bar.firstChild);document.body.appendChild(inp);
 const chatEl=$('chat');
 if(chatEl){
  chatEl.addEventListener('dragover',function(e){e.preventDefault()});
  chatEl.addEventListener('drop',function(e){e.preventDefault();if(e.dataTransfer&&e.dataTransfer.files&&e.dataTransfer.files[0])handleFile(e.dataTransfer.files[0])})}
 window.addEventListener('paste',function(e){
  const files=e.clipboardData&&e.clipboardData.files;
  if(files&&files.length){e.preventDefault();handleFile(files[0])}});
 /* FE-1 send() পাঠানোর সময় pendingImageData খালি করে দেয় — chip-টাও তখন সরিয়ে দিই */
 setInterval(function(){if($('imgchip')&&!window.pendingImageData)clearImageChipOnly()},1000)}
/* ================= ৩১: Command palette ("/") ================= */
const COMMANDS=[
 {label:'নতুন কথোপকথন',key:'new chat',run:function(){newConvo()}},
 {label:'স্মৃতি দেখাও',key:'memory',run:function(){fe2Tab('memory')}},
 {label:'নিয়ম',key:'rules niyom',run:function(){if(typeof openRules==='function')openRules()}},
 {label:'মক টেস্ট',key:'mock test exam',run:function(){if(typeof toggleExamForm==='function')toggleExamForm()}},
 {label:'আপগ্রেড চেক',key:'upgrade check',run:function(){if(typeof quick==='function')quick('আপগ্রেড চেক করো')}},
 {label:'আবহাওয়া',key:'weather',run:function(){if(typeof quick==='function')quick('আবহাওয়া কেমন?')}},
 {label:'খবর',key:'news',run:function(){if(typeof quick==='function')quick('আজকের খবর দাও')}},
 {label:'PC অবস্থা',key:'pc status system',run:function(){if(typeof quick==='function')quick('সিস্টেমের অবস্থা দেখাও')}},
 {label:'ফোকাস মোড',key:'focus',run:function(){toggleFocus()}},
 {label:'সাহায্য',key:'help',run:function(){showHelp()}}];
let palItems=[],palSel=0;
function hidePalette(){const p=$('cmdpalette');if(p)p.hidden=true;palItems=[]}
function renderPalette(){
 const p=$('cmdpalette');if(!p)return;
 if(!palItems.length){p.hidden=true;return}
 p.hidden=false;p.innerHTML='';
 palItems.forEach(function(cmd,idx){
  const d=document.createElement('div');d.className='cmditem'+(idx===palSel?' sel':'');d.textContent='/ '+cmd.label;
  d.addEventListener('click',function(){runCommand(idx)});p.appendChild(d)})}
function runCommand(idx){
 const cmd=palItems[idx];if(!cmd)return;
 hidePalette();
 const el=$('text');if(el)el.value='';
 try{cmd.run()}catch(e){}}
function buildPalette(){
 const bar=$('bar');if(!bar||!bar.parentNode)return;
 const p=document.createElement('div');p.id='cmdpalette';p.hidden=true;
 bar.parentNode.insertBefore(p,bar);
 const el=$('text');if(!el)return;
 el.addEventListener('input',function(){
  const v=el.value;
  if(v.charAt(0)!=='/'){hidePalette();return}
  const q=v.slice(1).trim().toLowerCase();
  palItems=COMMANDS.filter(function(c){return !q||c.label.indexOf(q)>=0||c.key.indexOf(q)>=0});
  palSel=0;renderPalette()});
 document.addEventListener('keydown',function(e){
  if(e.target!==el)return;
  const pal=$('cmdpalette');if(!pal||pal.hidden)return;
  if(e.key==='ArrowDown'){e.preventDefault();e.stopPropagation();e.stopImmediatePropagation();palSel=Math.min(palItems.length-1,palSel+1);renderPalette()}
  else if(e.key==='ArrowUp'){e.preventDefault();e.stopPropagation();e.stopImmediatePropagation();palSel=Math.max(0,palSel-1);renderPalette()}
  else if(e.key==='Enter'){e.preventDefault();e.stopPropagation();e.stopImmediatePropagation();runCommand(palSel)}
  else if(e.key==='Escape'){e.preventDefault();e.stopPropagation();e.stopImmediatePropagation();hidePalette()}},true)}
/* ================= ৩৭, ৩৮: Onboarding + Help ================= */
const ONBOARD_STEPS=[
 {t:'স্বাগতম! আমি Sokhi 👋',b:'আমাকে বাংলায় বা Banglish-এ যা খুশি বলতে পারো। যেমন: "আবহাওয়া কেমন?", "আজকের খবর দাও", "আমাকে গণিত শেখাও", "ইউটিউব খোলো"।'},
 {t:'গলায় বলো, বা লিখে পাঠাও 🎤',b:'মাইক বোতামে চেপে বললেই আমি শুনে গলায় উত্তর দেব — বলতে বলতেই লেখা ঘরে আংশিক লেখা দেখতে পাবে। "লাইভ" চালু করলে শুধু কথা বললেই হবে। লিখে পাঠালে সাধারণত লিখেই উত্তর দিই।'},
 {t:'স্মার্ট মাথার জন্য key বসাও ⚙️',b:'ডানদিকের ওপরের ⚙️ সেটিংসে গিয়ে ফ্রি Gemini key বসালে আমার স্মার্ট মাথা চালু হবে (key শুধু এই ল্যাপটপেই থাকে)। সেটিংস থেকেই গলার টোন, থিম, শান্ত সময় — সব বদলাতে পারবে।'}];
let onboardIdx=0;
function renderOnboard(){
 const body=$('fe2onboardbody'),ttl=$('fe2onboardtitle'),btn=$('fe2onboardnext');
 if(!body||!ONBOARD_STEPS[onboardIdx])return;
 if(ttl)ttl.textContent='ধাপ '+(onboardIdx+1)+'/'+ONBOARD_STEPS.length+' — '+ONBOARD_STEPS[onboardIdx].t;
 body.textContent=ONBOARD_STEPS[onboardIdx].b;
 if(btn)btn.textContent=onboardIdx===ONBOARD_STEPS.length-1?'বুঝেছি, শুরু করি':'পরবর্তী →'}
function showOnboarding(){
 onboardIdx=0;renderOnboard();
 const o=$('fe2onboard');if(o)o.style.display='block'}
window.fe2ShowOnboarding=showOnboarding;
function buildOnboarding(){
 const o=document.createElement('div');o.id='fe2onboard';o.className='fe2modal';
 o.innerHTML='<div class="panel"><h3 id="fe2onboardtitle">স্বাগতম!</h3><div id="fe2onboardbody" style="font-size:14.5px;line-height:1.7;white-space:pre-wrap"></div><div style="text-align:right;margin-top:16px"><button id="fe2onboardnext" type="button">পরবর্তী →</button></div></div>';
 document.body.appendChild(o);
 $('fe2onboardnext').addEventListener('click',function(){
  if(onboardIdx<ONBOARD_STEPS.length-1){onboardIdx++;renderOnboard()}
  else{try{localStorage.setItem('sokhi_onboarded','1')}catch(e){}o.style.display='none'}});
 let seen=false;try{seen=!!localStorage.getItem('sokhi_onboarded')}catch(e){}
 if(!seen)setTimeout(showOnboarding,700)}
function showHelp(){const m=$('fe2helpmodal');if(m)m.style.display='block'}
window.fe2ShowHelp=showHelp;
function buildHelp(){
 const btn=document.createElement('button');btn.id='fe2helpbtn';btn.title='সাহায্য';btn.textContent='?';
 btn.addEventListener('click',showHelp);document.body.appendChild(btn);
 const m=document.createElement('div');m.id='fe2helpmodal';m.className='fe2modal';
 m.innerHTML='<div class="panel"><h3>সাহায্য — কী কী বলা যায়</h3>'+
 '<div class="secttl">বলা যায় এমন বাক্য</div><ul>'+
 '<li>আবহাওয়া কেমন? / আজকের খবর দাও</li>'+
 '<li>আমাকে গণিত শেখাও / মক টেস্ট দাও</li>'+
 '<li>কী কী মনে রেখেছ? / আমার প্যাটার্ন বিশ্লেষণ করো</li>'+
 '<li>সিস্টেমের অবস্থা দেখাও / ইউটিউব খোলো</li>'+
 '<li>আপগ্রেড চেক করো / কতদূর হলো?</li></ul><hr>'+
 '<div class="secttl">Shortcut</div><ul>'+
 '<li>Enter — বার্তা পাঠানো</li>'+
 '<li>/ — কমান্ড মেনু (↑ ↓ দিয়ে বেছে Enter)</li>'+
 '<li>Esc — কমান্ড মেনু বন্ধ</li>'+
 '<li>📎 বোতাম / ফাইল টেনে চ্যাটে ফেলা / paste — ফাইল বা ছবি যোগ</li>'+
 '<li>🎤 — গলায় বলা (বলতে বলতেই লেখা উঠবে)</li></ul><hr>'+
 '<div class="secttl">টিপস</div><ul>'+
 '<li>স্মৃতি ট্যাবে Sokhi কী মনে রেখেছে দেখতে ও মুছতে পারবে।</li>'+
 '<li>কথোপকথন-বার থেকে বিষয় ধরে আলাদা চ্যাট রাখা যায়।</li>'+
 '<li>ফোকাস মোডে (⛶) শুধু চ্যাট বড় হয়ে আসে।</li>'+
 '<li>যেকোনো বার্তার নিচের 📌 চাপ দিলে বার্তাটা পিন ট্যাবে জমা থাকবে; কথোপকথন-তালিকায় 📌 দিয়ে কথোপকথন pin করে ওপরে রাখা যায়।</li>'+
 '<li>সেটিংস থেকে ব্যাকআপ/রিস্টোর ও Sync ফাইল নেওয়া যায়; Wake word চালু করলে "সখি" বলে ডাকলেই Sokhi জাগবে, আর রাতের Auto-dim চোখ বাঁচাবে।</li></ul>'+
 '<div style="display:flex;gap:6px;justify-content:flex-end;margin-top:14px;flex-wrap:wrap"><button id="fe2help-onboard" type="button">প্রথম-চালুর গাইড আবার দেখাও</button><button id="fe2help-close" type="button">বন্ধ করো</button></div></div>';
 document.body.appendChild(m);
 m.addEventListener('click',function(e){if(e.target===m)m.style.display='none'});
 $('fe2help-close').addEventListener('click',function(){m.style.display='none'});
 $('fe2help-onboard').addEventListener('click',function(){m.style.display='none';showOnboarding()})}
/* ================= ৩৯: প্রতিদিনের টিপ কার্ড ================= */
const TIPS=[
 'লেখার ঘরে "/" লিখলেই কমান্ডের তালিকা আসে — সেখান থেকে এক চাপে কাজ চালাতে পারো।',
 'text ফাইল বা ছবি টেনে চ্যাটে ফেললেই (drag-drop) Sokhi সেটা পড়ে নেবে; paste করলেও হবে।',
 'স্মৃতি ট্যাবে গেলে Sokhi কী কী মনে রেখেছে দেখতে পারবে — ভুল তথ্য ✕ চেপে মুছতেও পারবে।',
 'ফোকাস মোড (⛶ বোতাম) চালু করলে পাশের প্যানেল সরে গিয়ে চ্যাট পুরো জায়গা পায় — পড়ার জন্য আরাম।',
 'সেটিংসে শান্ত সময় বসালে রাতে Sokhi নিজে থেকে গলায় বলবে না।',
 'কথোপকথন-বারের "তালিকা" থেকে পুরোনো চ্যাটে ফিরতে পারো, আবার .txt হিসেবে export-ও করা যায়।',
 'সেটিংসের অক্ষরের আকার স্লাইডার দিয়ে চোখের আরাম অনুযায়ী লেখা বড়-ছোট করা যায়।',
 'মাইকে বলতে বলতেই লেখা ঘরে আংশিক লেখা দেখা যাবে — শেষ হলেই নিজে পাঠিয়ে দেবে।',
 'নরম (চোখের আরাম) থিমটা রাতে চোখের জন্য হালকা — সেটিংসের থিম থেকে বেছে নাও।',
 'বার্তার নিচের 📌 চাপ দিলে সেটা পিন ট্যাবে জমা থাকে — দরকারি উত্তর হারাবে না। সেটিংস থেকে মাঝে মাঝে ব্যাকআপ নিয়ে রাখো।'];
function buildTipCard(){
 const left=$('leftcol');if(!left)return;
 const card=document.createElement('div');card.className='card';card.id='fe2tipcard';
 const h=document.createElement('h3');h.textContent='💡 আজকের টিপ';card.appendChild(h);
 const b=document.createElement('div');b.className='body';
 const idx=Math.floor(Date.now()/86400000)%TIPS.length;
 b.textContent=TIPS[idx];card.appendChild(b);
 left.appendChild(card)}
/* ================= v1.3 fe3: পিন, Wake word, Auto-dim, ব্যাকআপ ================= */
/* ---------- B: বার্তা pin করা (script-1-এর 📌 বোতাম এখানে ডাকে) ---------- */
window.fe3PinMessage=async function(d,btn){
 if(!d)return;
 const who=d.classList.contains('me')?'me':'sokhi';
 let idx=parseInt(d.dataset.idx,10);if(isNaN(idx))idx=-1;
 const text=d._full||'';
 try{
  const j=await api('/api/pins',{action:'add',convo_id:(typeof activeId!=='undefined'?activeId:null),idx:idx,who:who,text:text});
  if(j&&j.ok===false)throw 'bad';
  if(btn){const old=btn.textContent;btn.textContent='✓ Pin হয়েছে';setTimeout(function(){btn.textContent=old},1400)}
 }catch(e){setStatus('Pin করা গেল না — আবার চেষ্টা করো')}};
/* ---------- C: পিন ট্যাব ---------- */
async function loadPins(){
 const box=$('fe3pinlist');if(!box)return;
 try{
  const j=await api('/api/pins',{action:'list'});
  const pins=(j&&j.pins)||[];
  box.innerHTML='';
  if(!pins.length){const d=document.createElement('div');d.className='small';d.textContent='এখনো কোনো বার্তা pin করোনি — বার্তার নিচের 📌 চাপ দিলে এখানে জমা থাকবে।';box.appendChild(d);return}
  pins.forEach(function(pin){
   const row=document.createElement('div');row.className='fe3pinrow';
   const tx=document.createElement('div');tx.className='tx';
   const full=String((pin&&pin.text)||'');
   tx.textContent=full.length>160?full.slice(0,160)+'…':full;
   const meta=document.createElement('div');meta.className='m';
   const bits=[];
   if(pin.title)bits.push(String(pin.title));
   else if(pin.convo_id)bits.push('কথোপকথন');
   const dt=fmtDate(pin.ts);if(dt)bits.push(dt);
   meta.textContent=bits.join(' • ');tx.appendChild(meta);
   row.appendChild(tx);
   const open=document.createElement('button');open.textContent='খোলো';open.title='কথোপকথন খোলো';
   open.addEventListener('click',function(){if(pin.convo_id)switchConvo(pin.convo_id)});
   row.appendChild(open);
   const del=document.createElement('button');del.textContent='✕';del.title='Pin তোলো';
   del.addEventListener('click',async function(){
    try{await api('/api/pins',{action:'remove',id:pin.id})}catch(e){}
    loadPins()});
   row.appendChild(del);
   box.appendChild(row)})
 }catch(e){box.innerHTML='';const d=document.createElement('div');d.className='small';d.textContent='Pin তালিকা লোড করা গেল না।';box.appendChild(d)}}
function buildPinsPane(){
 const right=$('rightcol');if(!right)return;
 const tabs=right.querySelector('.tabs');
 if(tabs){const b=document.createElement('button');b.id='tabbtn-pins';b.textContent='পিন';b.addEventListener('click',function(){fe2Tab('pins')});tabs.appendChild(b)}
 ['chat','agents','notes','tasks','memory'].forEach(function(n){
  const b=$('tabbtn-'+n);if(!b)return;
  b.addEventListener('click',function(){const p=$('pane-pins');if(p)p.classList.remove('on');const pb=$('tabbtn-pins');if(pb)pb.classList.remove('on')})});
 const pane=document.createElement('div');pane.className='tabpane';pane.id='pane-pins';
 const scroll=document.createElement('div');scroll.id='fe3pinscroll';
 const head=document.createElement('div');head.style.cssText='display:flex;gap:6px;align-items:center;margin-bottom:8px';
 const h=document.createElement('div');h.className='secttl';h.style.flex='1';h.textContent='📌 Pin করা বার্তা';head.appendChild(h);
 const rb=document.createElement('button');rb.textContent='🔄 রিফ্রেশ';rb.style.fontSize='13px';rb.addEventListener('click',loadPins);head.appendChild(rb);
 scroll.appendChild(head);
 const list=document.createElement('div');list.id='fe3pinlist';scroll.appendChild(list);
 pane.appendChild(scroll);
 const memPane=$('pane-memory');
 if(memPane&&memPane.parentNode===right)right.insertBefore(pane,memPane.nextSibling);
 else{const chatPane=$('pane-chat');if(chatPane&&chatPane.parentNode===right)right.insertBefore(pane,chatPane.nextSibling);else right.appendChild(pane)}}
/* ---------- F: রাতের Auto-dim ইঞ্জিন ---------- */
function fe3DimMirror(){
 try{return JSON.parse(localStorage.getItem('sokhi_dim')||'{}')}catch(e){return {}}}
window.sokhiDimNow=function(){
 const dm=fe3DimMirror();
 if(!dm||!dm.enabled)return false;
 const s=dm.start||'',e=dm.end||'';
 if(!s||!e||s===e)return false;
 const now=new Date(),cur=now.getHours()*60+now.getMinutes();
 const sm=parseInt(s.split(':')[0],10)*60+(parseInt(s.split(':')[1],10)||0);
 const em=parseInt(e.split(':')[0],10)*60+(parseInt(e.split(':')[1],10)||0);
 if(sm<em)return cur>=sm&&cur<em;
 return cur>=sm||cur<em};
function fe3DimLevel(){
 const dm=fe3DimMirror();const lv=parseFloat(dm&&dm.level);
 return isNaN(lv)?0.6:Math.min(1,Math.max(0.3,lv))}
function applyDim(){
 let ov=$('fe3dimoverlay');
 if(!ov){ov=document.createElement('div');ov.id='fe3dimoverlay';ov.style.cssText='position:fixed;inset:0;background:#000;opacity:0;pointer-events:none;z-index:8500;transition:opacity 1.2s';document.body.appendChild(ov)}
 ov.style.opacity=window.sokhiDimNow()?String(1-fe3DimLevel()):'0'}
window.fe3ApplyDim=applyDim;
function fe3DimLevelLabel(){
 const el=$('fe3dimlevel');const lbl=$('fe3dimlevelval');if(!el||!lbl)return;
 const lv=parseFloat(el.value)||0.6;
 lbl.textContent=(typeof bnDigits==='function'?bnDigits(Math.round(lv*100)):String(Math.round(lv*100)))+'%'}
async function saveDim(){
 const on=$('fe3dimon')?$('fe3dimon').checked:false;
 const st=$('fe3dimstart')?($('fe3dimstart').value||'21:00'):'21:00';
 const en=$('fe3dimend')?($('fe3dimend').value||'06:00'):'06:00';
 const lvEl=$('fe3dimlevel');const lv=lvEl?(parseFloat(lvEl.value)||0.6):0.6;
 try{localStorage.setItem('sokhi_dim',JSON.stringify({enabled:on,start:st,end:en,level:lv}))}catch(e){}
 try{await api('/api/settings',{dim_start:on?st:'',dim_end:on?en:'',dim_level:lv})}catch(e){}
 applyDim();
 setStatus(on?'🌙 Auto-dim সেভ হয়েছে — রাতে স্ক্রিন নিজে ম্লান হবে':'Auto-dim সেভ হয়েছে (বন্ধ আছে)')}
/* ---------- G: Wake word ইঞ্জিন ---------- */
let wakeRec=null,wakeOn=false,wakeRestart=null;
try{wakeOn=localStorage.getItem('sokhi_wake')==='1'}catch(e){}
function fe3LiveOn(){const b=$('livebtn');return !!(b&&b.classList.contains('on'))}
function fe3Speaking(){try{return !!speakingNow}catch(e){return false}}
function startWake(){
 if(!wakeOn||wakeRec||fe3LiveOn()||fe3Speaking())return;
 const R=window.SpeechRecognition||window.webkitSpeechRecognition;if(!R)return;
 let r=null;
 try{r=new R()}catch(e){return}
 try{r.lang='bn-BD';r.interimResults=true;r.continuous=true}
 catch(e){try{r.continuous=false}catch(e2){}}
 wakeRec=r;
 r.onresult=function(ev){
  let txt='';
  try{for(let i=0;i<ev.results.length;i++)txt+=ev.results[i][0].transcript+' '}catch(err){}
  if(/সখি|সখী|শখি|sokhi|sakhi/i.test(txt)&&!isEchoOfSpeech(txt)){
   stopWake(false);
   setStatus('👂 ডাক শুনেছি!');
   if(typeof startLive==='function')startLive();
   else if(typeof mic==='function')mic()}};
 r.onend=function(){
  if(wakeRec!==r)return;wakeRec=null;
  if(wakeOn&&!fe3LiveOn()&&!fe3Speaking()){clearTimeout(wakeRestart);wakeRestart=setTimeout(startWake,800)}};
 r.onerror=function(ev){
  if(ev&&ev.error==='not-allowed'){
   if(wakeRec===r)wakeRec=null;
   wakeOn=false;
   try{localStorage.setItem('sokhi_wake','0')}catch(e){}
   const wk=$('fe3wake');if(wk)wk.checked=false;
   try{api('/api/settings',{wake_word:false}).catch(function(){})}catch(e){}
   setStatus('🔇 Wake word-এর জন্য মাইকের অনুমতি লাগবে');
   try{r.abort()}catch(e){}
   return}
  if(wakeRec!==r)return;wakeRec=null;
  if(wakeOn&&!fe3LiveOn()&&!fe3Speaking()){clearTimeout(wakeRestart);wakeRestart=setTimeout(startWake,800)}};
 try{stopSpeak()}catch(e){} /* v1.4 #113 barge-in */
 try{r.start()}catch(e){if(wakeRec===r)wakeRec=null}}
function stopWake(clearFlag){
 clearTimeout(wakeRestart);
 const r=wakeRec;wakeRec=null;
 if(r){try{r.abort()}catch(e){}}
 if(clearFlag){wakeOn=false;try{localStorage.setItem('sokhi_wake','0')}catch(e){}}}
window.fe3StartWake=startWake;
window.fe3StopWake=stopWake;
function fe3SetWake(on){
 wakeOn=!!on;
 try{localStorage.setItem('sokhi_wake',wakeOn?'1':'0')}catch(e){}
 try{api('/api/settings',{wake_word:wakeOn}).catch(function(){})}catch(e){}
 const wk=$('fe3wake');if(wk)wk.checked=wakeOn;
 if(wakeOn)startWake();else stopWake(false)}
/* v1.9.1: echo guard টগল — fe3SetWake-এর একই ধরন (localStorage + সার্ভার) */
function fe3SetEchoGuard(on){
 echoGuardOn=!!on;
 try{localStorage.setItem('sokhi_echoguard',echoGuardOn?'1':'0')}catch(e){}
 try{api('/api/settings',{echo_guard:echoGuardOn}).catch(function(){})}catch(e){}
 const egx=$('fe3echoguard');if(egx)egx.checked=echoGuardOn;
 setStatus(echoGuardOn?'🔇 নিজের কণ্ঠ চেনা চালু':'🔊 নিজের কণ্ঠ চেনা বন্ধ')}
window.fe3SetEchoGuard=fe3SetEchoGuard;
/* ---------- H: ব্যাকআপ / রিস্টোর / Sync ---------- */
async function fe3ExportBackup(kind){
 const msg=$('fe3backupmsg');
 try{
  const j=await api('/api/backup',{action:'export',kind:kind});
  if(!j||!j.ok||!j.bundle)throw 'bad';
  const blob=new Blob([JSON.stringify(j.bundle,null,2)],{type:'application/json'});
  const url=URL.createObjectURL(blob);
  const a=document.createElement('a');a.href=url;
  a.download=j.filename||(kind==='sync'?'sokhi-sync.json':'sokhi-backup.json');
  document.body.appendChild(a);a.click();a.remove();
  setTimeout(function(){URL.revokeObjectURL(url)},2000);
  if(msg)msg.textContent='✓ ব্যাকআপ নেওয়া হয়েছে';
 }catch(e){if(msg)msg.textContent='ব্যাকআপ নেওয়া গেল না — আবার চেষ্টা করো'}}
async function fe3ImportBackup(file){
 const msg=$('fe3backupmsg');
 let bundle=null;
 try{
  let text='';
  if(file.text)text=await file.text();
  else text=await new Promise(function(res,rej){const rd=new FileReader();rd.onload=function(){res(String(rd.result||''))};rd.onerror=rej;rd.readAsText(file)});
  bundle=JSON.parse(text);
 }catch(e){if(msg)msg.textContent='ফাইলটা ঠিকমতো পড়া গেল না।';return}
 if(!confirm('এই ফাইলের তথ্য দিয়ে বর্তমান কথোপকথন, স্মৃতি ও সেটিংস বদলে যাবে (আগেরটা নিজে থেকে একটা snapshot-এ সেভ থাকবে)। এগোবে?'))return;
 try{
  const j=await api('/api/backup',{action:'import',bundle:bundle});
  if(j&&j.ok){if(msg)msg.textContent='✓ রিস্টোর হয়েছে — পেজ আবার লোড হচ্ছে';setTimeout(function(){location.reload()},800)}
  else if(msg)msg.textContent=(j&&j.error)?String(j.error):'রিস্টোর করা গেল না — আবার চেষ্টা করো';
 }catch(e){if(msg)msg.textContent='রিস্টোর করা গেল না — আবার চেষ্টা করো'}}
/* ---------- fe3 ইঞ্জিন বুট ---------- */
function buildFe3Engines(){
 applyDim();
 setInterval(applyDim,30000);
 setInterval(function(){if(wakeOn&&!wakeRec&&!fe3LiveOn()&&!fe3Speaking())startWake()},5000);
 if(wakeOn)setTimeout(startWake,1500)}
/* =====================================================================
   Desktop Sokhi v1.5.0 — WAVE-3 daily-life UI (#212 বাজার + #334/#324
   আজকের কার্ড). ONE <script> block's contents — integrator pastes this
   INSIDE the final fe2/fe3 <script> block (or a new <script> right
   before </body>), AFTER the main script so api/apiGet/add/$ exist,
   and adds buildDailyUI() to the boot call list (next to buildTipCard()).
   House style followed: DOM built dynamically, no innerHTML templates
   for user data (textContent only), ids prefixed daily* to avoid clashes.
   ===================================================================== */
(function(){
'use strict';
var d$ = function(id){ return document.getElementById(id); };
var _dailyBooted = false;

/* ---------------- #334 + #324: আজকের কার্ড (chat pane, first load) ------ */
async function loadDailyCard(){
  var box = d$('dailycardbody'); if(!box) return;
  try{
    var j = await apiGet('/api/dailycard');
    if(!j || !j.fact){ box.textContent = 'আজকের কার্ড আনা গেল না।'; return; }
    box.innerHTML = '';
    var f = document.createElement('div');
    f.textContent = '💡 অজানা সত্য: ' + j.fact;
    box.appendChild(f);
    var p = document.createElement('div');
    p.style.marginTop = '6px';
    p.textContent = '📜 প্রবাদ: ' + (j.proverb || '');
    box.appendChild(p);
    var m = document.createElement('div');
    m.className = 'small';
    m.textContent = 'মানে: ' + (j.meaning || '');
    box.appendChild(m);
  }catch(e){ box.textContent = 'আজকের কার্ড আনা গেল না।'; }
}

function buildDailyCard(){
  /* Card lives at the top of the chat pane (#pane-chat), above #chat,
     so it is seen on first load without disturbing the message flow. */
  var pane = d$('pane-chat'); if(!pane || d$('dailycard')) return;
  var card = document.createElement('div');
  card.id = 'dailycard';
  card.className = 'card';
  card.style.cssText = 'margin:0 0 8px;padding:10px 12px;flex:none';
  var head = document.createElement('div');
  head.style.cssText = 'display:flex;gap:6px;align-items:center';
  var h = document.createElement('div');
  h.className = 'secttl'; h.style.flex = '1'; h.textContent = '🌞 আজকের কার্ড';
  head.appendChild(h);
  var rb = document.createElement('button');
  rb.textContent = '🔄'; rb.title = 'আবার লোড করো'; rb.style.fontSize = '12px';
  rb.addEventListener('click', loadDailyCard);
  head.appendChild(rb);
  var hide = document.createElement('button');
  hide.textContent = '✕'; hide.title = 'আজকের জন্য লুকাও'; hide.style.fontSize = '12px';
  hide.addEventListener('click', function(){ card.style.display = 'none'; });
  head.appendChild(hide);
  card.appendChild(head);
  var body = document.createElement('div');
  body.id = 'dailycardbody';
  body.style.cssText = 'font-size:13.5px;line-height:1.6;margin-top:4px';
  body.textContent = 'লোড হচ্ছে…';
  card.appendChild(body);
  var chat = d$('chat');
  if(chat && chat.parentNode === pane) pane.insertBefore(card, chat);
  else pane.appendChild(card);
  loadDailyCard();
}

/* ---------------- #212: বাজার-তালিকা (Tasks pane-এর ভিতরে) ------------- */
function dailyMoney(v){
  var n = parseFloat(v) || 0;
  var s = (n === Math.floor(n)) ? String(Math.floor(n)) : String(n);
  return s.replace(/[0-9]/g, function(c){ return '০১২৩৪৫৬৭৮৯'[+c]; });
}

async function loadBazaar(){
  var list = d$('dailybazaarlist'); if(!list) return;
  var tot = d$('dailybazaartotal');
  try{
    var j = await apiGet('/api/bazaar');
    var items = (j && j.items) || [];
    list.innerHTML = '';
    if(!items.length){
      var d = document.createElement('div');
      d.className = 'small';
      d.textContent = 'তালিকা খালি — নিচে লিখে যোগ করো, বা চ্যাটে বলো: "বাজারে যোগ করো চাল"।';
      list.appendChild(d);
    }
    items.forEach(function(it){
      var row = document.createElement('div');
      row.style.cssText = 'display:flex;gap:6px;align-items:center;padding:6px 0;border-bottom:1px solid var(--line);font-size:14px';
      var cb = document.createElement('input');
      cb.type = 'checkbox'; cb.checked = !!it.bought; cb.title = 'কেনা হয়েছে';
      cb.style.cssText = 'flex:none;width:auto';
      cb.addEventListener('change', async function(){
        try{ await api('/api/bazaar', {action:'toggle', id:it.id}); }catch(e){}
        loadBazaar();
      });
      row.appendChild(cb);
      var tx = document.createElement('span');
      tx.style.flex = '1';
      if(it.bought) tx.style.cssText = 'flex:1;text-decoration:line-through;color:var(--muted)';
      var label = String(it.item || '');
      if(it.qty) label += ' (' + it.qty + ')';
      if(parseFloat(it.est_price) > 0) label += ' — আনুমানিক ' + dailyMoney(it.est_price) + ' টাকা';
      tx.textContent = label;
      row.appendChild(tx);
      var del = document.createElement('button');
      del.textContent = '✕'; del.title = 'মোছো'; del.style.fontSize = '12px';
      del.addEventListener('click', async function(){
        try{ await api('/api/bazaar', {action:'delete', id:it.id}); }catch(e){}
        loadBazaar();
      });
      row.appendChild(del);
      list.appendChild(row);
    });
    if(tot){
      tot.textContent = items.length
        ? ('আনুমানিক মোট খরচ: ' + dailyMoney(j.total) + ' টাকা (কেনা ' +
           dailyMoney(j.bought_total) + ' টাকা, বাকি ' + dailyMoney(j.pending_total) + ' টাকা)')
        : '';
    }
  }catch(e){
    list.innerHTML = '';
    var d2 = document.createElement('div');
    d2.className = 'small'; d2.textContent = 'বাজারের তালিকা লোড করা গেল না।';
    list.appendChild(d2);
  }
}

async function addBazaarItem(){
  var itemEl = d$('dailybazaaritem'), qtyEl = d$('dailybazaarqty'),
      priceEl = d$('dailybazaarprice'), msg = d$('dailybazaarmsg');
  var item = itemEl ? itemEl.value.trim() : '';
  if(!item){ if(msg) msg.textContent = 'আগে জিনিসের নামটা লেখো।'; return; }
  var body = { action:'add', item:item,
               qty: qtyEl ? qtyEl.value.trim() : '',
               est_price: priceEl ? (parseFloat(priceEl.value) || 0) : 0 };
  try{
    var j = await api('/api/bazaar', body);
    if(j && j.ok === false){ if(msg) msg.textContent = j.error || 'যোগ করা গেল না।'; return; }
    if(itemEl) itemEl.value = '';
    if(qtyEl) qtyEl.value = '';
    if(priceEl) priceEl.value = '';
    if(msg) msg.textContent = '';
    loadBazaar();
  }catch(e){ if(msg) msg.textContent = 'যোগ করা গেল না — আবার চেষ্টা করো।'; }
}

function buildBazaarSection(){
  var pane = d$('pane-tasks'); if(!pane || d$('dailybazaar')) return;
  var wrap = document.createElement('div');
  wrap.id = 'dailybazaar';
  wrap.style.cssText = 'margin-top:16px;border-top:1px solid var(--line);padding-top:10px;display:flex;flex-direction:column;min-height:0';
  var h = document.createElement('div');
  h.className = 'secttl'; h.textContent = '🛒 বাজারের তালিকা';
  wrap.appendChild(h);
  var tot = document.createElement('div');
  tot.id = 'dailybazaartotal'; tot.className = 'statline';
  wrap.appendChild(tot);
  var list = document.createElement('div');
  list.id = 'dailybazaarlist';
  list.style.cssText = 'overflow-y:auto;min-height:0';
  wrap.appendChild(list);
  var row1 = document.createElement('div');
  row1.style.cssText = 'display:flex;gap:6px;margin-top:8px';
  var item = document.createElement('input');
  item.id = 'dailybazaaritem'; item.type = 'text';
  item.placeholder = 'জিনিসের নাম…'; item.style.flex = '1';
  row1.appendChild(item);
  var qty = document.createElement('input');
  qty.id = 'dailybazaarqty'; qty.type = 'text';
  qty.placeholder = 'পরিমাণ (৫ কেজি)'; qty.style.cssText = 'flex:0 0 96px;width:96px';
  row1.appendChild(qty);
  wrap.appendChild(row1);
  var row2 = document.createElement('div');
  row2.style.cssText = 'display:flex;gap:6px;margin-top:6px';
  var price = document.createElement('input');
  price.id = 'dailybazaarprice'; price.type = 'number'; price.min = '0';
  price.placeholder = 'আনুমানিক দাম (টাকা)'; price.style.flex = '1';
  row2.appendChild(price);
  var addBtn = document.createElement('button');
  addBtn.textContent = 'যোগ করো';
  addBtn.addEventListener('click', addBazaarItem);
  row2.appendChild(addBtn);
  var clearBtn = document.createElement('button');
  clearBtn.textContent = 'কেনাগুলো মোছো'; clearBtn.style.fontSize = '13px';
  clearBtn.addEventListener('click', async function(){
    try{ await api('/api/bazaar', {action:'clear_bought'}); }catch(e){}
    loadBazaar();
  });
  row2.appendChild(clearBtn);
  wrap.appendChild(row2);
  var msg = document.createElement('div');
  msg.id = 'dailybazaarmsg'; msg.className = 'small'; msg.style.marginTop = '4px';
  wrap.appendChild(msg);
  item.addEventListener('keydown', function(e){ if(e.key === 'Enter') addBazaarItem(); });
  pane.appendChild(wrap);
  /* Tasks tab খুললেই তালিকা টাটকা থাকুক — বিদ্যমান tab বোতামে হুক */
  var tb = d$('tabbtn-tasks');
  if(tb) tb.addEventListener('click', loadBazaar);
  loadBazaar();
}

/* ---------------- boot (integrator calls this once) -------------------- */
function buildDailyUI(){
  if(_dailyBooted) return;
  _dailyBooted = true;
  buildDailyCard();
  buildBazaarSection();
}
window.buildDailyUI = buildDailyUI;
window.dailyLoadBazaar = loadBazaar;
window.dailyLoadCard = loadDailyCard;
})();

function buildSettingsV18Model(){
 const panel=document.querySelector('#modal .panel');if(!panel)return;
 if(document.getElementById('fe8modelsec'))return;
 const closeBtn=Array.prototype.slice.call(panel.querySelectorAll('button')).find(function(b){return b.textContent.trim()==='বন্ধ করো'});
 const box=document.createElement('div');box.id='fe8modelsec';
 box.innerHTML=
  '<hr><div class="secttl">🧠 Gemini মডেল</div>'+
  '<div style="font-size:13px;margin-top:6px">কোন মডেলটা আগে চেষ্টা হবে: '+
  '<select id="fe8model">'+
  '<option value="auto">স্বয়ংক্রিয় (সুপারিশ — মডেল নিজে বেছে নেবে)</option>'+
  '<option value="gemini-3.5-flash-lite">দ্রুত (flash-lite)</option>'+
  '<option value="gemini-3.5-flash">gemini-3.5-flash</option>'+
  '<option value="gemini-2.5-flash">gemini-2.5-flash</option>'+
  '<option value="gemini-3.8-flash">gemini-3.8-flash (বর্তমান ডিফল্ট)</option>'+
  '<option value="custom">নিজের মডেলের নাম…</option>'+
  '</select></div>'+
  '<div id="fe8modelcustomrow" style="display:none;gap:6px;align-items:center;flex-wrap:wrap;margin-top:8px;font-size:13px">'+
  '<input id="fe8modelcustom" type="text" placeholder="যেমন: gemini-2.5-flash" style="flex:1;min-width:160px">'+
  '<button id="fe8modelsave" type="button">সেভ</button></div>'+
  '<div id="fe8modelmsg" class="small" style="margin-top:6px"></div>'+
  '<div class="hint">নিজে মডেল বেছে দিলে সেটাই আগে চেষ্টা হবে; পাওয়া না গেলে নিজে থেকে অন্য ফ্রি মডেলে চলে যাবে আর চ্যাটে জানিয়ে দেবে।</div>';
 if(closeBtn)panel.insertBefore(box,closeBtn);else panel.appendChild(box);
 const sel=$('fe8model');
 const row=$('fe8modelcustomrow');
 const inp=$('fe8modelcustom');
 const msg=$('fe8modelmsg');
 function showMsg(t,isErr){
  if(!msg)return;
  msg.textContent=t||'';
  msg.style.color=isErr?'#c0392b':''}
 async function saveModel(val){
  showMsg('সেভ হচ্ছে…');
  try{
   const r=await api('/api/settings',{gemini_model:val});
   if(r&&r.ok===false){showMsg(r.error||'সেভ হয়নি — মডেলের নামটা আবার দেখো।',true);return false}
   showMsg('সেভ হয়ে গেছে ✓');
   return true;
  }catch(e){showMsg('সেভ হয়নি — আবার চেষ্টা করো।',true);return false}}
 if(sel)sel.addEventListener('change',function(){
  if(sel.value==='custom'){
   if(row)row.style.display='flex';
   showMsg('নিচে মডেলের নাম লিখে সেভ চাপো।');
   if(inp)inp.focus();
  }else{
   if(row)row.style.display='none';
   saveModel(sel.value);
  }});
 const sv=$('fe8modelsave');
 if(sv)sv.addEventListener('click',function(){
  const v=inp?inp.value.trim():'';
  if(!v){showMsg('আগে মডেলের নামটা লেখো।',true);return}
  saveModel(v)});
 fe8LoadModel();
}
async function fe8LoadModel(){
 const sel=$('fe8model');if(!sel)return;
 const row=$('fe8modelcustomrow');
 const inp=$('fe8modelcustom');
 try{
  const s=await apiGet('/api/status');
  if(!s)return;
  if(!s.gemini_model_mode||s.gemini_model_mode==='auto'){
   sel.value='auto';
   if(row)row.style.display='none';
   return}
  const known=['gemini-3.5-flash-lite','gemini-3.5-flash','gemini-2.5-flash','gemini-3.8-flash'];
  const m=s.gemini_model||'';
  if(known.indexOf(m)>=0){
   sel.value=m;
   if(row)row.style.display='none';
  }else{
   sel.value='custom';
   if(row)row.style.display='flex';
   if(inp)inp.value=m;
  }
 }catch(e){}}
/* boot (আলাদা করে যোগ করো): buildSettingsExtras();-এর পরে
   buildSettingsV18Model(); */

window.browserVoiceName=window.browserVoiceName||'';

function populateBrowserVoices(){
 const sel=$('fe8browser');if(!sel)return;
 let vs=[];try{vs=speechSynthesis.getVoices()||[]}catch(e){}
 const cur=sel.value||window.browserVoiceName||'';
 sel.innerHTML='';
 const auto=document.createElement('option');auto.value='';auto.textContent='স্বয়ংক্রিয় (ডিভাইসের সেরা বাংলা গলা)';sel.appendChild(auto);
 vs.forEach(function(v){const o=document.createElement('option');o.value=v.name;o.textContent=v.name+' — '+(v.lang||'');sel.appendChild(o)});
 /* Preserve the current selection when that voice still exists on this
    device; if it does not (e.g. name saved from another device), the select
    falls back to "" (স্বয়ংক্রিয়) on screen. The saved config is NOT
    rewritten here — populate never saves. */
 if(cur&&vs.some(function(v){return v.name===cur}))sel.value=cur;else sel.value=''}

async function fe8LoadVoices(){
 try{const s=await apiGet('/api/status');if(!s)return;
  if(s.tts_voice){const ev=$('fe8edgevoice');if(ev)ev.value=s.tts_voice}
  if(s.tts_engine){const ge=$('fe8engine');if(ge)ge.value=s.tts_engine}
  if(s.gemini_voice){const gv=$('fe8gemvoice');if(gv)gv.value=s.gemini_voice}
  window.browserVoiceName=s.browser_voice||'';
  populateBrowserVoices();
  const bs=$('fe8browser');if(bs&&window.browserVoiceName)bs.value=window.browserVoiceName;
 }catch(e){}}

async function fe8TestVoice(){
 const sample='আসসালামু আলাইকুম, আমি সখী।';
 const name=window.browserVoiceName||'';
 if(name){
  try{const vs=speechSynthesis.getVoices()||[];
   const v=vs.find(function(x){return x.name===name});
   if(v){const u=new SpeechSynthesisUtterance(sample);u.voice=v;u.lang=v.lang||'bn-BD';u.rate=.92*(window.voiceRate||1);u.pitch=1.05;speechSynthesis.speak(u);return}
  }catch(e){}
  /* Chosen name is not present on THIS device — fall through to the
     Edge-then-synthSpeak path below instead of staying silent. */}
 try{if(typeof edgeSpeak!=='function')throw 'noedge';await edgeSpeak(sample);return}catch(e){}
 try{await synthSpeak(sample)}catch(e){}}

function buildSettingsV18Voice(){
 const panel=document.querySelector('#modal .panel');if(!panel)return;
 if($('fe8settings'))return;
 const closeBtn=Array.prototype.slice.call(panel.querySelectorAll('button')).find(function(b){return b.textContent.trim()==='বন্ধ করো'});
 const box=document.createElement('div');box.id='fe8settings';
 box.innerHTML=
  '<hr><div class="secttl">🗣️ কণ্ঠ বাছাই</div>'+
  '<div style="font-size:13px;margin-top:6px">কণ্ঠের ইঞ্জিন: '+
  '<select id="fe8engine"><option value="edge">Edge (মাইক্রোসফটের গলা)</option><option value="gemini">Gemini (সবচেয়ে প্রাণবন্ত — ফ্রি key লাগবে)</option><option value="browser">ব্রাউজারের গলা (ডিভাইসের নিজের)</option></select></div>'+
  '<div style="font-size:13px;margin-top:6px">Gemini গলা: '+
  '<select id="fe8gemvoice"><option value="Aoede">আওয়েদে (উষ্ণ নারী কণ্ঠ)</option><option value="Kore">কোরে (নারী কণ্ঠ)</option><option value="Leda">লেডা (নারী কণ্ঠ)</option><option value="Callirrhoe">ক্যালিরো (নারী কণ্ঠ)</option><option value="Puck">পাক (পুরুষ কণ্ঠ)</option></select></div>'+
  '<div style="font-size:13px;margin-top:6px">Edge গলা: '+
  '<select id="fe8edgevoice"><option value="bn-BD-NabanitaNeural">নাবনিতা (নারী কণ্ঠ)</option><option value="bn-BD-PradeepNeural">প্রদীপ (পুরুষ কণ্ঠ)</option><option value="bn-IN-TanishaaNeural">তানিশা (নারী কণ্ঠ)</option></select></div>'+
  '<div style="font-size:13px;margin-top:6px">ব্রাউজারের গলা: '+
  '<select id="fe8browser"><option value="">স্বয়ংক্রিয় (ডিভাইসের সেরা বাংলা গলা)</option></select></div>'+
  '<div style="margin-top:8px"><button id="fe8voicetest" type="button">কণ্ঠ পরীক্ষা</button> <span id="fe8voicemsg" class="small"></span></div>'+
  '<div class="hint">Gemini কণ্ঠে চ্যাটের একই ফ্রি Gemini key লাগে; key না থাকলে বা Gemini সাড়া না দিলে নিজে থেকে Edge গলায় বলবে আর status-এ জানিয়ে দেবে। Edge গলা ইন্টারনেটে তৈরি হয়; ব্রাউজারের গলা ডিভাইসের নিজের। গলার গতি আগের স্লাইডারেই বদলায় (Gemini কণ্ঠে গতি স্লাইডার কাজ করে না)।</div>';
 if(closeBtn)panel.insertBefore(box,closeBtn);else panel.appendChild(box);
 const ev=$('fe8edgevoice');
 if(ev)ev.addEventListener('change',async function(){
  const msg=$('fe8voicemsg');
  try{const j=await api('/api/settings',{tts_voice:ev.value});
   if(j&&j.ok){if(msg)msg.textContent='✅ Edge গলা সেভ হয়েছে'}
   else{if(msg)msg.textContent='❌ '+(j&&j.error?j.error:'সেভ হয়নি');fe8LoadVoices()}
  }catch(e){if(msg)msg.textContent='❌ সেভ হয়নি — আবার চেষ্টা করো'}});
 const bs=$('fe8browser');
 if(bs)bs.addEventListener('change',async function(){
  window.browserVoiceName=bs.value;
  const msg=$('fe8voicemsg');
  try{const j=await api('/api/settings',{browser_voice:bs.value});
   if(j&&j.ok){if(msg)msg.textContent=bs.value?'✅ ব্রাউজারের গলা সেভ হয়েছে':'✅ ব্রাউজারের গলা স্বয়ংক্রিয় রাখা হয়েছে'}
   else{if(msg)msg.textContent='❌ '+(j&&j.error?j.error:'সেভ হয়নি')}
  }catch(e){if(msg)msg.textContent='❌ সেভ হয়নি — আবার চেষ্টা করো'}});
 const ge=$('fe8engine');
 if(ge)ge.addEventListener('change',async function(){
  const msg=$('fe8voicemsg');
  try{const j=await api('/api/settings',{tts_engine:ge.value});
   if(j&&j.ok){if(msg)msg.textContent='✅ কণ্ঠের ইঞ্জিন সেভ হয়েছে'}
   else{if(msg)msg.textContent='❌ '+(j&&j.error?j.error:'সেভ হয়নি');fe8LoadVoices()}
  }catch(e){if(msg)msg.textContent='❌ সেভ হয়নি — আবার চেষ্টা করো'}});
 const gv=$('fe8gemvoice');
 if(gv)gv.addEventListener('change',async function(){
  const msg=$('fe8voicemsg');
  try{const j=await api('/api/settings',{gemini_voice:gv.value});
   if(j&&j.ok){if(msg)msg.textContent='✅ Gemini গলা সেভ হয়েছে'}
   else{if(msg)msg.textContent='❌ '+(j&&j.error?j.error:'সেভ হয়নি');fe8LoadVoices()}
  }catch(e){if(msg)msg.textContent='❌ সেভ হয়নি — আবার চেষ্টা করো'}});
 const tb=$('fe8voicetest');
 if(tb)tb.addEventListener('click',function(){fe8TestVoice()});
 if(window.speechSynthesis){
  try{speechSynthesis.addEventListener('voiceschanged',populateBrowserVoices)}
  catch(e){try{speechSynthesis.onvoiceschanged=populateBrowserVoices}catch(e2){}}}
 populateBrowserVoices();
 fe8LoadVoices()}

/* ================= বুট ================= */
buildConvoBar();
buildMemoryPane();
buildPinsPane();
buildSettingsExtras();
buildSettingsV18Model();
buildSettingsV18Voice();
buildFocusButton();
buildBrainBadge();
buildAttach();
buildPalette();
buildHelp();
buildOnboarding();
buildTipCard();
buildDailyUI();
buildFe3Engines();
try{if(typeof pin==='function'&&pin())loadActiveIntoChat()}catch(e){}
})();

</script>
<script>
/*BW14-START — Worker B v1.4.0 UI (integrator-trimmed): board/doctor
  buttons + memory weights section. (#700 card and #109 UI/engine are
  Worker A's block below — duplicates removed at merge.)
  Uses the page's global api()/apiGet()/add() from the main script. */
(function(){
"use strict";
function el(id){return document.getElementById(id)}
function bwGet(p){
  if(typeof apiGet==="function")return apiGet(p);
  return fetch(p,{headers:{"X-PIN":(typeof pin==="function"?pin():"")}})
    .then(function(r){return r.json()});
}
function bwPost(p,b){
  if(typeof api==="function")return api(p,b);
  return fetch(p,{method:"POST",
    headers:{"Content-Type":"application/json",
             "X-PIN":(typeof pin==="function"?pin():"")},
    body:JSON.stringify(b)}).then(function(r){return r.json()});
}
function bwSay(t){
  if(typeof add==="function"){
    add(t,"sokhi");
    if(typeof scrollChatToBottom==="function")scrollChatToBottom();
  }
}
window.bw14Board=function(){
  bwGet("/api/board").then(function(j){
    bwSay((j&&j.text)||"রিপোর্ট পাইনি।");
  }).catch(function(){bwSay("সাপ্তাহিক রিপোর্ট আনতে পারলাম না।")});
};
window.bw14Doctor=function(){
  bwGet("/api/doctor").then(function(j){
    bwSay((j&&j.text)||"রিপোর্ট পাইনি।");
  }).catch(function(){bwSay("স্বাস্থ্য রিপোর্ট আনতে পারলাম না।")});
};
/* ---------------- স্মৃতির ওজন সেকশন (#pane-memory-তে যোগ) ---------------- */
function bwRenderWeights(){
  var pane=el("pane-memory");
  if(!pane)return;
  var scroll=el("fe2memscroll")||pane;
  var sec=el("bw14weights");
  if(!sec){
    sec=document.createElement("div");
    sec.id="bw14weights";sec.style.marginTop="16px";
    scroll.appendChild(sec);
  }
  bwGet("/api/memory").then(function(j){
    var facts=(j&&j.facts)||[];
    var wts=(j&&j.fact_weights)||[];
    sec.innerHTML="";
    var h=document.createElement("div");h.className="secttl";
    h.textContent="স্মৃতির ওজন (বেশি → কম)";
    sec.appendChild(h);
    if(!facts.length){
      var d=document.createElement("div");d.className="small";
      d.textContent="কিছু নেই।";sec.appendChild(d);return;
    }
    var items=facts.map(function(f,i){
      return {f:f,i:i,w:(typeof wts[i]==="number"?wts[i]:1)};
    });
    items.sort(function(a,b){return (b.w-a.w)||(a.i-b.i)});
    items.forEach(function(it){
      var row=document.createElement("div");
      row.style.cssText="display:flex;gap:6px;align-items:center;margin-top:4px;font-size:13.5px";
      var s=document.createElement("span");s.style.flex="1";
      s.textContent=String(it.f);row.appendChild(s);
      var badge=document.createElement("span");badge.className="small";
      badge.textContent="ওজন "+it.w;row.appendChild(badge);
      sec.appendChild(row);
    });
    var low=items.filter(function(it){return it.w<=1}).slice(0,10);
    if(low.length){
      var ph=document.createElement("div");ph.className="secttl";
      ph.style.marginTop="12px";
      ph.textContent="আর্কাইভ প্রস্তাব (কম ওজনের তথ্য — সিদ্ধান্ত তোমার)";
      sec.appendChild(ph);
      low.forEach(function(it){
        var row=document.createElement("div");
        row.style.cssText="display:flex;gap:6px;align-items:center;margin-top:4px;font-size:13.5px";
        var s=document.createElement("span");s.style.flex="1";
        s.textContent=String(it.f);row.appendChild(s);
        var b=document.createElement("button");
        b.textContent="আর্কাইভ";b.style.fontSize="12px";
        b.addEventListener("click",function(){
          bwPost("/api/memory",{action:"archive_fact",index:it.i})
          .then(function(){
            if(window.fe2Tab)window.fe2Tab("memory");
            setTimeout(bwRenderWeights,400);
          }).catch(function(){});
        });
        row.appendChild(b);sec.appendChild(row);
      });
    }
  }).catch(function(){});
}
/* ---------------- কার্ড তৈরি + বুট ---------------- */
function bwBuild(){
  var left=el("leftcol");
  if(left&&!el("bw14card")){
    var card=document.createElement("div");
    card.className="card";card.id="bw14card";
    var h=document.createElement("h3");
    h.textContent="বোর্ড • ডাক্তার";
    card.appendChild(h);
    var row=document.createElement("div");
    row.style.cssText="display:flex;gap:6px;flex-wrap:wrap";
    var b1=document.createElement("button");
    b1.textContent="🗓️ সাপ্তাহিক রিপোর্ট";b1.style.fontSize="13px";
    b1.addEventListener("click",window.bw14Board);row.appendChild(b1);
    var b2=document.createElement("button");
    b2.textContent="🩺 নিজের ডাক্তার";b2.style.fontSize="13px";
    b2.addEventListener("click",window.bw14Doctor);row.appendChild(b2);
    card.appendChild(row);
    left.appendChild(card);
  }
  bwRenderWeights();
}
if(document.readyState==="loading"){
  document.addEventListener("DOMContentLoaded",bwBuild);
}else{
  bwBuild();
}
setInterval(bwRenderWeights,60000);
})();
/*BW14-END*/

</script>
<script>
/* ============================================================
   v1.4.0 — Worker A (front-end): #113 barge-in বোতাম, #75 কথা থেকে
   কাজ ধরা, #700 দৈনিক কঠিন প্রশ্ন, #109 রিমাইন্ডার নিয়ম (UI + ইঞ্জিন)
   ============================================================ */
(function(){
'use strict';
function $(id){return document.getElementById(id)}
function v14Speaking(){try{return !!speakingNow}catch(e){return false}}
function v14Exam(){try{return !!examActive}catch(e){return false}}
window.v14StopSpeak=function(){try{stopSpeak()}catch(e){}};

/* ---------- ছোট style ---------- */
var st=document.createElement('style');
st.textContent=
 '#v14stopbtn{position:fixed;right:16px;bottom:96px;z-index:90;display:none;align-items:center;gap:6px;'+
 'padding:12px 18px;border-radius:999px;font-size:15px;font-weight:600;background:#c0392b;color:#fff;'+
 'border:1px solid #e74c3c;box-shadow:0 4px 18px rgba(0,0,0,.45);cursor:pointer}'+
 '#v14stopbtn.on{display:inline-flex}'+
 '.v14chip{margin:4px 0 10px 44px;padding:10px 12px;background:var(--panel2);border:1px solid var(--accent);'+
 'border-radius:10px;font-size:14px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;max-width:92%}'+
 '.v14chip button{padding:5px 12px;font-size:13px}'+
 '#v14dailyq{border:1px solid var(--accent);background:var(--panel);border-radius:var(--radius);'+
 'padding:12px 14px;margin-bottom:10px;box-shadow:var(--shadow);font-size:14.5px}'+
 '#v14dailyq .opts{margin:8px 0 8px 20px;line-height:1.9}'+
 '#v14dailyq .opt-right{background:rgba(46,204,113,.25);border-radius:6px;padding:1px 8px;font-weight:700}'+
 '#v14dailyq button{padding:6px 14px;font-size:13.5px;margin-right:8px}'+
 '.v14remrow{display:flex;gap:6px;align-items:flex-start;padding:7px 0;border-bottom:1px solid var(--line);font-size:14px}'+
 '.v14remrow span{flex:1;min-width:0;white-space:pre-wrap;word-break:break-word}'+
 '.v14remrow button{flex:none;padding:3px 8px;font-size:12px}';
document.head.appendChild(st);

/* ---------- #113: বলার সময় সবসময়-দেখা ⏹ থামো বোতাম ---------- */
var stopBtn=document.createElement('button');
stopBtn.id='v14stopbtn';stopBtn.type='button';stopBtn.textContent='⏹ থামো';
stopBtn.title='Sokhi-র বলা এখনই থামাও';
stopBtn.addEventListener('click',function(){window.v14StopSpeak()});
document.body.appendChild(stopBtn);
setInterval(function(){
 stopBtn.classList.toggle('on',v14Speaking());
},300);

/* ---------- #75: কথা থেকে কাজ ধরা ---------- */
var V14_INTENT=['করতে হবে','করা লাগবে','করতে চাই','কিনতে হবে','কিনতে চাই','যেতে হবে','দিতে হবে','নিতে হবে','আনতে হবে'];
var V14_TIME=['কাল','আগামীকাল','পরশু','শুক্রবার','শনিবার','রবিবার','সোমবার','মঙ্গলবার','বুধবার','বৃহস্পতিবার','সকালে','বিকেলে','রাতে','tomorrow'];
var V14_INTENT_EN=['need to','have to','buy'];
var v14Proposed={};
var v14ChipEl=null;
function v14HasAny(s,list){for(var i=0;i<list.length;i++){if(s.indexOf(list[i])!==-1)return true}return false}
window.v14TaskDetect=function(t){
 try{
  if(v14Exam())return;
  var raw=String(t||'').trim();if(!raw)return;
  if(v14Proposed[raw])return;
  if(v14ChipEl&&v14ChipEl.parentNode)return; /* একবারে একটাই chip */
  var low=raw.toLowerCase();
  var intent=v14HasAny(raw,V14_INTENT)||v14HasAny(low,V14_INTENT_EN);
  if(!intent)return;
  var timed=v14HasAny(raw,V14_TIME)||low.indexOf('tomorrow')!==-1;
  if(!timed&&raw.length<=12)return;
  v14Proposed[raw]=1;
  var chat=$('chat');if(!chat)return;
  var chip=document.createElement('div');chip.className='v14chip';
  var label=document.createElement('span');
  label.textContent='📝 এটা কাজে যোগ করবো? — '+(raw.length>60?raw.slice(0,60)+'…':raw);
  var yes=document.createElement('button');yes.type='button';yes.textContent='যোগ করো';
  var no=document.createElement('button');no.type='button';no.textContent='না';
  no.addEventListener('click',function(){chip.remove();if(v14ChipEl===chip)v14ChipEl=null});
  yes.addEventListener('click',async function(){
   yes.disabled=true;no.disabled=true;
   try{await api('/api/tasks',{text:raw});
    chip.textContent='✓ যোগ হয়েছে';
    setTimeout(function(){chip.remove();if(v14ChipEl===chip)v14ChipEl=null},4000);
   }catch(e){yes.disabled=false;no.disabled=false;label.textContent='যোগ করা গেল না — আবার চেষ্টা করো: '+raw}
  });
  chip.appendChild(label);chip.appendChild(yes);chip.appendChild(no);
  chat.appendChild(chip);v14ChipEl=chip;
  if(typeof scrollChatToBottom==='function')scrollChatToBottom();
 }catch(e){}
};

/* ---------- #700: দৈনিক কঠিন প্রশ্ন ---------- */
var v14DailyTried=false;
async function v14DailyQ(){
 if(v14DailyTried)return;v14DailyTried=true;
 var j=null;
 try{j=await apiGet('/api/dailyq')}catch(e){return}
 if(!j||!j.ok||j.done||!j.question)return;
 var chat=$('chat');if(!chat)return;
 if($('v14dailyq'))return;
 var q=j.question;
 var card=document.createElement('div');card.id='v14dailyq';
 var head=document.createElement('div');head.className='secttl';
 head.textContent='🌟 আজকের কঠিন প্রশ্ন ('+(q.topic||'সাধারণ')+')';
 card.appendChild(head);
 var qt=document.createElement('div');qt.textContent=q.q||'';card.appendChild(qt);
 var opts=document.createElement('div');opts.className='opts';
 var optEls=[];
 (q.options||[]).forEach(function(o,i){
  var d=document.createElement('div');d.textContent=(i+1)+'. '+o;opts.appendChild(d);optEls.push(d)});
 card.appendChild(opts);
 var btnRow=document.createElement('div');
 var reveal=document.createElement('button');reveal.type='button';reveal.textContent='উত্তর দেখো';
 var skip=document.createElement('button');skip.type='button';skip.textContent='আজ থাক';
 reveal.addEventListener('click',async function(){
  reveal.disabled=true;skip.disabled=true;
  try{
   var r=await api('/api/dailyq',{action:'reveal'});
   if(r&&r.ok){
    if(typeof r.answer_index==='number'&&optEls[r.answer_index])optEls[r.answer_index].classList.add('opt-right');
    var ans=document.createElement('div');ans.style.marginTop='8px';ans.style.fontWeight='600';
    ans.textContent='✓ সঠিক উত্তর: '+(r.answer_text||((q.options||[])[r.answer_index]||''));
    card.appendChild(ans);
    var done=document.createElement('div');done.className='small';done.textContent='আজকের প্রশ্ন শেষ — কাল আবার নতুন প্রশ্ন আসবে।';
    card.appendChild(done);
   }else{reveal.disabled=false;skip.disabled=false}
  }catch(e){reveal.disabled=false;skip.disabled=false}
 });
 skip.addEventListener('click',async function(){
  skip.disabled=true;reveal.disabled=true;
  try{await api('/api/dailyq',{action:'skip'})}catch(e){}
  card.remove();
 });
 btnRow.appendChild(reveal);btnRow.appendChild(skip);
 card.appendChild(btnRow);
 chat.insertBefore(card,chat.firstChild);
}
setTimeout(v14DailyQ,1800);

/* ---------- #109: রিমাইন্ডার নিয়ম (UI + ফায়ারিং ইঞ্জিন) ---------- */
var V14_DAYS=[['daily','প্রতিদিন'],['sat','শনিবার'],['sun','রবিবার'],['mon','সোমবার'],['tue','মঙ্গলবার'],['wed','বুধবার'],['thu','বৃহস্পতিবার'],['fri','শুক্রবার']];
var V14_DAYNAME={daily:'প্রতিদিন',sat:'শনিবার',sun:'রবিবার',mon:'সোমবার',tue:'মঙ্গলবার',wed:'বুধবার',thu:'বৃহস্পতিবার',fri:'শুক্রবার'};
var V14_WDKEY=['sun','mon','tue','wed','thu','fri','sat'];
var v14RemRules=[];
var v14RemLastLoad=0;
function v14DaysLabel(days){
 if(!days||days==='daily')return 'প্রতিদিন';
 return String(days).split(',').map(function(d){return V14_DAYNAME[d.trim()]||d.trim()}).join(', ')}
function v14RenderReminders(){
 var list=$('v14remlist');if(!list)return;
 list.innerHTML='';
 if(!v14RemRules.length){
  var d=document.createElement('div');d.className='small';d.textContent='এখনো কোনো রিমাইন্ডার নিয়ম নেই।';list.appendChild(d);return}
 v14RemRules.forEach(function(r){
  var row=document.createElement('div');row.className='v14remrow';
  var sp=document.createElement('span');
  sp.textContent='⏰ '+(r.text||'')+' — '+(r.time||'')+' ('+v14DaysLabel(r.days)+')';
  var del=document.createElement('button');del.type='button';del.textContent='✕';
  del.title='মুছে ফেলো';
  del.addEventListener('click',async function(){
   try{var j=await api('/api/reminders',{action:'delete',id:r.id});
    if(j&&j.rules)v14RemRules=j.rules;else await v14LoadReminders(true);
   }catch(e){await v14LoadReminders(true)}
   v14RenderReminders()});
  row.appendChild(sp);row.appendChild(del);list.appendChild(row)})}
async function v14LoadReminders(force){
 var now=Date.now();
 if(!force&&now-v14RemLastLoad<800)return;
 v14RemLastLoad=now;
 try{var j=await apiGet('/api/reminders');
  if(j&&j.ok&&Array.isArray(j.rules))v14RemRules=j.rules;
 }catch(e){}
 v14RenderReminders()}
function v14BuildReminders(){
 var pane=$('pane-tasks');if(!pane||$('v14remsec'))return;
 var sec=document.createElement('div');sec.id='v14remsec';sec.style.marginTop='16px';
 var ttl=document.createElement('div');ttl.className='secttl';ttl.textContent='⏰ রিমাইন্ডার নিয়ম';sec.appendChild(ttl);
 var list=document.createElement('div');list.id='v14remlist';sec.appendChild(list);
 var form=document.createElement('div');form.style.cssText='display:flex;gap:6px;flex-wrap:wrap;margin-top:8px';
 var txt=document.createElement('input');txt.id='v14remtext';txt.type='text';txt.placeholder='রিমাইন্ডারের কথা লেখো…';txt.style.flex='1';txt.style.minWidth='140px';
 var tim=document.createElement('input');tim.id='v14remtime';tim.type='time';tim.value='08:00';
 var sel=document.createElement('select');sel.id='v14remdays';
 V14_DAYS.forEach(function(pair){var o=document.createElement('option');o.value=pair[0];o.textContent=pair[1];sel.appendChild(o)});
 var addB=document.createElement('button');addB.type='button';addB.textContent='যোগ করো';
 addB.addEventListener('click',async function(){
  var v=txt.value.trim();if(!v)return;
  var tm=tim.value||'08:00';
  try{var j=await api('/api/reminders',{action:'add',text:v,time:tm,days:sel.value});
   if(j&&j.rules)v14RemRules=j.rules;else await v14LoadReminders(true);
   txt.value='';v14RenderReminders();
  }catch(e){try{setStatus('রিমাইন্ডার যোগ করা গেল না')}catch(e2){}}
 });
 form.appendChild(txt);form.appendChild(tim);form.appendChild(sel);form.appendChild(addB);
 sec.appendChild(form);
 var hint=document.createElement('div');hint.className='small';hint.style.marginTop='6px';
 hint.textContent='সময় হলে Sokhi চ্যাটে জানাবে আর গলায় বলবে (শান্ত সময়ে শুধু চ্যাটে)।';
 sec.appendChild(hint);
 pane.appendChild(sec);
 v14RenderReminders()}
/* Tasks ট্যাব খুললেই রিমাইন্ডার লোড — showTab মোড়ক + বোতাম listener (দুটোই, dedupe আছে) */
try{
 var origShowTab=window.showTab;
 if(typeof origShowTab==='function'){
  window.showTab=function(name){
   origShowTab(name);
   if(name==='tasks'){v14BuildReminders();v14LoadReminders(false)}}}
}catch(e){}
var tb=$('tabbtn-tasks');
if(tb)tb.addEventListener('click',function(){v14BuildReminders();v14LoadReminders(false)});
v14BuildReminders();
v14LoadReminders(true);
setInterval(v14LoadReminders,300000);
/* ফায়ারিং ইঞ্জিন: প্রতি ৩০ সেকেন্ডে যাচাই */
function v14RemTick(){
 try{
  if(!v14RemRules.length)return;
  var now=new Date();
  var hhmm=('0'+now.getHours()).slice(-2)+':'+('0'+now.getMinutes()).slice(-2);
  var wd=V14_WDKEY[now.getDay()];
  var dateStr=now.getFullYear()+'-'+('0'+(now.getMonth()+1)).slice(-2)+'-'+('0'+now.getDate()).slice(-2);
  v14RemRules.forEach(function(r){
   if(!r||r.time!==hhmm)return;
   var days=r.days||'daily';
   if(days!=='daily'){
    var parts=String(days).split(',').map(function(d){return d.trim()});
    if(parts.indexOf(wd)===-1)return}
   var key='v14rem_fired_'+r.id+'_'+dateStr;
   try{if(localStorage.getItem(key))return;localStorage.setItem(key,'1')}catch(e){}
   var msg='⏰ রিমাইন্ডার: '+(r.text||'');
   try{if(typeof add==='function')add(msg,'sokhi')}catch(e){}
   var quiet=false;
   try{quiet=!!(window.sokhiQuietNow&&window.sokhiQuietNow())}catch(e){}
   if(!quiet){try{if(typeof speak==='function')speak('রিমাইন্ডার: '+(r.text||''))}catch(e){}}
  });
 }catch(e){}
}
setInterval(v14RemTick,30000);
})();
</script>
</body></html>"""


_panels_cache = {"ts": 0, "weather": "", "news": ""}


def panels_data():
    if time.time() - _panels_cache["ts"] > 600 or not _panels_cache["weather"]:
        try:
            _panels_cache["weather"] = get_weather(get_config().get("city", "Dhaka"))
        except Exception:
            pass
        try:
            _panels_cache["news"] = get_news(5)
        except Exception:
            pass
        _panels_cache["ts"] = time.time()
    _pd = {"weather_text": apply_call_name(_panels_cache["weather"]),
           "news_text": apply_call_name(_panels_cache["news"])}
    try:
        _pd.update(fullforms_panels())
    except Exception:
        pass
    return _pd


# --------------------------------------------------------------- server

_daily_release_lock = threading.Lock()


def _kick_daily_release():
    """daily_release_if_due()-কে background thread-এ চালায় (v1.1 latency
    fix) — দিনের প্রথম chat/status অনুরোধে self-upgrade-এর ভারী কাজ যেন
    উত্তরে দেরি না করে। lock থাকায় একসঙ্গে একটিই রান হয়।"""
    def _run():
        if _daily_release_lock.acquire(blocking=False):
            try:
                daily_release_if_due()
            except Exception:
                pass
            finally:
                _daily_release_lock.release()
    threading.Thread(target=_run, daemon=True).start()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _pin_ok(self):
        # requests from the laptop itself also use the PIN: one simple rule
        return self.headers.get("X-PIN", "") == get_pin()

    def do_GET(self):
        # --- v1.8.0 #47: inline chart SVG (query string থাকে, তাই parse করে)
        _parsed = urllib.parse.urlparse(self.path)
        if _parsed.path == "/api/chart":
            if not self._pin_ok():
                return self._json({"error": "pin"}, 403)
            _qs = urllib.parse.parse_qs(_parsed.query)
            _kind = (_qs.get("kind") or [""])[0].strip()
            _subj = (_qs.get("subject") or [""])[0].strip()
            if _kind == "concept":
                _svg = concept_svg(_subj) if _subj else None
                if not _svg:
                    return self._json({"ok": False, "error": f"{_NO_DATA} — এই বিষয়ের ধারণা-মানচিত্র আঁকার মতো পাঠ পাইনি।"})
                return self._json({"ok": True, "kind": "concept", "title": f"ধারণা-মানচিত্র — {_subj}", "svg": _svg})
            _series = chart_series(_kind)
            if not _series:
                return self._json({"ok": False, "error": f"{_NO_DATA} — চার্ট আঁকার মতো ডেটা পাইনি।"})
            _svg = svg_line_chart(_series) if _kind == "coverage" else svg_bar_chart(_series)
            return self._json({"ok": True, "kind": _kind, "title": _series.get("title", ""), "svg": _svg})
        if self.path in ("/", "/index.html"):
            body = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/api/status":
            if not self._pin_ok():
                return self._json({"error": "pin"}, 403)
            _kick_daily_release()
            ensure_edge_tts()
            mem, ver = get_memory(), get_version()
            caps = load_json(CAPS_FILE, [])
            return self._json({"ok": True, "version": ver["version"],
                               "skills": len(caps) + len(load_plugins()),
                               "interactions": mem["interaction_count"],
                               "facts": len(mem["facts"]),
                               "knowledge": len(load_json(KNOW_FILE, {})),
                               "auto_upgrade": bool(get_config().get("auto_self_upgrade", True)),
                               "voice_engine": tts_engine_status(), "voice_rate": _clamp_voice_rate(get_config().get("voice_rate", 1.0)),
                               "tts_preset": get_config().get("tts_preset", "মিষ্টি"), "tts_voice": get_config().get("tts_voice", "bn-BD-NabanitaNeural"), "browser_voice": get_config().get("browser_voice", ""), "tts_engine": get_config().get("tts_engine", "edge"), "gemini_voice": get_config().get("gemini_voice", "Aoede"), "call_name": get_config().get("call_name", ""), "update_url_set": bool(get_config().get("update_url")), "voice_edge": bool(shutil.which("edge-tts") or shutil.which("edge-tts.exe")), "key_set": bool(get_config().get("gemini_api_key")), "foundation": foundation_status(), "exam_active": exam_active(), "agents_active": sum(1 for j in AGENT_JOBS if j["status"] == "চলছে"), "reply_style": get_config().get("reply_style", "স্বাভাবিক"), "quiet_start": get_config().get("quiet_start", ""), "quiet_end": get_config().get("quiet_end", ""), "reply_language": get_config().get("reply_language", "বাংলা"), "wake_word": bool(get_config().get("wake_word", False)), "echo_guard": bool(get_config().get("echo_guard", True)), "dim_start": get_config().get("dim_start", ""), "dim_end": get_config().get("dim_end", ""), "dim_level": get_config().get("dim_level", 0.6), "gemini_model": get_config().get("gemini_model", "gemini-3.8-flash"), "gemini_model_mode": get_config().get("gemini_model_mode", "auto"), "brain": "smart" if bool(get_config().get("gemini_api_key")) else "offline"})
        if self.path == "/api/memory":
            if not self._pin_ok():
                return self._json({"error": "pin"}, 403)
            _mem = get_memory()
            _mem["fact_weights"] = fact_weights_aligned(_mem.get("facts", []))
            return self._json(_mem)
        if self.path == "/api/agents":
            if not self._pin_ok():
                return self._json({"error": "pin"}, 403)
            return self._json(agent_jobs_public())
        if self.path == "/api/panels":
            if not self._pin_ok():
                return self._json({"error": "pin"}, 403)
            return self._json(panels_data())
        if self.path == "/api/notes":
            if not self._pin_ok():
                return self._json({"error": "pin"}, 403)
            _nf = DATA / "notes.txt"
            return self._json({"text": _nf.read_text(encoding="utf-8") if _nf.exists() else ""})
        if self.path == "/api/tasks":
            if not self._pin_ok():
                return self._json({"error": "pin"}, 403)
            return self._json(tasks_api(None))
        if self.path == "/api/rules":
            if not self._pin_ok():
                return self._json({"error": "pin"}, 403)
            return self._json({"text": rules_text()})
        if self.path == "/api/whiteboard":
            if not self._pin_ok():
                return self._json({"error": "pin"}, 403)
            return self._json({"lines": wb_lines()})
        if self.path == "/api/convos":
            if not self._pin_ok():
                return self._json({"error": "pin"}, 403)
            _store = convos_load()
            return self._json({"active": _store.get("active"),
                               "items": [{"id": it.get("id"), "title": it.get("title", ""), "pinned": bool(it.get("pinned")),
                                          "updated": it.get("updated", 0),
                                          "count": len(it.get("messages", []))}
                                         for it in _store.get("items", [])
                                         if isinstance(it, dict)]})
        if self.path == "/api/dailyq":
            if not self._pin_ok():
                return self._json({"error": "pin"}, 403)
            return self._json(dailyq_get())
        if self.path == "/api/reminders":
            if not self._pin_ok():
                return self._json({"error": "pin"}, 403)
            return self._json(reminders_api({"action": "list"}))
        if self.path == "/api/board":
            if not self._pin_ok():
                return self._json({"error": "pin"}, 403)
            return self._json(board_api())
        if self.path == "/api/doctor":
            if not self._pin_ok():
                return self._json({"error": "pin"}, 403)
            return self._json(doctor_report())
        if self.path == "/api/dailycard":
            if not self._pin_ok():
                return self._json({"error": "pin"}, 403)
            return self._json(daily_card())
        if self.path == "/api/bazaar":
            if not self._pin_ok():
                return self._json({"error": "pin"}, 403)
            return self._json(bazaar_api(None))
        if self.path == "/api/wins":
            if not self._pin_ok():
                return self._json({"error": "pin"}, 403)
            return self._json(wins_api(None))
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path not in ("/api/chat", "/api/settings", "/api/testkey", "/api/tts", "/api/tts_test", "/api/agents", "/api/exam", "/api/notes", "/api/tasks", "/api/rules", "/api/whiteboard", "/api/convos", "/api/memory", "/api/feedback", "/api/pins", "/api/backup", "/api/dailyq", "/api/reminders", "/api/bazaar", "/api/wins"):
            return self._json({"error": "not found"}, 404)
        if not self._pin_ok():
            return self._json({"error": "pin"}, 403)
        try:
            n = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except Exception:
            data = {}
        if self.path == "/api/tts_test":
            ensure_edge_tts()
            _tpref = (get_config().get("tts_engine") or "edge").strip().lower()
            if _tpref == "browser":
                return self._json({"ok": True, "engine": "browser", "voice_engine": tts_engine_status(), "voice": get_config().get("browser_voice", ""), "note": "ব্রাউজারের গলা বেছে দেওয়া — টেস্টের শব্দ ব্রাউজার থেকেই আসবে"})
            audio = make_tts_audio("আসসালামু আলাইকুম, আমি সখী।")
            if audio:
                _eng = VOICE_STATE.get("engine", "")
                _vce = (get_config().get("gemini_voice") or "Aoede") if _eng == "gemini" else voice_identity()["voice"]
                return self._json({"ok": True, "engine": _eng, "voice_engine": tts_engine_status(), "voice": _vce, "rate": VOICE_STATE.get("rate", ""), "pitch": VOICE_STATE.get("pitch", ""), "note": VOICE_STATE.get("note", "")})
            return self._json({"ok": False, "engine": VOICE_STATE.get("engine", ""), "voice_engine": tts_engine_status(), "error": VOICE_STATE.get("error", "অজানা সমস্যা"), "note": VOICE_STATE.get("note", "")})
        if self.path == "/api/tts":
            audio = make_tts_audio(str(data.get("text") or ""), data.get("rate") or None, data.get("pitch") or None)
            if not audio:
                return self._json({"ok": False, "error": "সার্ভারের গলা আসেনি — ব্রাউজারের গলা চলবে", "note": VOICE_STATE.get("note", "")}, 500)
            body_bytes = audio.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav" if audio.suffix == ".wav" else "audio/mpeg")
            self.send_header("Content-Length", str(len(body_bytes)))
            self.end_headers()
            self.wfile.write(body_bytes)
            return
        if self.path == "/api/settings":
            if "reply_style" in data:
                _rs = str(data.get("reply_style") or "").strip()
                if _rs not in ("সংক্ষেপ", "স্বাভাবিক", "বিস্তারিত"):
                    return self._json({"ok": False, "error": "উত্তরের ধরন হতে হবে: সংক্ষেপ, স্বাভাবিক বা বিস্তারিত।"})
                cfg = get_config(); cfg["reply_style"] = _rs; save_config(cfg)
                return self._json({"ok": True, "reply_style": _rs})
            if "quiet_start" in data or "quiet_end" in data:
                cfg = get_config()
                for _qk in ("quiet_start", "quiet_end"):
                    if _qk in data:
                        _qv = str(data.get(_qk) or "").strip()
                        if _qv and not re.match(r"^\d{2}:\d{2}$", _qv):
                            return self._json({"ok": False, "error": "সময়টা HH:MM আকারে দাও, যেমন 23:00।"})
                        cfg[_qk] = _qv
                save_config(cfg)
                return self._json({"ok": True, "quiet_start": cfg.get("quiet_start", ""), "quiet_end": cfg.get("quiet_end", "")})
            if "reply_language" in data:
                _rl = str(data.get("reply_language") or "").strip()
                if _rl not in ("বাংলা", "Banglish", "English"):
                    return self._json({"ok": False, "error": "উত্তরের ভাষা হতে হবে: বাংলা, Banglish বা English।"})
                cfg = get_config(); cfg["reply_language"] = _rl; save_config(cfg)
                return self._json({"ok": True, "reply_language": _rl})
            if "wake_word" in data:
                cfg = get_config(); cfg["wake_word"] = bool(data.get("wake_word")); save_config(cfg)
                return self._json({"ok": True, "wake_word": cfg["wake_word"]})
            if "echo_guard" in data:
                cfg = get_config(); cfg["echo_guard"] = bool(data.get("echo_guard")); save_config(cfg)
                return self._json({"ok": True, "echo_guard": cfg["echo_guard"]})
            if "dim_start" in data or "dim_end" in data:
                cfg = get_config()
                for _dk in ("dim_start", "dim_end"):
                    if _dk in data:
                        _dv = str(data.get(_dk) or "").strip()
                        if _dv and not re.match(r"^\d{2}:\d{2}$", _dv):
                            return self._json({"ok": False, "error": "সময়টা HH:MM আকারে দাও, যেমন 23:00।"})
                        cfg[_dk] = _dv
                # the settings page sends dim_level in the SAME request —
                # handle it here too or it would be dropped by this return.
                if "dim_level" in data:
                    try:
                        cfg["dim_level"] = max(0.3, min(1.0, float(data.get("dim_level"))))
                    except Exception:
                        return self._json({"ok": False, "error": "dim_level সংখ্যা হতে হবে (0.3–1.0)।"})
                save_config(cfg)
                return self._json({"ok": True, "dim_start": cfg.get("dim_start", ""), "dim_end": cfg.get("dim_end", ""), "dim_level": cfg.get("dim_level", 0.6)})
            if "dim_level" in data:
                try:
                    _dl = float(data.get("dim_level"))
                except Exception:
                    return self._json({"ok": False, "error": "dim_level সংখ্যা হতে হবে (0.3–1.0)।"})
                _dl = max(0.3, min(1.0, _dl))
                cfg = get_config(); cfg["dim_level"] = _dl; save_config(cfg)
                return self._json({"ok": True, "dim_level": _dl})
            if "gemini_model" in data:
                _gm = str(data.get("gemini_model") or "").strip()
                cfg = get_config()
                if _gm == "auto":
                    cfg["gemini_model_mode"] = "auto"
                    save_config(cfg)
                    return self._json({"ok": True, "gemini_model": cfg.get("gemini_model", "gemini-3.8-flash"), "gemini_model_mode": "auto"})
                if len(_gm) > 80 or not re.match(r"^gemini[A-Za-z0-9._\-]{0,74}$", _gm):
                    return self._json({"ok": False, "error": "মডেলের নামটা ঠিক লাগছে না — 'gemini' দিয়ে শুরু হতে হবে, শুধু ইংরেজি অক্ষর/সংখ্যা/./-/_ চলবে, আর সর্বোচ্চ ৮০ অক্ষর। যেমন: gemini-2.5-flash"})
                cfg["gemini_model"] = _gm
                cfg["gemini_model_mode"] = "custom"
                save_config(cfg)
                return self._json({"ok": True, "gemini_model": _gm, "gemini_model_mode": "custom"})
            preset = str(data.get("tts_preset") or "")
            presets = {"মিষ্টি": ("-3%", "+4%"), "স্বাভাবিক": ("0%", "+1%"), "প্রাণবন্ত": ("+5%", "+5%")}
            if preset in presets:
                cfg = get_config()
                cfg["tts_preset"] = preset
                cfg["tts_rate"], cfg["tts_pitch"] = presets[preset]
                save_config(cfg)
                return self._json({"ok": True, "tts_preset": preset})
            if "voice_rate" in data:
                try:
                    vr = _clamp_voice_rate(float(data.get("voice_rate")))
                except Exception:
                    return self._json({"ok": False, "error": "voice_rate সংখ্যা হতে হবে (0.8–1.2)"})
                cfg = get_config()
                cfg["voice_rate"] = vr
                save_config(cfg)
                return self._json({"ok": True, "voice_rate": vr})
            if "tts_voice" in data:
                _ok, _res = validate_tts_voice(data.get("tts_voice"))
                if not _ok:
                    return self._json({"ok": False, "error": _res})
                cfg = get_config(); cfg["tts_voice"] = _res; save_config(cfg)
                return self._json({"ok": True, "tts_voice": _res})
            if "browser_voice" in data:
                _ok, _res = validate_browser_voice(data.get("browser_voice"))
                if not _ok:
                    return self._json({"ok": False, "error": _res})
                cfg = get_config(); cfg["browser_voice"] = _res; save_config(cfg)
                return self._json({"ok": True, "browser_voice": _res})
            if "tts_engine" in data:
                _ok, _res = validate_tts_engine(data.get("tts_engine"))
                if not _ok:
                    return self._json({"ok": False, "error": _res})
                cfg = get_config(); cfg["tts_engine"] = _res; save_config(cfg)
                return self._json({"ok": True, "tts_engine": _res})
            if "gemini_voice" in data:
                _ok, _res = validate_gemini_voice(data.get("gemini_voice"))
                if not _ok:
                    return self._json({"ok": False, "error": _res})
                cfg = get_config(); cfg["gemini_voice"] = _res; save_config(cfg)
                return self._json({"ok": True, "gemini_voice": _res})
            if isinstance(data.get("call_name"), str):
                cfg = get_config()
                cfg["call_name"] = data["call_name"].strip()[:40]
                save_config(cfg)
                return self._json({"ok": True, "call_name": cfg["call_name"]})
            if isinstance(data.get("update_url"), str):
                cfg = get_config()
                cfg["update_url"] = data["update_url"].strip()
                save_config(cfg)
                return self._json({"ok": True, "update_url_set": bool(cfg["update_url"])})
            # Bhaiya pastes his own free Gemini key here; it is saved ONLY in
            # data/config.json on his own laptop and never shown back.
            # An EMPTY save never wipes an existing key (v0.3 fix) — clearing
            # needs the separate explicit clear_key action.
            cfg = get_config()
            new_key = str(data.get("gemini_api_key") or "").strip()
            if new_key:
                cfg["gemini_api_key"] = new_key
                log_change("Settings থেকে Gemini key বসানো হয়েছে")
            elif data.get("clear_key"):
                cfg["gemini_api_key"] = ""
                log_change("Settings থেকে Gemini key মুছে ফেলা হয়েছে")
            if "city" in data and str(data.get("city") or "").strip():
                cfg["city"] = str(data.get("city")).strip()
            save_config(cfg)
            return self._json({"ok": True, "key_set": bool(cfg["gemini_api_key"])})
        if self.path == "/api/testkey":
            if not get_config().get("gemini_api_key"):
                return self._json({"ok": False, "message": "আগে key বসাও ভাইয়া, তারপর টেস্ট করো।"})
            out = ask_gemini("এক লাইনে বলো: তুমি কে?", get_memory())
            if out:
                return self._json({"ok": True, "message": "Key কাজ করছে ভাইয়া! Sokhi বলল: " + out})
            err = _last_gemini_error.get("info", "")
            hint = ""
            if "429" in err:
                hint = " মনে হচ্ছে ফ্রি লিমিটে ঠেকেছে (429) — একটু পরে আবার চেষ্টা করো।"
            elif "400" in err or "404" in err:
                hint = " মডেল/key-তে সমস্যা হতে পারে (400/404) — Saba-কে এই লেখাটা পাঠাও।"
            elif "timed out" in err or "urlopen" in err or "Network" in err:
                hint = " নেট সংযোগে সমস্যা মনে হচ্ছে — ল্যাপটপের ইন্টারনেট দেখো।"
            return self._json({"ok": False, "message": "Key দিয়ে সাড়া পাইনি ভাইয়া।" + hint + " (কারিগরি তথ্য: " + (err[:160] or "জানা যায়নি") + ")"})
        if self.path == "/api/agents":
            return self._json(agents_api(data))
        if self.path == "/api/exam":
            return self._json(exam_api(data))
        if self.path == "/api/notes":
            (DATA / "notes.txt").write_text(str(data.get("text") or "")[:20000], encoding="utf-8")
            return self._json({"ok": True})
        if self.path == "/api/tasks":
            return self._json(tasks_api(data))
        if self.path == "/api/bazaar":
            return self._json(bazaar_api(data))
        if self.path == "/api/wins":
            return self._json(wins_api(data))
        if self.path == "/api/rules":
            if data.get("rule"):
                return self._json({"ok": True, "message": rules_add(str(data["rule"])), "text": rules_text()})
            return self._json({"ok": True, "text": rules_text()})
        if self.path == "/api/convos":
            return self._json(convos_api(data))
        if self.path == "/api/memory":
            return self._json(memory_api(data))
        if self.path == "/api/feedback":
            return self._json(feedback_api(data))
        if self.path == "/api/pins":
            return self._json(pins_api(data))
        if self.path == "/api/backup":
            return self._json(backup_api(data))
        if self.path == "/api/dailyq":
            return self._json(dailyq_api(data))
        if self.path == "/api/reminders":
            return self._json(reminders_api(data))
        if self.path == "/api/whiteboard":
            if data.get("action") == "clear":
                wb_clear()
            return self._json({"ok": True, "lines": wb_lines()})
        # /api/chat (v1.1, problem 4): measure the whole request and log it.
        # NOTE: no TTS is built on this path — voice is a separate /api/tts
        # call made by the page AFTER the text reply arrives, so the text
        # is never blocked waiting for audio.
        _chat_t0 = time.perf_counter()
        _kick_daily_release()
        _msg = data.get("message", "") or ""
        _regen = bool(data.get("regenerate"))
        _image_raw = data.get("image")
        _extra = {}
        if _regen:
            _store = convos_load()
            _act = _convo_find(_store, _store.get("active")) or convo_active()
            _msgs = list(_act.get("messages", []))
            _last_user_idx = -1
            for _i in range(len(_msgs) - 1, -1, -1):
                if _msgs[_i].get("r") == "user":
                    _last_user_idx = _i
                    break
            if _last_user_idx < 0:
                _err = "আগে একটা প্রশ্ন করো, তারপর আবার উত্তর চাইতে পারবে।"
                return self._json({"ok": False, "error": _err, "reply": _err})
            _last_user = str(_msgs[_last_user_idx].get("t") or "")
            # drop the last model message after that user message
            _kept = []
            _dropped = False
            for _i, _m in enumerate(_msgs):
                if (not _dropped and _i > _last_user_idx
                        and _m.get("r") == "model" and _i == len(_msgs) - 1):
                    _dropped = True
                    continue
                # also handle model not strictly last: drop first model after user if it is the final pair
                _kept.append(_m)
            if not _dropped:
                # fallback: remove the last model entry overall if it follows the user msg
                for _i in range(len(_msgs) - 1, _last_user_idx, -1):
                    if _msgs[_i].get("r") == "model":
                        _kept = _msgs[:_i] + _msgs[_i + 1:]
                        _dropped = True
                        break
            _act["messages"] = _kept
            _act["updated"] = int(time.time())
            _store2 = convos_load()
            _act2 = _convo_find(_store2, _act.get("id"))
            if _act2 is not None:
                _act2["messages"] = _kept
                _act2["updated"] = int(time.time())
                convos_save(_store2)
            _prompt = _last_user
            if _prompt.startswith("[ছবি] "):
                _prompt = _prompt[len("[ছবি] "):]
            reply = apply_call_name(care_suffix(handle_message(_prompt)))
            convo_remember(_prompt, reply)
            _store3 = convos_load()
            _act3 = _convo_find(_store3, _act.get("id")) or convo_active()
            _act3.setdefault("messages", []).append(
                {"r": "model", "t": reply, "ts": int(time.time())})
            _act3["updated"] = int(time.time())
            convos_save(_store3)
            _extra = {"regenerated": True, "convo_id": _act3.get("id"),
                      "title": _act3.get("title", "")}
        elif _image_raw:
            _img = _parse_image_data_url(_image_raw)
            _prompt = str(_msg).strip() or "এই ছবিটা দেখে সহজ বাংলায় বুঝিয়ে বলো।"
            _saved = "[ছবি] " + str(_msg)
            if not (get_config().get("gemini_api_key") or "").strip():
                reply = ("ছবিটা বুঝতে হলে আগে সেটিংসে ফ্রি Gemini key বসাতে হবে। "
                         "key বসালেই ছবি দেখে উত্তর দিতে পারব।")
                reply = apply_call_name(reply)
            elif _img is None:
                reply = apply_call_name("ছবিটা ঠিকমতো পাইনি — আবার পাঠিয়ে দেখো।")
            else:
                _smart = ask_gemini(_prompt, get_memory(), image=_img)
                if _smart:
                    reply = apply_call_name(care_suffix(_smart))
                else:
                    reply = apply_call_name(
                        "ছবিটা দেখে এখন উত্তর দিতে পারলাম না — নেট বা ফ্রি লিমিটের সমস্যা হতে পারে, একটু পরে আবার চেষ্টা করো।")
            convo_remember(_saved, reply)
            _act = convo_append(_saved, reply)
            _extra = {"convo_id": _act.get("id"), "title": _act.get("title", "")}
        else:
            reply = apply_call_name(care_suffix(handle_message(_msg)))
            convo_remember(_msg, reply)
            _act = convo_append(_msg, reply)
            _extra = {"convo_id": _act.get("id"), "title": _act.get("title", "")}
        _chat_ms = int((time.perf_counter() - _chat_t0) * 1000)
        try:
            with (DATA / "latency.log").open("a", encoding="utf-8") as _lf:
                _lf.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                          f"/api/chat ms={_chat_ms} "
                          f"gemini_ms={LAST_LATENCY.get('ms')} "
                          f"model={LAST_LATENCY.get('model')}\n")
        except Exception:
            pass
        _resp = {"reply": reply, "ms": _chat_ms}
        _resp.update(_extra)
        self._json(_resp)


def local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


APP_VERSION = "1.9.2"


def main():
    get_prompt()
    ver = get_version()
    if ver["version"] < APP_VERSION:
        # v0.2 upgrade: keep ALL of Bhaiya's data (memory, PIN, plugins) —
        # only the version number moves up.
        ver["version"] = APP_VERSION
        save_json(VERSION_FILE, ver)
        # v0.4: teach existing installs the new Bangla-answer rules (once)
        prompt_now = PROMPT_FILE.read_text(encoding="utf-8") if PROMPT_FILE.exists() else ""
        if "বাংলা উত্তরের নিয়ম" not in prompt_now:
            with PROMPT_FILE.open("a", encoding="utf-8") as fh:
                fh.write(BANGLA_RULES)
            log_change("প্রম্পটে বাংলা উত্তরের নতুন নিয়ম যোগ হলো (v0.4)")
        if "যত্নের নিয়ম" not in prompt_now:
            with PROMPT_FILE.open("a", encoding="utf-8") as fh:
                fh.write(CARE_RULES)
            log_change("প্রম্পটে যত্নের নিয়ম যোগ হলো (v0.5) — সঙ্গীর মতো উষ্ণ, যত্নশীল টোন")
        if "v1.0 নিয়ম" not in prompt_now:
            with PROMPT_FILE.open("a", encoding="utf-8") as fh:
                fh.write(V1_RULES)
            log_change("প্রম্পটে v1.0 নিয়ম যোগ হলো — এজেন্ট দল, শিক্ষক মোড, নিজের বসানো নিয়ম")
        register_capability("agents", "এজেন্ট দল: গবেষক, খবর, পড়া-সহকারী, PC-সহকারী (background কাজ + report-back)")
        register_capability("teacher", "শিক্ষক মোড (সব বিষয়) + সময় ধরে মক টেস্ট + হোয়াইটবোর্ড")
        register_capability("pc-pack-n8", "N8 দৈনন্দিন PC কমান্ড প্যাক (১২টি)")
        register_capability("rules-n13", "কথা বলে নিয়ম বসানো ও স্কিল-খসড়া অনুমোদন")
        register_capability("fullforms-v11", "F1 world model, F2 আগাম-প্রস্তুতি, F3 GUI computer-use (গেটসহ), F4 প্রকল্প, F6 growth diary, F7 রাতের গবেষণা, F8 prediction, N10 কোডিং এজেন্ট, N11 নথি/রিপোর্ট, bridge (Desktop দিক)")
        # v1.2.0 migration: conversations store — seed the first
        # conversation from the old single convo buffer (convo.json).
        try:
            if not CONVERSATIONS_FILE.exists():
                _buf = convo_load()
                _now_ts = int(time.time())
                _seed_msgs = [{"r": it.get("r", "user"), "t": it.get("t", ""),
                               "ts": int(it.get("ts") or _now_ts)}
                              for it in _buf if isinstance(it, dict)]
                _seed = {"id": _new_convo_id(), "title": "আগের কথোপকথন",
                         "created": _now_ts, "updated": _now_ts,
                         "messages": _seed_msgs}
                convos_save({"active": _seed["id"], "items": [_seed]})
                log_change("v1.2.0: পুরোনো কথোপকথন নতুন কথোপকথন-ভান্ডারে আনা হলো")
        except Exception:
            pass
        register_capability("pro-v12", "Professional & Comfortable: একাধিক কথোপকথন, regenerate, স্মৃতি-দর্শক, ছবি-প্রশ্ন, উত্তর-দৈর্ঘ্য পছন্দ")
        log_change("আপগ্রেড: v1.2.0 — একাধিক কথোপকথন ও খোঁজা/নাম বদল/মোছা, আবার উত্তর (regenerate), বার্তা edit-resend (truncate), স্মৃতি দেখা/মোছা/যোগ, ছবি পাঠিয়ে প্রশ্ন (Gemini vision), উত্তর-দৈর্ঘ্য পছন্দ ও quiet hours সেটিং, উত্তর রেটিং সেভ")
        log_change(f"আপগ্রেড: v{APP_VERSION} — professional UI polish + স্থির গ্রিড/প্যানেল-স্ক্রল/auto-scroll, গলার গতি ঠিক (preset পুনঃসামঞ্জস্য + মোট slowdown cap −12% + গতি স্লাইডার) ও Edge নির্ভরযোগ্যতা, reply দ্রুত (fast-first মডেল + timeout 12s + daily-release background-এ), F1–F8/N10/N11 পূর্ণ রূপ, bridge Desktop প্রোটোকল")
        register_capability("v13-parked", "ভাষা পছন্দ (বাংলা/Banglish/English), বার্তা ও কথোপকথন pin, backup/restore, wake word, রাতের auto-dim, sync ফাইল")
        log_change("আপগ্রেড: v1.3.0 — parked ৬টি: উত্তরের ভাষা পছন্দ, pin (বার্তা + কথোপকথন), সব কথোপকথন backup/restore, wake word 'Sokhi', রাতের auto-dim, বহু-ডিভাইস sync (ফাইল-ভিত্তিক)")
        register_capability("v18-deferred3", "ছবি/চার্ট উত্তর (inline SVG), Gemini মডেল বাছাই, কণ্ঠ বাছাই (Edge + ব্রাউজার) ও কণ্ঠ পরীক্ষা")
        log_change("আপগ্রেড: v1.8.0 — deferred ৩টি: #47 আসল ডেটা থেকে inline SVG চার্ট/ধারণা-মানচিত্র, #49 Gemini মডেল বাছাই (auto/custom + fallback নোটিশ), #50 কণ্ঠ বাছাই (Edge নাবনিতা/প্রদীপ + ব্রাউজারের গলা) ও কণ্ঠ পরীক্ষা বোতাম")
        register_capability("v19-elite", "ELITE প্যাক: ভুলের খরচ/অগ্রগতির গ্রাফ/অভিক্ষেপ বিশ্লেষণ, ফাঁদ ও বাদ-দেওয়ার অনুশীলন, চাপ-সিমুলেশন, ক্যাম্পেইন পরিকল্পক ও মাইলফলক, ইঞ্জিন-রেডি প্যানেল, রিভিশন সূচি/পকেট সার/দ্বৈত মূল্যায়ন/সাহস বার্তা")
        log_change("আপগ্রেড: v1.9.0 — ELITE ব্যাচ: #763/#764/#765 বিশ্লেষণ, #755/#756/#759 প্রশিক্ষণ ও চাপ-সিমুলেশন, #766/#662/#767/#769/#770/#781/#782/#783/#784 পরিকল্পনা, ইঞ্জিন-রেডি #754/#757/#760/#761/#762/#768/#771/#776/#778/#779/#780, সুইপ #667/#703/#716/#729/#753")
        register_capability("v191-echoguard", "Echo guard: স্পিকার থেকে নিজের কণ্ঠ মাইকে ফিরে এলে চিনে ফেলে দেয় — লাইভ মোডে নিজে নিজেকে উত্তর দেয় না; আসল barge-in আগের মতোই; সেটিংসে টগল (ডিফল্ট চালু)")
        log_change("আপগ্রেড: v1.9.1 — বাগ-ফিক্স: লাইভ মোডে Sokhi নিজের বলা কথা স্পিকার→মাইক echo-তে শুনে নিজেকেই উত্তর দিত; echo guard যোগ হলো — speak()-এ বলা কথা মনে রেখে recognition-ইনপুট মিলিয়ে ফেলে দেয় (বলা চলাকালে + শেষের ৮০০ms), barge-in অক্ষত; সেটিংসে 'নিজের কণ্ঠ চেনা (echo guard)' টগল")
        register_capability("v192-voice", "কণ্ঠের ইঞ্জিন বাছাই (Gemini/Edge/ব্রাউজার) + Gemini গলা বাছাই (ডিফল্ট Aoede) + Edge-এ তানিশা গলা; কোন ইঞ্জিন+গলা বলল status/ডাক্তারে পরিষ্কার; Gemini ফলব্যাকে সৎ নোট")
        log_change("আপগ্রেড: v1.9.2 — কণ্ঠের মান: Settings-এ TTS ইঞ্জিন বাছাই (Gemini = সবচেয়ে প্রাণবন্ত, একই ফ্রি key; ব্যর্থ হলে Edge→Google ফলব্যাক + status/ডাক্তারে নোট), Gemini গলা বাছাই (Aoede/Kore/Leda/Callirrhoe/Puck), Edge গলায় তানিশা যোগ, /api/tts এখন WAV-ও দেয় আর ব্যর্থতায় HTTP 500 (পেজের ব্রাউজার-গলা ফলব্যাক সত্যিই চলে)")
    register_capability("core", "কথা, স্মৃতি, PC কমান্ড, আবহাওয়া, খবর, ওয়েব সার্চ")
    daily_release_if_due()
    pin = get_pin()
    print("=" * 58)
    print("  SOKHI DESKTOP — Super Sokhi v" + get_version()["version"])
    print("  সম্পূর্ণ ফ্রি • তোমার তথ্য এই PC-তেই থাকে")
    print("-" * 58)
    print(f"  ল্যাপটপে খোলো : http://localhost:{PORT}")
    print(f"  ফোন থেকে খোলো : http://{local_ip()}:{PORT}   (একই Wi-Fi)")
    print(f"  PIN (গোপন রাখো): {pin}")
    print("=" * 58)
    try:
        webbrowser.open(f"http://localhost:{PORT}")
    except Exception:
        pass
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
