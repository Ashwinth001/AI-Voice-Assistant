"""
Fast command router - instant matching, no LLM needed.
Reduces 50s delay to under 1s for all common commands.
"""
import re


def _after(text: str, keywords: list) -> str:
    t = text.lower()
    for kw in keywords:
        if kw in t:
            idx = t.index(kw) + len(kw)
            rest = text[idx:].strip()
            if rest:
                return rest
    return text


def _remind_params(text: str) -> dict:
    t = text.lower()
    minutes = 5
    m = re.search(r"(\d+)\s*(minute|min|hour|second|sec)", t)
    if m:
        val, unit = int(m.group(1)), m.group(2)
        if "hour" in unit: minutes = val * 60
        elif "sec" in unit: minutes = max(1, val // 60)
        else: minutes = val
    msg = text
    for kw in [" to ", " about ", " for "]:
        if kw in t:
            idx = t.index(kw) + len(kw)
            rest = text[idx:]
            if not re.match(r"\d+\s*(min|hour)", rest.lower()):
                msg = rest
                break
    return {"message": msg.strip(), "minutes": minutes}


def _lang_ext(lang: str) -> str:
    return {"python":"py","go":"go","javascript":"js","java":"java",
            "rust":"rs","typescript":"ts","c++":"cpp","c":"c"}.get(lang,"py")


BROWSER_MAP = {
    "google":   "https://www.google.com",
    "youtube":  "https://www.youtube.com",
    "gmail":    "https://mail.google.com",
    "github":   "https://github.com",
    "linkedin": "https://www.linkedin.com",
    "twitter":  "https://www.twitter.com",
    "facebook": "https://www.facebook.com",
    "netflix":  "https://www.netflix.com",
    "amazon":   "https://www.amazon.in",
    "flipkart": "https://www.flipkart.com",
    "teams":    "https://teams.microsoft.com",
    "outlook":  "https://outlook.live.com",
    "chatgpt":  "https://chat.openai.com",
    "whatsapp": "https://web.whatsapp.com",
    "maps":     "https://maps.google.com",
    "drive":    "https://drive.google.com",
    "meet":     "https://meet.google.com",
    "stackoverflow": "https://stackoverflow.com",
}

SLEEP_WORDS = [
    "sleep", "standby", "go to sleep", "stop listening",
    "be quiet", "silent mode", "stop", "mute yourself",
    "shhh", "shut up",
]
REMIND_WORDS   = ["remind me", "set a reminder", "alert me", "notify me"]
PPT_WORDS      = ["create a presentation","make a presentation","create a ppt",
                  "make a ppt","create slides","create powerpoint","build a presentation"]
RESEARCH_WORDS = ["research on","research about","learn about","learn on",
                  "study about","find out about","teach yourself about",
                  "search and learn about","read about","explore"]
CODE_WORDS     = ["write a program","write code","create a program","code for",
                  "write a script","write a function","create a script",
                  "write an app","build an app","make a program"]
ANALYZE_WORDS  = ["analyze","analyse","review","understand","explain","read this file","check this code"]
SCREEN_WORDS   = ["what am i doing","look at my screen","analyze my screen",
                  "what is on my screen","watch my screen","what do you see"]
SYSINFO_WORDS  = ["system info","cpu usage","ram usage","memory usage",
                  "disk usage","how is my system","system status"]
UPDATE_WORDS   = ["update your model","update yourself","upgrade your model",
                  "get latest model","update ai","check for model update"]
EMAIL_WORDS    = ["check email","read email","check my mail","latest email",
                  "any new email","open outlook","open gmail"]
TEAMS_WORDS    = ["create meeting","schedule meeting","new meeting","create teams meeting",
                  "schedule a call","set up a meeting"]
# Camera and recording commands
PHOTO_WORDS    = ["take a photo","take photo","capture photo","take picture",
                  "take a picture","click photo","snap a photo"]
VIDEO_WORDS    = ["record video","start recording video","record from camera",
                  "start video recording","capture video"]
STOP_VIDEO     = ["stop recording","stop video","end recording","finish recording"]
SCREENSHOT_WORDS = ["take screenshot","capture screen","screenshot",
                   "take a screenshot","grab screen"]
SCREEN_REC_WORDS = ["record screen","start screen recording","capture screen video",
                    "record my screen"]
STOP_SCREEN    = ["stop screen recording","end screen recording"]
# Auto-learn commands
LEARN_WORDS    = ["learn about","remember this","study about","memorize",
                  "teach yourself about","learn everything about"]
# Identity commands
IDENTITY_WORDS = ["who are you","what is your name","who made you","who created you",
                  "who is your creator","what are you","introduce yourself"]


def try_fast_route(text: str) -> dict | None:
    t = text.lower().strip()

    # Sleep
    if any(w in t for w in SLEEP_WORDS):
        return {"action": "__sleep__", "params": {}}

    # Reminder
    if any(w in t for w in REMIND_WORDS):
        return {"action": "set_reminder", "params": _remind_params(text)}

    # Screen analyze
    if any(w in t for w in SCREEN_WORDS):
        return {"action": "screen_analyze", "params": {}}

    # System info
    if any(w in t for w in SYSINFO_WORDS):
        return {"action": "system_info", "params": {}}

    # Update model
    if any(w in t for w in UPDATE_WORDS):
        return {"action": "update_model", "params": {}}

    # PPT
    if any(w in t for w in PPT_WORDS):
        topic = _after(text, [" on "," about "," for "," titled "])
        return {"action": "create_ppt", "params": {"topic": topic, "slides": 5}}

    # Research / learn
    if any(w in t for w in RESEARCH_WORDS):
        for kw in RESEARCH_WORDS:
            if kw in t:
                topic = text[t.index(kw)+len(kw):].strip()
                if topic:
                    return {"action": "research_topic", "params": {"topic": topic}}

    # Code
    if any(w in t for w in CODE_WORDS):
        lang = "python"
        for l in ["python","go","golang","javascript","java","rust","c++","typescript"]:
            if l in t:
                lang = "go" if l == "golang" else l
                break
        return {"action": "write_code", "params": {
            "language": lang, "task": text,
            "filename": f"solution.{_lang_ext(lang)}"}}

    # Analyze file
    if any(w in t for w in ANALYZE_WORDS):
        path_m = re.search(r'[A-Za-z]:[\\\/][^\s"\']+|[\w.\\\/]+\.[a-z]{2,4}', text)
        if path_m:
            return {"action": "analyze_file", "params": {"path": path_m.group()}}

    # Teams meeting
    if any(w in t for w in TEAMS_WORDS):
        title = _after(text, [" titled "," called "," named "," title "," for "])
        # Extract time
        time_m = re.search(r"(\d{1,2}(?::\d{2})?)\s*(am|pm)?\s*(?:to|-)\s*(\d{1,2}(?::\d{2})?)\s*(am|pm)?", t)
        start_t, end_t = "14:00", "15:00"
        if time_m:
            start_t = time_m.group(1) + (":00" if ":" not in time_m.group(1) else "")
            end_t   = time_m.group(3) + (":00" if ":" not in time_m.group(3) else "")
        return {"action": "create_teams_meeting",
                "params": {"title": title, "start": start_t, "end": end_t}}

    # Email check
    if any(w in t for w in EMAIL_WORDS):
        from_m = re.search(r"[\w.+-]+@[\w.-]+\.\w+", text)
        return {"action": "check_email",
                "params": {"from": from_m.group() if from_m else ""}}

    # Identity questions
    if any(w in t for w in IDENTITY_WORDS):
        return {"action": "identity_response", "params": {}}

    # Camera - take photo
    if any(w in t for w in PHOTO_WORDS):
        return {"action": "take_photo", "params": {}}

    # Camera - record video
    if any(w in t for w in VIDEO_WORDS):
        return {"action": "start_video", "params": {}}

    # Stop video recording
    if any(w in t for w in STOP_VIDEO):
        return {"action": "stop_video", "params": {}}

    # Screenshot
    if any(w in t for w in SCREENSHOT_WORDS):
        return {"action": "take_screenshot", "params": {}}

    # Screen recording
    if any(w in t for w in SCREEN_REC_WORDS):
        return {"action": "start_screen_recording", "params": {}}

    # Stop screen recording
    if any(w in t for w in STOP_SCREEN):
        return {"action": "stop_screen_recording", "params": {}}

    # Auto-learn
    if any(w in t for w in LEARN_WORDS):
        for kw in LEARN_WORDS:
            if kw in t:
                topic = text[t.index(kw)+len(kw):].strip()
                if topic:
                    return {"action": "auto_learn", "params": {"topic": topic, "depth": "deep"}}

    # Named browser targets
    for name, url in BROWSER_MAP.items():
        if f"open {name}" in t or f"go to {name}" in t:
            return {"action": "open_browser", "params": {"url": url}}

    # Open chrome / browser
    if any(w in t for w in ["open chrome","open browser","open google chrome","open firefox"]):
        return {"action": "open_browser", "params": {"url": "https://www.google.com"}}

    # Search
    if "search" in t and ("for" in t or "about" in t):
        q = _after(text, ["search for","search about","search on","google for","search"])
        if q:
            return {"action": "search_web", "params": {"query": q}}

    # Restart / shutdown
    if any(w in t for w in ["restart my pc","restart the computer","reboot","restart pc"]):
        return {"action": "restart_pc", "params": {}}
    if any(w in t for w in ["shut down","shutdown","turn off computer","power off"]):
        return {"action": "shutdown_pc", "params": {}}

    return None
