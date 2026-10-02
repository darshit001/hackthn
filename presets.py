"""Community presets and language table. Adding a community or a language = adding one dict entry.
voice_eleven ids are ElevenLabs premade voices usable on the free API (Sarah, George, Brian verified 29 Sep 2026);
eleven_flash_v2_5 is multilingual, so the same voice speaks Hindi. gender picks the edge-tts voice from LANGUAGES.
language on a community is only the default language chip in the UI. accent is RRGGBB for the highlighted caption word."""

DURATIONS = [15, 30, 45, 60]

LANGUAGES = {
    "en": dict(
        label="English", whisper="en",
        instruction="English",
        voice_edge={"f": "en-IN-NeerjaNeural", "m": "en-IN-PrabhatNeural"},
    ),
    "hi": dict(
        label="हिन्दी", whisper="hi",
        instruction="Hindi in Devanagari script, simple everyday spoken Hindi; write every number as Hindi words",
        voice_edge={"f": "hi-IN-SwaraNeural", "m": "hi-IN-MadhurNeural"},
    ),
    "hinglish": dict(
        label="Hinglish", whisper="hi",
        instruction="Hinglish written in Roman script (a natural mix of Hindi and English, the way young Indians text)",
        voice_edge={"f": "en-IN-NeerjaNeural", "m": "en-IN-PrabhatNeural"},
    ),
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
        accent="FF2D95",
    ),
}
