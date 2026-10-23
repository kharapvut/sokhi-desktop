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
    cfg.setdefault("git_auto_push", False)
    cfg.setdefault("city", "Dhaka")
    cfg.setdefault("auto_self_upgrade", True)
    cfg.setdefault("update_url", "")
    cfg.setdefault("tts_voice", "bn-BD-NabanitaNeural")
    cfg.setdefault("call_name", "")
    cfg.setdefault("tts_preset", "মিষ্টি")
    cfg.setdefault("tts_rate", "-8%")
    cfg.setdefault("tts_pitch", "+3%")
    cfg.setdefault("bridge_enabled", False)
    cfg.setdefault("computer_use_enabled", False)
    cfg.setdefault("away_mode", True)
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
    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": gemini_contents(user_text),
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
    """ask_gemini-কে নিরাপদে ডাকে; key না থাকলে/ব্যর্থ হলে None।"""
    try:
        mem = get_memory()
    except Exception:
        mem = {}
    try:
        out = ask_gemini(prompt, mem)
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


# ------------------------------------------- foundation (F3 / F5 / N14) — honest stubs
def foundation_status():
    cfg = get_config()
    return {
        "computer_use_gui": bool(cfg.get("computer_use_enabled", False)),
        "bridge_enabled": bool(cfg.get("bridge_enabled", False)),
        "bridge_queue": len(load_json(BRIDGE_QUEUE_FILE, [])),
        "note": ("F3 পূর্ণ GUI computer-use ও F5/N14 cloud-sync v1.0-তে foundation-only: "
                 "config ফ্ল্যাগ ও bridge-queue কাঠামো প্রস্তুত; মূল কাজ (এজেন্ট দল, "
                 "away-task তালিকা, WhatsApp সেতু Muse-Sokhi দিয়ে) পরের ধাপে যুক্ত হবে।"),
    }


