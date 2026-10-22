# -*- coding: utf-8 -*-
"""
Sokhi Desktop — Super Sokhi v0.1 (100% FREE, Python standard library only)
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
    cfg.setdefault("git_auto_push", False)
    cfg.setdefault("city", "Dhaka")
    cfg.setdefault("auto_self_upgrade", True)
    cfg.setdefault("update_url", "")
    cfg.setdefault("tts_voice", "bn-BD-NabanitaNeural")
    cfg.setdefault("call_name", "")
    cfg.setdefault("tts_preset", "মিষ্টি")
    cfg.setdefault("tts_rate", "-8%")
    cfg.setdefault("tts_pitch", "+3%")
    if not CONFIG_FILE.exists():
        save_json(CONFIG_FILE, cfg)
    return cfg


def save_config(cfg):
    save_json(CONFIG_FILE, cfg)


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


def _log_gemini_error(model, err):
    info = f"model={model} error={err}"
    _last_gemini_error["info"] = info
    try:
        with (DATA / "gemini-error.log").open("a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {info}\n")
    except Exception:
        pass


def ask_gemini(user_text, mem):
    """Smart brain — Gemini FREE tier only. Tries the configured model,
    then backup free models, so one model's limit/overload does not drop
    Sokhi back to her offline brain. The real error is logged (never the
    key itself) so failures can be diagnosed instead of guessed."""
    cfg = get_config()
    key = (cfg.get("gemini_api_key") or "").strip()
    if not key:
        return None
    facts = "; ".join(mem.get("facts", [])[-10:])
    likes = ", ".join(mem.get("likes", [])[-10:])
    system = get_prompt() + f"\nমনে থাকা তথ্য: {facts}\nপছন্দ: {likes}"
    _name = (get_config().get("call_name") or "").strip()
    if _name:
        system += (f"\n\n[ডাকনামের নিয়ম — সবচেয়ে জরুরি, আগের সব নির্দেশের উপরে] "
                   f"তুমি তাকে '{_name}' বলে ডাকবে। 'ভাইয়া' বা 'মনির ভাইয়া' কখনোই বলবে না।")
    else:
        system += ("\n\n[ডাকনামের নিয়ম — সবচেয়ে জরুরি, আগের সব নির্দেশের উপরে] "
                   "তুমি তাকে কোনো নামে ডাকবে না — 'ভাইয়া' বা 'মনির ভাইয়া' বলবে না; "
                   "শুধু তুমি-রূপে, নাম ছাড়া কথা বলবে।")
    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"parts": [{"text": user_text}]}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 1024},
    }
    models = []
    for m in (cfg.get("gemini_model", "gemini-3.8-flash"),
              "gemini-3.5-flash", "gemini-2.5-flash", "gemini-3.5-flash-lite"):
        if m and m not in models:
            models.append(m)
    for model in models:
        url = ("https://generativelanguage.googleapis.com/v1beta/models/"
               f"{model}:generateContent")
        req = urllib.request.Request(
            url, data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": key},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode("utf-8"))
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            detail = str(e)
            try:
                if hasattr(e, "read"):
                    detail += " " + e.read().decode("utf-8", errors="ignore")[:200]
            except Exception:
                pass
            _log_gemini_error(model, detail)
            continue
    return None


# ------------------------------------------------------------- TTS voice
# Best free Bangla female voice: Microsoft Edge TTS, bn-BD-NabanitaNeural
# (natural female). Needs the free `edge-tts` tool on Bhaiya's laptop —
# start-sokhi.bat installs it in the background on first run. If it is
# not there, this returns None and the browser's own voice is used.

VOICE_STATE = {"engine": "", "error": ""}


def _tts_edge(text, out_file, rate=None, pitch=None):
    voice = get_config().get("tts_voice", "bn-BD-NabanitaNeural")
    candidates = []
    exe = shutil.which("edge-tts") or shutil.which("edge-tts.exe")
    if exe:
        candidates.append([exe])
    candidates.append([sys.executable, "-m", "edge_tts"])
    last = "edge-tts পাওয়া যায়নি"
    for cmd in candidates:
        try:
            cfg = get_config()
            r = subprocess.run(cmd + ["--voice", voice,
                                      "--rate=" + (rate or cfg.get("tts_rate", "-8%")),
                                      "--pitch=" + (pitch or cfg.get("tts_pitch", "+3%")),
                                      "--text", text, "--write-media", str(out_file)],
                               capture_output=True, text=True, timeout=30)
            if r.returncode == 0 and out_file.exists() and out_file.stat().st_size > 1000:
                return True
            last = (r.stderr or "returncode " + str(r.returncode))[-200:]
        except Exception as e:
            last = str(e)
    raise RuntimeError("Edge গলা: " + last)


def _tts_google(text, out_file, rate=None, pitch=None):
    q = urllib.parse.quote(text)
    url = ("https://translate.google.com/translate_tts?ie=UTF-8&q=" + q +
           "&tl=bn&client=tw-ob")
    data = http_get_bytes(url, 20)
    if len(data) < 2000:
        raise RuntimeError("Google গলা ছোট/খালি সাড়া দিল")
    out_file.write_bytes(data)
    return True


def make_tts_audio(text, rate=None, pitch=None):
    import hashlib
    text = (text or "").strip()[:600]
    if not text:
        return None
    TTS_CACHE.mkdir(parents=True, exist_ok=True)
    cfg = get_config()
    h = hashlib.md5(("v3|" + (rate or cfg.get("tts_rate", "")) + "|" + (pitch or cfg.get("tts_pitch", "")) + "|" + text).encode("utf-8")).hexdigest()
    out_file = TTS_CACHE / f"{h}.mp3"
    if out_file.exists() and out_file.stat().st_size > 1000:
        return out_file
    errors = []
    for engine, fn in (("edge-নাবনিতা", _tts_edge), ("google-বাংলা", _tts_google)):
        try:
            if fn(text, out_file, rate, pitch):
                VOICE_STATE.update(engine=engine, error="")
                return out_file
        except Exception as e:
            errors.append(str(e))
    VOICE_STATE.update(engine="", error=" | ".join(errors)[:300])
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
        if "প্যাটার্ন" in text or "বিশ্লেষণ" in text or "insight" in low:
            return insights_text(mem)
        if "কী কী মনে" in text or "কি মনে রেখেছ" in text or "what do you remember" in low:
            facts = mem["facts"]
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

        # --- learned knowledge first (works even offline, instant)
        cached = knowledge_get(text)
        if cached:
            return cached.get("a", "")

        # --- smart brain (free Gemini) if key exists; learn the answer
        smart = ask_gemini(text, mem)
        if smart:
            knowledge_put(text, smart)
            auto_evolve(mem)
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
<style>
*{box-sizing:border-box} body{margin:0;font-family:'Segoe UI',sans-serif;background:#050a18;color:#dff6ff;min-height:100vh}
header{text-align:center;padding:14px 8px 4px}
.orb{width:110px;height:110px;margin:6px auto;border-radius:50%;
 background:radial-gradient(circle at 35% 35%,#9ff5ff,#22b8f0 45%,#0b3d91 80%);
 box-shadow:0 0 45px #22b8f0aa, inset 0 0 30px #ffffff55;animation:pulse 3s infinite}
@keyframes pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.06)}}
.orb.talking{animation:pulse .6s infinite}
h1{margin:4px 0 0;font-size:22px;letter-spacing:2px}
.sub{opacity:.75;font-size:13px}
#chat{max-width:760px;margin:10px auto;padding:10px;display:flex;flex-direction:column;gap:8px}
.msg{max-width:85%;padding:9px 12px;border-radius:14px;white-space:pre-wrap;line-height:1.45;font-size:15px}
body{padding-bottom:120px}
.me{align-self:flex-end;background:#0b5cad}
.sokhi{align-self:flex-start;background:#0d2138;border:1px solid #1d5f8a}
#bar{position:sticky;bottom:0;background:#050a18ee;padding:10px;display:flex;gap:8px;max-width:760px;margin:0 auto}
input,button{font-size:16px;border-radius:10px;border:1px solid #1d5f8a;background:#0d2138;color:#dff6ff;padding:10px}
input{flex:1} button{cursor:pointer;background:#0b5cad}
.quick{max-width:760px;margin:0 auto;padding:0 10px 70px;display:flex;flex-wrap:wrap;gap:6px}
.quick button{font-size:13px;padding:7px 10px}
#pinbox{max-width:420px;margin:30px auto;background:#0d2138;padding:18px;border-radius:14px;text-align:center}
#gear{position:fixed;top:10px;right:10px;width:42px;height:42px;border-radius:50%;font-size:19px;padding:0;z-index:50;box-shadow:0 0 12px #22b8f066}
#modal{display:none;position:fixed;inset:0;background:#02040acc;z-index:60}
#modal .panel{max-width:430px;margin:60px auto;background:#0d2138;border:1px solid #1d5f8a;border-radius:16px;padding:18px}
#modal .panel h3{margin:0 0 8px;font-size:16px}
.orb.listening{box-shadow:0 0 55px #2effa8aa, inset 0 0 30px #ffffff55;background:radial-gradient(circle at 35% 35%,#c8ffe9,#22f0a0 45%,#0b9159 80%)}
#livebtn.on{background:#a00f2d;border-color:#ff5577}
</style></head><body>
<header><div class="orb" id="orb"></div><h1>SOKHI</h1>
<div class="sub" id="status">তোমার Windows ল্যাপটপের নিজের AI সঙ্গী — সম্পূর্ণ ফ্রি</div></header>

<button id="gear" title="সেটিংস" onclick="document.getElementById('modal').style.display='block'">⚙️</button>
<div id="modal" onclick="if(event.target===this)this.style.display='none'">
 <div class="panel">
  <h3>⚙️ সেটিংস</h3>
  <div style="font-size:14px;margin-bottom:4px">স্মার্ট মাথা (Gemini ফ্রি key)</div>
  <div id="keystat" style="font-size:13px;opacity:.85;margin-bottom:8px">key-র অবস্থা জানা যাচ্ছে…</div>
  <input id="apikey" type="password" placeholder="Gemini key বসাও (শুধু এই ল্যাপটপেই থাকবে)" style="width:100%;margin-bottom:8px">
  <div style="display:flex;gap:6px;flex-wrap:wrap">
   <button onclick="saveKey()">সেভ করো</button>
   <button onclick="testKey()">টেস্ট করো</button>
   <button onclick="clearKey()">key মোছো</button>
  </div>
  <div id="keymsg" style="font-size:13px;margin-top:8px"></div>
  <div style="font-size:12px;opacity:.7;margin-top:6px">key কাউকে পাঠাবে না — এই ঘরে বসালেই শুধু এই ল্যাপটপে সেভ থাকে।</div>
  <hr style="border-color:#1d5f8a;margin:14px 0">
  <div style="font-size:14px;margin-bottom:4px">আমাকে যে নামে ডাকবে</div>
  <div style="display:flex;gap:6px">
   <input id="callname" type="text" placeholder="যেমন: সোনা / জান (ফাঁকা রাখলে নাম ছাড়া)" style="flex:1">
   <button onclick="saveCall()">সেভ</button>
  </div>
  <div style="font-size:12px;opacity:.7;margin-top:6px">চ্যাটে বললেও হবে: "আমাকে সোনা বলে ডাকো"। Sokhi আর ভাইয়া বলে ডাকবে না।</div>
  <hr style="border-color:#1d5f8a;margin:14px 0">
  <div style="font-size:14px;margin-bottom:4px">গলা (ভয়েস)</div>
  <div id="voicestat" style="font-size:13px;opacity:.85;margin-bottom:8px">গলার অবস্থা জানা যাচ্ছে…</div>
  <button onclick="testVoice()">🔊 গলা টেস্ট করো</button>
  <div style="font-size:13px;margin-top:10px">গলার টোন:
   <select id="tonepreset" onchange="saveTone()" style="background:#0a1a2f;color:#eaf6ff;border:1px solid #1d5f8a;border-radius:8px;padding:6px"><option>মিষ্টি</option><option>স্বাভাবিক</option><option>প্রাণবন্ত</option></select>
  </div>
  <hr style="border-color:#1d5f8a;margin:14px 0">
  <div style="font-size:14px;margin-bottom:4px">GitHub — নিজে আপডেটের ঠিকানা</div>
  <div id="ghstat" style="font-size:13px;opacity:.85;margin-bottom:8px">…</div>
  <div style="display:flex;gap:6px">
   <input id="updateurl" type="text" placeholder="raw manifest.json-এর লিংক বসাও" style="flex:1">
   <button onclick="saveUrl()">সেভ</button>
  </div>
  <div style="font-size:12px;opacity:.7;margin-top:6px">লিংক বসালেই Sokhi GitHub থেকে নিজে নতুন ভার্সন এনে বসাতে পারবে। ধাপগুলো Saba-র গাইডে আছে।</div>
  <hr style="border-color:#1d5f8a;margin:14px 0">
  <div style="font-size:14px;margin-bottom:4px">নিজে নিজে আপগ্রেড</div>
  <div id="autostat" style="font-size:13px;opacity:.85;margin-bottom:8px">…</div>
  <button onclick="document.getElementById('modal').style.display='none';quick('আপগ্রেড চেক করো')">এখনই স্ব-আপগ্রেড চেক করো</button>
  <button style="float:right" onclick="document.getElementById('modal').style.display='none'">বন্ধ করো</button>
 </div>
</div>

<div id="pinbox" style="display:none">
 <p>ভাইয়া, প্রথমবার PIN দাও (ল্যাপটপে Sokhi চালালে স্ক্রিনে PIN দেখাবে)</p>
 <input id="pin" inputmode="numeric" placeholder="PIN" style="width:140px;text-align:center">
 <button onclick="savePin()">ঢোকো</button></div>

<div id="main" style="display:none">
 <div id="chat"></div>
 <div class="quick">
  <button onclick="quick('আজকের খবর দাও')">📰 খবর</button>
  <button onclick="quick('আবহাওয়া কেমন?')">🌦️ আবহাওয়া</button>
  <button onclick="quick('ইউটিউব খোলো')">▶️ YouTube</button>
  <button onclick="quick('প্যাটার্ন বিশ্লেষণ করো')">🧠 আমার প্যাটার্ন</button>
  <button onclick="quick('কী কী মনে রেখেছ?')">💾 স্মৃতি</button>
  <button onclick="quick('তোমার ভার্সন কত?')">🔖 ভার্সন</button>
  <button onclick="quick('সিস্টেমের অবস্থা দেখাও')">💻 PC-র অবস্থা</button>
 </div>
 </div>
 <div id="bar">
  <input id="text" placeholder="Sokhi-কে বলো... (বাংলা/Banglish)" onkeydown="if(event.key==='Enter')send()">
  <button onclick="mic()">🎤</button>
  <button id="livebtn" onclick="toggleLive()">🔴 লাইভ</button>
  <button onclick="send()">পাঠাও</button>
 </div>
<script>
const PINKEY='sokhi_pin';
function pin(){return localStorage.getItem(PINKEY)||''}
function savePin(){localStorage.setItem(PINKEY,document.getElementById('pin').value.trim());location.reload()}
async function api(path,body){
 const r=await fetch(path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json','X-PIN':pin()},body:body?JSON.stringify(body):undefined});
 if(r.status===403){document.getElementById('pinbox').style.display='block';document.getElementById('main').style.display='none';throw 'pin'}
 return r.json()}
function add(t,who){const d=document.createElement('div');d.className='msg '+who;d.textContent=t;if(who==='sokhi'){d.style.cursor='pointer';d.title='শুনতে চাপ দাও';d.onclick=()=>speak(t)}document.getElementById('chat').appendChild(d);window.scrollTo(0,document.body.scrollHeight)}
let edgeOk=null, speakingNow=false, currentAudio=null, speakToken=0;
function stopSpeak(){speakToken++;try{speechSynthesis.cancel()}catch(e){} if(currentAudio){try{currentAudio.pause()}catch(e){} currentAudio=null} speakingNow=false;document.getElementById('orb').classList.remove('talking')}
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
 try{const u=new SpeechSynthesisUtterance(text);u.lang='bn-BD';u.rate=rate?.8:.92;u.pitch=1.05;
 const vs=speechSynthesis.getVoices();
 const f=vs.find(v=>/google/i.test(v.name)&&/bn|বাংলা/i.test(v.lang+v.name))||vs.find(v=>/bn/i.test(v.lang)&&/female|নাবনিতা|nabanita/i.test(v.name))||vs.find(v=>/bn/i.test(v.lang))||vs.find(v=>/female/i.test(v.name));
 if(f)u.voice=f;u.onend=()=>res();u.onerror=()=>res();speechSynthesis.speak(u)}catch(e){res()}})}
async function speak(t,rate){
 const my=++speakToken;speakingNow=true;const orb=document.getElementById('orb');orb.classList.add('talking');
 try{for(const c of chunksOf(t)){
  if(my!==speakToken)break;
  if(edgeOk!==false){try{await edgeSpeak(c,rate);edgeOk=true;continue}catch(e){edgeOk=false}}
  if(my!==speakToken)break;
  await synthSpeak(c,rate)}}catch(e){}
 if(my===speakToken){orb.classList.remove('talking');speakingNow=false}}
let liveOn=false, recog=null;
function setStatus(x){document.getElementById('status').textContent=x}
function toggleLive(){liveOn?stopLive():startLive()}
function startLive(){
 const R=window.SpeechRecognition||window.webkitSpeechRecognition;
 if(!R){alert('এই ব্রাউজারে লাইভ কথা হবে না ল্যাপটপের Chrome-এ খোলো');return}
 liveOn=true;document.getElementById('livebtn').classList.add('on');document.getElementById('livebtn').textContent='⏹️ লাইভ চালু';
 add('লাইভ মোড চালু — এখন শুধু কথা বলো, আমি শুনে উত্তর দেব। থামাতে বলো: লাইভ বন্ধ।','sokhi');
 listen()}
function stopLive(){liveOn=false;const b=document.getElementById('livebtn');b.classList.remove('on');b.textContent='🔴 লাইভ';
 document.getElementById('orb').classList.remove('listening');try{recog&&recog.abort()}catch(e){}setStatus('লাইভ বন্ধ')}
function listen(){
 if(!liveOn||speakingNow)return;
 const R=window.SpeechRecognition||window.webkitSpeechRecognition;if(!R)return;
 recog=new R();recog.lang='bn-BD';recog.interimResults=false;
 document.getElementById('orb').classList.add('listening');setStatus('🎧 শুনছি…');
 recog.onresult=async e=>{
  document.getElementById('orb').classList.remove('listening');
  const txt=e.results[0][0].transcript.trim();if(!txt){listen();return}
  if(/লাইভ বন্ধ|থামো|স্টপ/.test(txt)){add(txt,'me');stopLive();add('লাইভ বন্ধ করলাম।','sokhi');return}
  add(txt,'me');setStatus('🤔 ভাবছি…');
  try{const j=await api('/api/chat',{message:txt});add(j.reply,'sokhi');setStatus('🗣️ বলছি…');await speak(j.reply,moodRate(txt))}catch(err){}
  if(liveOn)listen()};
 recog.onerror=e=>{document.getElementById('orb').classList.remove('listening');
  if(e.error==='not-allowed'){stopLive();alert('মাইকের অনুমতি লাগবে Chrome-এর ঠিকানার পাশে 🔒 চেপে Microphone Allow করো');return}
  if(liveOn&&!speakingNow)setTimeout(listen,700)};
 recog.onend=()=>{document.getElementById('orb').classList.remove('listening');if(liveOn&&!speakingNow)setTimeout(listen,350)};
 try{recog.start()}catch(e){}}
function moodRate(t){return /ক্লান্ত|মন খারাপ|ভালো লাগছে না|টেনশন|দুঃখ|কষ্ট হচ্ছে/.test(t)?'-16%':null}
async function send(speakIt){
 const el=document.getElementById('text');const t=el.value.trim();if(!t)return;el.value='';
 add(t,'me');try{const j=await api('/api/chat',{message:t});add(j.reply,'sokhi');if(speakIt)speak(j.reply,moodRate(t))}catch(e){}}
function quick(t){document.getElementById('text').value=t;send()}
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
 if(j.ok){document.getElementById('voicestat').textContent='✅ ভালো গলা চলছে: '+j.engine;speak('আসসালামু আলাইকুম, আমি সখী। আমার গলা এখন এমন শোনাবে।')}
 else{document.getElementById('voicestat').textContent='❌ ভালো গলা আসেনি — ব্রাউজারের গলা চলবে। কারণ: '+j.error}}
async function testKey(){
 document.getElementById('keymsg').textContent='টেস্ট হচ্ছে… একটু অপেক্ষা করো';
 const j=await api('/api/testkey',{});
 document.getElementById('keymsg').textContent=j.message;}
function mic(){
 const R=window.SpeechRecognition||window.webkitSpeechRecognition;
 if(!R){alert('এই ব্রাউজারে গলা-শোনা নেই Chrome ব্যবহার করো');return}
 const r=new R();r.lang='bn-BD';r.onresult=e=>{document.getElementById('text').value=e.results[0][0].transcript;send(true)};r.start()}
(async()=>{
 if(!pin()){document.getElementById('pinbox').style.display='block';return}
 try{const s=await api('/api/status');document.getElementById('main').style.display='block';
 document.getElementById('status').textContent='ভার্সন v'+s.version+' • স্কিল '+s.skills+'টা • কথা হয়েছে '+s.interactions+' বার • সম্পূর্ণ ফ্রি';
 document.getElementById('keystat').textContent=s.key_set?'✅ key বসানো আছে — স্মার্ট মাথা চালু':'❌ key বসানো নেই — অফলাইন মাথায় চলছে';
 document.getElementById('voicestat').textContent=s.voice_engine?('✅ ভালো গলা চলছে: '+s.voice_engine):(s.voice_edge?'ভালো গলা বসানো আছে — টেস্ট করে দেখো':'⚠️ ভালো গলার টুল এখনো বসেনি — Sokhi আবার চালালে পেছনে বসবে; টেস্ট বোতামে আসল গলা যাচাই হবে');
 document.getElementById('callname').value=s.call_name||'';
 document.getElementById('tonepreset').value=s.tts_preset||'মিষ্টি';
 document.getElementById('ghstat').textContent=s.update_url_set?'✅ GitHub ঠিকানা বসানো আছে':'❌ এখনো বসানো হয়নি — Saba-র গাইড দেখে বসাও';
 document.getElementById('orb').onclick=()=>{if(speakingNow)stopSpeak()};
 document.getElementById('autostat').textContent=(s.auto_upgrade?'✅ চালু আছে':'❌ বন্ধ আছে')+' • শেখা উত্তর: '+s.knowledge+'টা • প্রতিদিন নিজে নিজে একটু করে ভালো হয়';
 document.getElementById('status').textContent+=' • শেখা উত্তর '+s.knowledge+'টা';
 const hh=new Date().getHours();const greet=hh<5?'অনেক রাত হয়েছে':hh<12?'শুভ সকাল':hh<17?'শুভ দুপুর':hh<20?'শুভ বিকেল':'শুভ সন্ধ্যা';
 const care=hh<12?'নাশতা হয়েছে তো?':hh<17?'দুপুরের খাবারটা ঠিকমতো খেয়ে নিয়ো।':hh<22?'পড়া কেমন চলছে?':'রাত জাগবে না বেশি, ঘুমও দরকার।';
 add('আসসালামু আলাইকুম'+(s.call_name?' '+s.call_name:'')+'! '+greet+'। আমি Sokhi — তোমার ল্যাপটপেই আছি। '+care+' গলায় বললে গলায় উত্তর দেব, লিখলে লিখে উত্তর দেব।','sokhi');
 }catch(e){}})();
speechSynthesis && speechSynthesis.getVoices();
</script></body></html>"""


