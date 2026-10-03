"""Community presets and language table. Adding a community or a language = adding one dict entry.
voice_eleven ids are ElevenLabs premade voices usable on the free API (Sarah, George, Brian verified 29 Sep 2026);
eleven_flash_v2_5 is multilingual, so the same voice speaks Hindi. gender picks the edge-tts voice from LANGUAGES.
language on a community is only the default language chip in the UI. accent is RRGGBB for the highlighted caption word.
wps = effective spoken words per second for the edge-tts voices at media.EDGE_RATE, including the pause each scene adds
(measured 2 Oct 2026); it sizes the script for a target length. ElevenLabs speaks ~15% faster, so its videos run a little short.
script = regex character range a translation into this language must use (None: Roman script, no Indic letters).
mood picks the background track from MUSIC (Kevin MacLeod, incompetech.com, CC BY 4.0; credited in the job JSON and README)."""

DURATIONS = [15, 30, 45, 60]

LANGUAGES = {
    "en": dict(
        label="English", script=None, whisper="en", wps=2.4,
        instruction="English",
        voice_edge={"f": "en-IN-NeerjaNeural", "m": "en-IN-PrabhatNeural"},
    ),
    "hi": dict(
        label="हिन्दी", script="ऀ-ॿ", whisper="hi", wps=2.1,
        instruction="Hindi in Devanagari script, simple everyday spoken Hindi; write every number as Hindi words",
        voice_edge={"f": "hi-IN-SwaraNeural", "m": "hi-IN-MadhurNeural"},
    ),
    "hinglish": dict(
        label="Hinglish", script=None, whisper="hi", wps=2.2,
        instruction="Hinglish written in Roman script (a natural mix of Hindi and English, the way young Indians text)",
        voice_edge={"f": "en-IN-NeerjaNeural", "m": "en-IN-PrabhatNeural"},
    ),
    "gu": dict(
        label="ગુજરાતી", script="઀-૿", whisper="gu", wps=1.7,
        instruction="Gujarati in Gujarati script, simple everyday spoken Gujarati; write every number as Gujarati words",
        voice_edge={"f": "gu-IN-DhwaniNeural", "m": "gu-IN-NiranjanNeural"},
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

COMMUNITIES = {
    "general": dict(
        label="Global Feed (General)",
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