def bridge_enqueue(item):
    q = load_json(BRIDGE_QUEUE_FILE, [])
    if not isinstance(q, list):
        q = []
    q.append({"item": str(item)[:300], "ts": now_str()})
    save_json(BRIDGE_QUEUE_FILE, q[-100:])
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

        # --- v1.0: teacher + mock test (agents/away handled earlier)
        _tch = teacher_handle(text, low)
        if _tch:
            return _tch
        if "মক টেস্ট" in text or "mock test" in low:
            return exam_start(_detect_subject(text, low) or "গণিত", 10, 10)
        if "পরীক্ষার অবস্থা" in text:
            return exam_status_text()
        if "পড়ার অগ্রগতি" in text:
            return study_progress_text()
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
 --accent:#22b8f0; --accent2:#0b5cad; --deep:#0b3d91; --bg:#050a18; --panel:#0d2138cc; --line:#1d5f8a; --txt:#dff6ff;
}
body[data-theme="blue"]{--accent:#22b8f0;--accent2:#0b5cad;--deep:#0b3d91;--bg:#050a18;--line:#1d5f8a}
body[data-theme="purple"]{--accent:#b06cf0;--accent2:#6d28b8;--deep:#3b1470;--bg:#0d0518;--line:#5b2a9d}
body[data-theme="gold"]{--accent:#f0b822;--accent2:#b8860b;--deep:#7a5a06;--bg:#141003;--line:#8a6d1d}
body[data-theme="pink"]{--accent:#f06cae;--accent2:#b8326e;--deep:#70143c;--bg:#180510;--line:#9d2a5f}
*{box-sizing:border-box}
body{margin:0;font-family:'Hind Siliguri','Segoe UI',sans-serif;background:var(--bg);color:var(--txt);min-height:100vh;padding-bottom:96px;transition:background .4s}
.tagline{text-align:center;font-size:11.5px;letter-spacing:.4px;opacity:.62;padding:8px 14px 0;line-height:1.5}
header{text-align:center;padding:6px 8px 2px}
h1{margin:2px 0 0;font-size:22px;letter-spacing:3px}
.sub{opacity:.78;font-size:13px}
#layout{display:grid;grid-template-columns:300px minmax(0,1fr) 400px;gap:12px;max-width:1560px;margin:8px auto;padding:0 10px;align-items:start}
@media(max-width:1080px){#layout{grid-template-columns:1fr}}
.card{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:12px;margin-bottom:12px;backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px)}
.card h3{margin:0 0 8px;font-size:15px}
.card .body{font-size:13.5px;line-height:1.55;white-space:pre-wrap;opacity:.94}
.small{font-size:12px;opacity:.7}
#orb{width:280px;height:300px;margin:2px auto;position:relative;cursor:pointer}
#orb canvas{display:block;width:280px;height:300px}
#orb.talking{filter:brightness(1.25)}
.nodes{display:flex;gap:8px;justify-content:center;flex-wrap:wrap;margin:6px 0 2px}
.nodes button{font-size:13px;padding:8px 12px;border-radius:999px}
#chat{display:flex;flex-direction:column;gap:8px;min-height:200px}
.msg{max-width:88%;padding:9px 12px;border-radius:14px;white-space:pre-wrap;line-height:1.5;font-size:15px;display:flex;gap:8px;align-items:flex-start}
.me{align-self:flex-end;background:var(--accent2)}
.sokhi{align-self:flex-start;background:#ffffff10;border:1px solid var(--line);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px)}
.avatar{flex:0 0 auto;width:24px;height:24px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#ffffffcc,var(--accent) 55%,var(--deep));display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;color:#04101f;margin-top:1px}
#bar{position:fixed;left:0;right:0;bottom:0;background:#02040add;padding:10px;display:flex;gap:8px;max-width:820px;margin:0 auto;z-index:40}
input,button,select,textarea{font-family:inherit;font-size:15px;border-radius:10px;border:1px solid var(--line);background:#0a1a2f;color:var(--txt);padding:9px}
input{flex:1} button{cursor:pointer;background:var(--accent2)}
textarea{width:100%;resize:vertical}
.quick{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.quick button{font-size:13px;padding:7px 10px}
#pinbox{max-width:420px;margin:30px auto;background:var(--panel);padding:18px;border-radius:14px;text-align:center;border:1px solid var(--line)}
#gear{position:fixed;top:10px;right:10px;width:42px;height:42px;border-radius:50%;font-size:19px;padding:0;z-index:50}
#modal{display:none;position:fixed;inset:0;background:#02040acc;z-index:60;overflow:auto}
#modal .panel{max-width:460px;margin:40px auto;background:#0d2138;border:1px solid var(--line);border-radius:16px;padding:18px}
#modal .panel h3{margin:0 0 8px;font-size:16px}
#livebtn.on{background:#a00f2d;border-color:#ff5577}
.tabs{display:flex;gap:6px;margin-bottom:10px;flex-wrap:wrap}
.tabs button{font-size:13.5px;padding:8px 11px;border-radius:999px;opacity:.75}
.tabs button.on{opacity:1;background:var(--accent);color:#04101f;font-weight:600}
.tabpane{display:none}
.tabpane.on{display:block}
.agentcard{border:1px solid var(--line);border-radius:12px;padding:9px 11px;margin-bottom:8px;background:#ffffff08;font-size:13.5px}
.agentcard .st{font-size:12px;opacity:.8}
.step{font-size:12.5px;opacity:.85}
.themebtns{display:flex;gap:6px;flex-wrap:wrap}
.themebtns button{font-size:13px;padding:7px 11px}
#examchip{display:none;align-items:center;gap:8px;background:#a00f2d;border:1px solid #ff5577;border-radius:999px;padding:5px 12px;font-size:13.5px;width:max-content;margin:8px auto}
#examform{display:none;margin-top:10px}
#examform .row{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
#examform input[type=number]{flex:0 0 84px}
#idle{display:none;position:fixed;inset:0;background:#02040af2;z-index:90;text-align:center;padding-top:14vh;cursor:pointer}
#idle .clock{font-size:84px;font-weight:700;letter-spacing:2px}
#idle .date{font-size:22px;opacity:.85;margin-top:6px}
#idle .wx{font-size:16px;opacity:.7;margin-top:14px;white-space:pre-wrap}
#hubsteps{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12.5px;line-height:1.7;white-space:pre-wrap}
.listitem{border-bottom:1px dashed #ffffff22;padding:6px 0;font-size:14px;white-space:pre-wrap}
</style></head><body data-theme="blue">
<div class="tagline">Sokhi is the world's first Sci-Fi AI Desktop Experience — built for those who grew up dreaming of JARVIS, and refused to settle for boring software.</div>
<header>
<div class="sub" id="status">তোমার Windows ল্যাপটপের নিজের AI সঙ্গী — সম্পূর্ণ ফ্রি</div>
</header>

<button id="gear" title="সেটিংস" onclick="openSettings()">⚙️</button>
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
  <hr style="border-color:var(--line);margin:14px 0">
  <div style="font-size:14px;margin-bottom:4px">আমাকে যে নামে ডাকবে</div>
  <div style="display:flex;gap:6px">
   <input id="callname" type="text" placeholder="যেমন: সোনা / জান (ফাঁকা রাখলে নাম ছাড়া)" style="flex:1">
   <button onclick="saveCall()">সেভ</button>
  </div>
  <div style="font-size:12px;opacity:.7;margin-top:6px">চ্যাটে বললেও হবে: "আমাকে সোনা বলে ডাকো"। Sokhi আর ভাইয়া বলে ডাকবে না।</div>
  <hr style="border-color:var(--line);margin:14px 0">
  <div style="font-size:14px;margin-bottom:4px">গলা (ভয়েস)</div>
  <div id="voicestat" style="font-size:13px;opacity:.85;margin-bottom:8px">গলার অবস্থা জানা যাচ্ছে…</div>
  <button onclick="testVoice()">🔊 গলা টেস্ট করো</button>
  <div style="font-size:13px;margin-top:10px">গলার টোন:
   <select id="tonepreset" onchange="saveTone()"><option>মিষ্টি</option><option>স্বাভাবিক</option><option>প্রাণবন্ত</option></select>
  </div>
  <hr style="border-color:var(--line);margin:14px 0">
  <div style="font-size:14px;margin-bottom:6px">🎨 রঙের থিম</div>
  <div class="themebtns">
   <button onclick="setTheme('blue')">🔵 নীল</button>
   <button onclick="setTheme('purple')">🟣 বেগুনি</button>
   <button onclick="setTheme('gold')">🟡 সোনালি</button>
   <button onclick="setTheme('pink')">🌸 গোলাপি</button>
  </div>
  <hr style="border-color:var(--line);margin:14px 0">
  <div style="font-size:14px;margin-bottom:4px">GitHub — নিজে আপডেটের ঠিকানা</div>
  <div id="ghstat" style="font-size:13px;opacity:.85;margin-bottom:8px">…</div>
  <div style="display:flex;gap:6px">
   <input id="updateurl" type="text" placeholder="raw manifest.json-এর লিংক বসাও" style="flex:1">
   <button onclick="saveUrl()">সেভ</button>
  </div>
  <div style="font-size:12px;opacity:.7;margin-top:6px">লিংক বসালেই Sokhi GitHub থেকে নিজে নতুন ভার্সন এনে বসাতে পারবে। ধাপগুলো Saba-র গাইডে আছে।</div>
  <hr style="border-color:var(--line);margin:14px 0">
  <div style="font-size:14px;margin-bottom:4px">নিজে নিজে আপগ্রেড</div>
  <div id="autostat" style="font-size:13px;opacity:.85;margin-bottom:8px">…</div>
  <button onclick="document.getElementById('modal').style.display='none';quick('আপগ্রেড চেক করো')">এখনই স্ব-আপগ্রেড চেক করো</button>
  <hr style="border-color:var(--line);margin:14px 0">
  <div id="rulesec">
  <div style="font-size:14px;margin-bottom:4px">📋 আমার নিয়ম (N13)</div>
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
  <div class="card"><h3>🌦️ আবহাওয়া</h3><div class="body" id="weather">লোড হচ্ছে…</div></div>
  <div class="card"><h3>📰 আজকের headlines</h3><div class="body" id="news">লোড হচ্ছে…</div></div>
  <div class="card"><h3>🛰️ Visual Hub</h3><div class="small" style="margin-bottom:6px">চলমান agent কাজের ধাপ</div><div id="hubsteps">এখন কোনো কাজ চলছে না।</div></div>
  <div class="card"><h3>🖍️ Whiteboard</h3><div class="body" id="board">বোর্ড খালি।</div>
   <button style="margin-top:8px;font-size:13px" onclick="clearBoard()">বোর্ড মোছো</button></div>
 </div>

 <div id="centercol">
  <div id="orb" title="কথা থামাতে চাপ দাও"><canvas id="pcanvas" width="280" height="300"></canvas></div>
  <h1 style="text-align:center">SOKHI</h1>
  <div class="nodes">
   <button onclick="quick('কী কী মনে রেখেছ?')">💾 Memory</button>
   <button onclick="quick('প্যাটার্ন বিশ্লেষণ করো')">🌌 Soul</button>
   <button id="skillsnode" onclick="quick('তোমার স্কিলগুলো কী কী?')">🧩 Skills</button>
   <button onclick="openSettings()">⚙️ Settings</button>
  </div>
  <div id="examchip"><span id="examtimer">⏳ 00:00</span><button style="font-size:12.5px;padding:4px 10px" onclick="finishExam()">শেষ করো</button></div>
  <div class="quick">
   <button onclick="quick('আজকের খবর দাও')">📰 খবর</button>
   <button onclick="quick('আবহাওয়া কেমন?')">🌦️ আবহাওয়া</button>
   <button onclick="quick('ইউটিউব খোলো')">▶️ YouTube</button>
   <button onclick="quick('প্যাটার্ন বিশ্লেষণ করো')">🧠 আমার প্যাটার্ন</button>
   <button onclick="quick('কী কী মনে রেখেছ?')">💾 স্মৃতি</button>
   <button onclick="quick('তোমার ভার্সন কত?')">🔖 ভার্সন</button>
   <button onclick="quick('সিস্টেমের অবস্থা দেখাও')">💻 PC-র অবস্থা</button>
   <button onclick="quick('আমাকে গণিত শেখাও')">🎓 শেখাও</button>
   <button onclick="quick('কতদূর হলো?')">🤖 কতদূর হলো</button>
   <button onclick="toggleExamForm()">📝 মক টেস্ট</button>
   <button onclick="openRules()">📋 নিয়ম</button>
  </div>
  <div id="examform" class="card">
   <h3>📝 মক টেস্ট শুরু করো</h3>
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
   <button id="tabbtn-chat" class="on" onclick="showTab('chat')">💬 চ্যাট</button>
   <button id="tabbtn-agents" onclick="showTab('agents')">🤖 এজেন্ট</button>
   <button id="tabbtn-notes" onclick="showTab('notes')">📝 নোট</button>
   <button id="tabbtn-tasks" onclick="showTab('tasks')">✅ টাস্ক</button>
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
 <input id="text" placeholder="Sokhi-কে বলো... (বাংলা/Banglish)" onkeydown="if(event.key==='Enter')send()">
 <button onclick="mic()">🎤</button>
 <button id="livebtn" onclick="toggleLive()">🔴 লাইভ</button>
 <button onclick="send()">পাঠাও</button>
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
function add(t,who){
 const d=document.createElement('div');d.className='msg '+who;
 if(who==='sokhi'){
  const av=document.createElement('span');av.className='avatar';av.textContent='স';d.appendChild(av);
  const tx=document.createElement('span');tx.textContent=t;d.appendChild(tx);
  d.style.cursor='pointer';d.title='শুনতে চাপ দাও';d.onclick=()=>speak(t)}
 else{d.textContent=t}
 document.getElementById('chat').appendChild(d);
 d.scrollIntoView({behavior:'smooth',block:'end'})}
let edgeOk=null, speakingNow=false, currentAudio=null, speakToken=0;
function stopSpeak(){speakToken++;try{speechSynthesis.cancel()}catch(e){} if(currentAudio){try{currentAudio.pause()}catch(e){} currentAudio=null} speakingNow=false;document.getElementById('orb').classList.remove('talking');setMood('calm')}
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
 const my=++speakToken;speakingNow=true;setMood('speaking');const orb=document.getElementById('orb');orb.classList.add('talking');
 try{for(const c of chunksOf(t)){
  if(my!==speakToken)break;
  if(edgeOk!==false){try{await edgeSpeak(c,rate);edgeOk=true;continue}catch(e){edgeOk=false}}
  if(my!==speakToken)break;
  await synthSpeak(c,rate)}}catch(e){}
 if(my===speakToken){orb.classList.remove('talking');speakingNow=false;setMood(liveOn?'listening':'calm')}}
let liveOn=false, recog=null;
function setStatus(x){document.getElementById('status').textContent=x}
function toggleLive(){liveOn?stopLive():startLive()}
function startLive(){
 const R=window.SpeechRecognition||window.webkitSpeechRecognition;
 if(!R){alert('এই ব্রাউজারে লাইভ কথা হবে না ল্যাপটপের Chrome-এ খোলো');return}
 liveOn=true;setMood('listening');document.getElementById('livebtn').classList.add('on');document.getElementById('livebtn').textContent='⏹️ লাইভ চালু';
 add('লাইভ মোড চালু — এখন শুধু কথা বলো, আমি শুনে উত্তর দেব। থামাতে বলো: লাইভ বন্ধ।','sokhi');
 listen()}
function stopLive(){liveOn=false;setMood('calm');const b=document.getElementById('livebtn');b.classList.remove('on');b.textContent='🔴 লাইভ';
 document.getElementById('orb').classList.remove('listening');try{recog&&recog.abort()}catch(e){}setStatus('লাইভ বন্ধ')}
function listen(){
 if(!liveOn||speakingNow)return;
 const R=window.SpeechRecognition||window.webkitSpeechRecognition;if(!R)return;
 recog=new R();recog.lang='bn-BD';recog.interimResults=false;
 document.getElementById('orb').classList.add('listening');setMood('listening');setStatus('🎧 শুনছি…');
 recog.onresult=async e=>{
  document.getElementById('orb').classList.remove('listening');
  const txt=e.results[0][0].transcript.trim();if(!txt){listen();return}
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
 const el=document.getElementById('text');const t=el.value.trim();if(!t)return;el.value='';
 add(t,'me');
 if(examActive){
  try{const j=await api('/api/exam',{action:'answer',answer:t});
   if(j&&j.reply)add(j.reply,'sokhi');
   if(j&&(j.done||j.finished||j.ended))endExamUi();
  }catch(e){}
  return}
 try{const j=await api('/api/chat',{message:t});add(j.reply,'sokhi');if(speakIt)speak(j.reply,moodRate(t))}catch(e){}}
function quick(t){document.getElementById('text').value=t;send()}
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
 document.getElementById('skillsnode').textContent='🧩 Skills '+s.skills+'টা';
 document.getElementById('keystat').textContent=s.key_set?'✅ key বসানো আছে — স্মার্ট মাথা চালু':'❌ key বসানো নেই — অফলাইন মাথায় চলছে';
 document.getElementById('voicestat').textContent=s.voice_engine?('✅ ভালো গলা চলছে: '+s.voice_engine):(s.voice_edge?'ভালো গলা বসানো আছে — টেস্ট করে দেখো':'⚠️ ভালো গলার টুল এখনো বসেনি — Sokhi আবার চালালে পেছনে বসবে; টেস্ট বোতামে আসল গলা যাচাই হবে');
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
</script></body></html>"""


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
    return {"weather_text": apply_call_name(_panels_cache["weather"]),
            "news_text": apply_call_name(_panels_cache["news"])}


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
                               "tts_preset": get_config().get("tts_preset", "মিষ্টি"), "call_name": get_config().get("call_name", ""), "update_url_set": bool(get_config().get("update_url")), "voice_edge": bool(shutil.which("edge-tts") or shutil.which("edge-tts.exe")), "key_set": bool(get_config().get("gemini_api_key")), "foundation": foundation_status(), "exam_active": exam_active(), "agents_active": sum(1 for j in AGENT_JOBS if j["status"] == "চলছে")})
        if self.path == "/api/memory":
            if not self._pin_ok():
                return self._json({"error": "pin"}, 403)
            return self._json(get_memory())
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
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path not in ("/api/chat", "/api/settings", "/api/testkey", "/api/tts", "/api/tts_test", "/api/agents", "/api/exam", "/api/notes", "/api/tasks", "/api/rules", "/api/whiteboard"):
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
        if self.path == "/api/agents":
            return self._json(agents_api(data))
        if self.path == "/api/exam":
            return self._json(exam_api(data))
        if self.path == "/api/notes":
            (DATA / "notes.txt").write_text(str(data.get("text") or "")[:20000], encoding="utf-8")
            return self._json({"ok": True})
        if self.path == "/api/tasks":
            return self._json(tasks_api(data))
        if self.path == "/api/rules":
            if data.get("rule"):
                return self._json({"ok": True, "message": rules_add(str(data["rule"])), "text": rules_text()})
            return self._json({"ok": True, "text": rules_text()})
        if self.path == "/api/whiteboard":
            if data.get("action") == "clear":
                wb_clear()
            return self._json({"ok": True, "lines": wb_lines()})
        daily_release_if_due()
        _msg = data.get("message", "")
        reply = apply_call_name(care_suffix(handle_message(_msg)))
        convo_remember(_msg, reply)
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


APP_VERSION = "1.0.0"


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
        log_change(f"আপগ্রেড: v{APP_VERSION} — নতুন ড্যাশবোর্ড (তিন-কলাম, কণা-চরিত্র, থিম, idle স্ক্রিন), Gemini conversation buffer, এজেন্ট দল, শিক্ষক+মক টেস্ট+হোয়াইটবোর্ড, N8 PC প্যাক, N13 কথা-বলে আপগ্রেড")
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
