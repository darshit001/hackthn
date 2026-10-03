"""Community presets and language table. Adding a community or a language = adding one dict entry.
voice_eleven ids are ElevenLabs premade voices usable on the free API (Sarah, George, Brian verified 29 Sep 2026);
eleven_flash_v2_5 is multilingual, so the same voice speaks Hindi. gender picks the edge-tts voice from LANGUAGES.
language on a community is only the default language chip in the UI. accent is RRGGBB for the highlighted caption word.
wps = effective spoken words per second for the edge-tts voices at media.EDGE_RATE, including the pause each scene adds
(measured 2 Oct 2026); it sizes the script for a target length. ElevenLabs speaks ~15% faster, so its videos run a little short.
cta = the lines an image post draws at the bottom: (single picture, last carousel slide, the follow line under it).
script = regex character range a translation into this language must use (None: Roman script, no Indic letters).
mood picks the background track from MUSIC (Kevin MacLeod, incompetech.com, CC BY 4.0; credited in the job JSON and README)."""

import os

import httpx

# A key is retired for this call on auth/quota rejections only; a 400 normally means the request is wrong, not the key.
KEY_RETRY = (401, 402, 403, 429)
# ElevenLabs answers a wrong-length key with 400 + authentication_error, so a 400 whose body blames the key counts too.
AUTH_WORDS = ("authentication_error", "invalid_api_key", "api key")


def with_keys(fn, *names):
    """Run fn(*keys) with each credential configured for `names`, newest failure moving to the next one.

    Looks up NAME, then NAME_2, then NAME_3. Several names rotate together, because Cloudflare's account id
    and API token are one credential split over two variables: a set counts only when every name in it is set.
    Falls through to the next set when a key is rejected or out of quota, so a dead or exhausted key is skipped
    without taking the provider down; any other error raises, since a second key will not fix a bad request."""
    sets = []
    for suffix in ("", "_2", "_3"):
        vals = [os.environ.get(n + suffix, "").strip() for n in names]
        if all(vals):
            sets.append(vals)
    if not sets:
        raise RuntimeError("no " + "/".join(names))
    for i, vals in enumerate(sets):
        try:
            return fn(*vals)
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            bad_key = code in KEY_RETRY or (code == 400 and any(w in e.response.text.lower() for w in AUTH_WORDS))
            if i == len(sets) - 1 or not bad_key:
                raise


DURATIONS = [15, 30, 45, 60]

LANGUAGES = {
    "en": dict(
        label="English", script=None, whisper="en", wps=2.4,
        cta=("Full story in the caption ↓", "The rest is in the caption ↓", "Follow for more"),
        instruction="English",
        voice_edge={"f": "en-IN-NeerjaNeural", "m": "en-IN-PrabhatNeural"},
    ),
    "hi": dict(
        label="हिन्दी", script="ऀ-ॿ", whisper="hi", wps=2.1,
        cta=("पूरी बात कैप्शन में ↓", "बाकी बात कैप्शन में ↓", "ऐसी और पोस्ट के लिए फ़ॉलो करें"),
        instruction="Hindi in Devanagari script, simple everyday spoken Hindi; write every number as Hindi words",
        voice_edge={"f": "hi-IN-SwaraNeural", "m": "hi-IN-MadhurNeural"},
    ),
    "hinglish": dict(
        label="Hinglish", script=None, whisper="hi", wps=2.2,
        cta=("Poori baat caption mein ↓", "Baaki baat caption mein ↓", "Aur aise posts ke liye follow karo"),
        instruction="Hinglish written in Roman script (a natural mix of Hindi and English, the way young Indians text)",
        voice_edge={"f": "en-IN-NeerjaNeural", "m": "en-IN-PrabhatNeural"},
    ),
    "gu": dict(
        label="ગુજરાતી", script="઀-૿", whisper="gu", wps=1.7,
        cta=("આખી વાત કેપ્શનમાં ↓", "બાકીની વાત કેપ્શનમાં ↓", "આવી વધુ પોસ્ટ માટે ફોલો કરો"),
        instruction="Gujarati in Gujarati script, simple everyday spoken Gujarati; write every number as Gujarati words",
        voice_edge={"f": "gu-IN-DhwaniNeural", "m": "gu-IN-DhwaniNeural"},  # Dhwani for every community, by choice
        eleven=False,  # eleven_flash_v2_5 has no Gujarati: an English voice read it with an accent, so edge speaks first
    ),
}

MUSIC = {  # mood -> (file under assets/music, track title)
    "upbeat": ("Carefree.mp3", "Carefree"),
    "calm": ("Wallpaper.mp3", "Wallpaper"),
    "electronic": ("Electrodoodle.mp3", "Electrodoodle"),
    "inspiring": ("Inspired.mp3", "Inspired"),
}
MUSIC_CREDIT = "Kevin MacLeod (incompetech.com), CC BY 4.0"
STYLES = {  # slug -> (label, phrase that leads every image prompt: FLUX weights the first words most)
    "photo": ("Photo", "Photograph, cinematic soft light"),
    "anime": ("Anime", "Anime illustration, cel shading, vivid colours, clean line art"),
    "infographic": ("Infographic", "Flat vector infographic illustration, bold simple shapes, limited palette"),
    "cinematic": ("Cinematic", "Cinematic 35mm film still, dramatic lighting, shallow depth of field, moody colour grade"),
}

