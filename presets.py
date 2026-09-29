"""Community presets. Adding a community = adding one dict entry; nothing else changes.
voice_eleven ids are ElevenLabs premade voices usable on the free API (Sarah, George, Brian verified 29 Sep 2026).
accent is RRGGBB used for the highlighted caption word."""

COMMUNITIES = {
    "general": dict(
        label="Global Feed (General)",
        tone="Clear, friendly, curiosity-driven English for a broad Indian audience. One surprising fact or idea per scene.",
        language="en",
        caption_style="Two short lines: a bold claim or question, then an invitation to comment.",
        hashtags=["#Qoneqt", "#GlobalFeed"],
        voice_eleven="EXAVITQu4vr4xnSDxMaL",  # Sarah
        voice_gemini="Kore",
        voice_edge="en-IN-NeerjaNeural",
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
        voice_edge="en-US-GuyNeural",
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
        voice_edge="en-US-ChristopherNeural",
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
        voice_edge="en-US-AriaNeural",
        accent="FFB300",
    ),
    "finance": dict(
        label="Money & Finance",
        tone="Plain-English money tips for young Indians. Spell every number out in words for the narrator.",
        language="en",
        caption_style="One actionable tip, then 'Not financial advice.'",
        hashtags=["#Finance", "#MoneyTips", "#Qoneqt"],
        voice_eleven="JBFqnCBsd6RMkjVDRZzb",  # George
        voice_gemini="Charon",
        voice_edge="en-IN-PrabhatNeural",
        accent="00FF9C",
    ),
    "hinglish_fun": dict(
        label="Hinglish Fun",
        tone="Playful Hinglish in Roman script, mixing Hindi and English the way young Indians text. Desi references, light humour.",
        language="hinglish",
        caption_style="One funny Hinglish line, then 'Comment karo agar relate kiya.'",
        hashtags=["#Hinglish", "#Desi", "#Qoneqt"],
        voice_eleven="nPczCjzI2devNBz1zQrb",  # Brian
        voice_gemini="Kore",
        voice_edge="en-IN-NeerjaNeural",
        accent="FF2D95",
    ),
}