# --------------------------------------------------------------- server

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
            daily_release_if_due()
            mem, ver = get_memory(), get_version()
            caps = load_json(CAPS_FILE, [])
            return self._json({"ok": True, "version": ver["version"],
                               "skills": len(caps) + len(load_plugins()),
                               "interactions": mem["interaction_count"],
                               "facts": len(mem["facts"]),
                               "knowledge": len(load_json(KNOW_FILE, {})),
                               "auto_upgrade": bool(get_config().get("auto_self_upgrade", True)),
                               "voice_engine": VOICE_STATE.get("engine", ""),
                               "tts_preset": get_config().get("tts_preset", "মিষ্টি"), "call_name": get_config().get("call_name", ""), "update_url_set": bool(get_config().get("update_url")), "voice_edge": bool(shutil.which("edge-tts") or shutil.which("edge-tts.exe")), "key_set": bool(get_config().get("gemini_api_key"))})
        if self.path == "/api/memory":
            if not self._pin_ok():
                return self._json({"error": "pin"}, 403)
            return self._json(get_memory())
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path not in ("/api/chat", "/api/settings", "/api/testkey", "/api/tts", "/api/tts_test"):
            return self._json({"error": "not found"}, 404)
        if not self._pin_ok():
            return self._json({"error": "pin"}, 403)
        try:
            n = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except Exception:
            data = {}
        if self.path == "/api/tts_test":
            audio = make_tts_audio("আসসালামু আলাইকুম, আমি সখী।")
            if audio:
                return self._json({"ok": True, "engine": VOICE_STATE.get("engine", "")})
            return self._json({"ok": False, "error": VOICE_STATE.get("error", "অজানা সমস্যা")})
        if self.path == "/api/tts":
            audio = make_tts_audio(str(data.get("text") or ""), data.get("rate") or None, data.get("pitch") or None)
            if not audio:
                return self._json({"ok": False, "error": "edge-tts নেই — ব্রাউজারের গলা চলবে"})
            body_bytes = audio.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Content-Length", str(len(body_bytes)))
            self.end_headers()
            self.wfile.write(body_bytes)
            return
        if self.path == "/api/settings":
            preset = str(data.get("tts_preset") or "")
            presets = {"মিষ্টি": ("-10%", "+4%"), "স্বাভাবিক": ("-4%", "+2%"), "প্রাণবন্ত": ("+2%", "+6%")}
            if preset in presets:
                cfg = get_config()
                cfg["tts_preset"] = preset
                cfg["tts_rate"], cfg["tts_pitch"] = presets[preset]
                save_config(cfg)
                return self._json({"ok": True, "tts_preset": preset})
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
        daily_release_if_due()
        reply = apply_call_name(care_suffix(handle_message(data.get("message", ""))))
        self._json({"reply": reply})


def local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


APP_VERSION = "0.5.0"


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
        log_change(f"আপগ্রেড: v{APP_VERSION} — গলার টোন-প্রিসেট (মিষ্টি/স্বাভাবিক/প্রাণবন্ত), যত্নের টোন প্রম্পটে, রাতের ঘুম-মনে-করানো, সময়-অনুযায়ী স্বাগত, কথা থামানোর সুবিধা")
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