# The user's photo, restyled by FLUX.2 before it talks: slug -> (label, what they wear, the background behind them)
OUTFITS = {
    "smart": ("Smart casual", "a well-fitted navy blazer over a plain white t-shirt", "a bright modern office"),
    "formal": ("Formal", "a tailored charcoal suit, crisp white shirt and a dark tie", "a sleek glass-walled boardroom"),
    "street": ("Streetwear", "a clean oversized hoodie and a simple chain", "a colourful city street at golden hour"),
    "sporty": ("Sporty", "a fitted athletic t-shirt and a sports watch", "a modern gym with soft window light"),
}
OUTFIT_FOR = {"finance": "formal", "fitness": "sporty", "hinglish_fun": "street", "motivation": "smart", "tech": "smart", "general": "smart"}

# How a talking video mixes the user with the AI pictures. The first and last scenes are always the user talking
# full-screen; the middle scenes show the user inside the AI picture, a talking bubble over it, or both.
LAYOUTS = {"both": "You + bubble", "scenes": "You in scenes", "bubble": "Bubble only"}

COMMUNITIES = {
    "general": dict(
        label="Global Feed (General)",
        examples=["why sleep matters", "5 quick hacks for Indian kitchen storage", "why we yawn when someone else yawns"],  # placeholder in the form and the subject anchor for suggestions
        tone="Clear, friendly, curiosity-driven for a broad Indian audience. One surprising fact or idea per scene.",
        language="en",
        caption_style="Two short lines: a bold claim or question, then an invitation to comment.",
        hashtags=["#Qoneqt", "#GlobalFeed"],
        voice_eleven="EXAVITQu4vr4xnSDxMaL",  # Sarah
        voice_gemini="Kore",
        gender="f",
        mood="calm",
        accent="FFE500",
    ),
    "tech": dict(
        label="Tech & AI",
        examples=["5 AI tools every student should know", "how UPI moves your money in seconds", "is your phone really listening to you"],
        tone="Punchy and concrete. One real fact, number, or tool per scene. No hype words.",
        language="en",
        caption_style="One-line insight, then 'Save this for later.'",
        hashtags=["#Tech", "#AI", "#Qoneqt"],
        voice_eleven="JBFqnCBsd6RMkjVDRZzb",  # George
        voice_gemini="Charon",
        gender="m",
        mood="electronic",
        accent="00E5FF",
    ),
    "fitness": dict(
        label="Fitness & Health",
        examples=["a 10-minute workout with no equipment", "how much water you really need in a day", "3 stretches for people who sit all day"],
        tone="Energetic coach voice. Second person, imperative, short sentences.",
        language="en",
        caption_style="One challenge line, then ask viewers to tag a friend.",
        hashtags=["#Fitness", "#Health", "#Qoneqt"],
        voice_eleven="nPczCjzI2devNBz1zQrb",  # Brian
        voice_gemini="Puck",
        gender="m",
        mood="electronic",
        accent="39FF14",
    ),
    "motivation": dict(
        label="Motivation",
        examples=["the 2-minute rule to beat procrastination", "why discipline beats motivation", "small wins that build big habits"],
        tone="Warm, story-led, builds to one takeaway line at the end.",
        language="en",
        caption_style="One quotable line, then ask what viewers are working on.",
        hashtags=["#Motivation", "#Mindset", "#Qoneqt"],
        voice_eleven="EXAVITQu4vr4xnSDxMaL",  # Sarah
        voice_gemini="Kore",
        gender="f",
        mood="inspiring",
        accent="FFB300",
    ),
    "finance": dict(
        label="Money & Finance",
        examples=["the 50-30-20 rule for your first salary", "SIP vs FD for beginners", "how to build an emergency fund"],
        tone="Plain money tips for young Indians. Spell every number out in words for the narrator.",
        language="en",
        caption_style="One actionable tip, then 'Not financial advice.'",
        hashtags=["#Finance", "#MoneyTips", "#Qoneqt"],
        voice_eleven="JBFqnCBsd6RMkjVDRZzb",  # George
        voice_gemini="Charon",
        gender="m",
        mood="calm",
        accent="00FF9C",
    ),
    "hinglish_fun": dict(
        label="Hinglish Fun",
        examples=["chai vs coffee", "har family WhatsApp group ke 5 log", "Monday morning vs Friday evening mood"],
        tone="Playful, desi references, light humour, the way young Indians talk to friends.",
        language="hinglish",
        caption_style="One funny line, then 'Comment karo agar relate kiya.'",
        hashtags=["#Hinglish", "#Desi", "#Qoneqt"],
        voice_eleven="nPczCjzI2devNBz1zQrb",  # Brian
        voice_gemini="Kore",
        gender="m",
        mood="upbeat",
        accent="FF2D95",
    ),
}
