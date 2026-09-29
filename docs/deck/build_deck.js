// Builds the 7-slide Round-2 deck. Run: node build_deck.js  (from docs/deck)
// Slide order follows the organiser's template exactly.
const pptxgen = require("pptxgenjs");
const path = require("path");

const TEAM = process.env.TEAM || "[Team Name]";
const TEAM_ID = process.env.TEAM_ID || "[Team ID]";
const COLLEGE = process.env.COLLEGE || "[College Name]";
const GITHUB = process.env.GITHUB_URL || "github.com/<user>/qoneqt-video-factory";
const LIVE = process.env.LIVE_URL || "huggingface.co/spaces/<user>/qoneqt-video-factory";

const BG = "0B0416", CARD = "160A2B", CARD2 = "1E0F3A", LINE = "2D1B4E", TXT = "F3EEFC", MUT = "A89CC4",
  ACC = "8B5CF6", ACC2 = "C4B5FD", YEL = "FFE500", WHITE = "FFFFFF";
const FONT = "Calibri";
const IMG = (f) => path.join(__dirname, "..", "screens", f);
const BGIMG = (n) => path.join(__dirname, "bg", `slide-0${n}.jpg`); // glassmorphism backgrounds from gen_image.py (ppt-generation skill workflow)

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625 in
pres.author = TEAM;
pres.title = "Qoneqt Video Factory";

// ---------- helpers ----------
function base(n, title, kicker) {
  const s = pres.addSlide();
  s.background = { path: BGIMG(n) };
  if (kicker) s.addText(kicker, { x: 0.5, y: 0.28, w: 7, h: 0.3, fontFace: FONT, fontSize: 11, color: ACC2, bold: true, charSpacing: 2, margin: 0, isTextBox: true });
  s.addText(title, { x: 0.5, y: kicker ? 0.55 : 0.4, w: 8.2, h: 0.6, fontFace: FONT, fontSize: 26, bold: true, color: WHITE, margin: 0, isTextBox: true });
  s.addText(`0${n} / 07`, { x: 8.7, y: 0.3, w: 0.8, h: 0.3, fontFace: FONT, fontSize: 10, color: MUT, align: "right", margin: 0, isTextBox: true });
  s.addText("Qoneqt × CTRL FREAK 2026  ·  Qoneqt Video Factory", { x: 0.5, y: 5.25, w: 6, h: 0.25, fontFace: FONT, fontSize: 9, color: MUT, margin: 0, isTextBox: true });
  return s;
}
function card(s, x, y, w, h, fill = CARD) {
  // frosted glass: dark glass for text cards, light glass for stat callouts
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: "120826", transparency: fill === CARD2 ? 18 : 26 }, line: { color: "FFFFFF", transparency: 60, width: 0.75 }, rectRadius: 0.1 });
}
function num(s, x, y, n, d = 0.36) {
  s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: ACC }, line: { color: ACC, width: 0 } });
  s.addText(String(n), { x, y, w: d, h: d, fontFace: FONT, fontSize: 13, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0, isTextBox: true });
}
function head(s, x, y, w, text, size = 14) {
  s.addText(text, { x, y, w, h: 0.32, fontFace: FONT, fontSize: size, bold: true, color: WHITE, margin: 0, isTextBox: true });
}
function body(s, x, y, w, h, text, size = 11.5, color = TXT) {
  s.addText(text, { x, y, w, h, fontFace: FONT, fontSize: size, color, margin: 0, valign: "top", isTextBox: true });
}
function bullets(s, x, y, w, h, items, size = 11.5) {
  s.addText(items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1, paraSpaceAfter: 4 } })),
    { x, y, w, h, fontFace: FONT, fontSize: size, color: TXT, margin: 0, valign: "top", isTextBox: true });
}
function stat(s, x, y, w, big, label) {
  card(s, x, y, w, 1.15, CARD2);
  s.addText(big, { x, y: y + 0.1, w, h: 0.6, fontFace: FONT, fontSize: 30, bold: true, color: YEL, align: "center", margin: 0, isTextBox: true });
  s.addText(label, { x: x + 0.1, y: y + 0.7, w: w - 0.2, h: 0.4, fontFace: FONT, fontSize: 10.5, color: MUT, align: "center", margin: 0, isTextBox: true });
}
function arrow(s, x, y, w) {
  s.addShape(pres.shapes.LINE, { x, y, w, h: 0, line: { color: ACC2, width: 1.5, endArrowType: "triangle" } });
}

// ---------- 1. Title ----------
{
  const s = pres.addSlide();
  s.background = { path: BGIMG(1) };
  s.addText("QONEQT AI CHALLENGE  ·  PART 2  ·  CTRL FREAK 2026", { x: 0.6, y: 0.7, w: 6, h: 0.3, fontFace: FONT, fontSize: 11, color: ACC2, bold: true, charSpacing: 2, margin: 0, isTextBox: true });
  s.addText([{ text: "Qoneqt ", options: { color: WHITE } }, { text: "Video Factory", options: { color: ACC2 } }],
    { x: 0.6, y: 1.05, w: 5.6, h: 0.9, fontFace: FONT, fontSize: 34, bold: true, margin: 0, isTextBox: true });
  s.addText("Topic in. Global Feed short out.", { x: 0.6, y: 1.95, w: 5.6, h: 0.45, fontFace: FONT, fontSize: 20, color: MUT, italic: true, margin: 0, isTextBox: true });
  body(s, 0.6, 2.55, 5.4, 0.6, "Theme: Build an LLM-Powered Content Pipeline for Qoneqt. A repeatable system that turns a topic into a publish-ready, captioned vertical video for the Qoneqt Global Feed.", 12.5, TXT);
  card(s, 0.6, 3.45, 5.2, 1.35);
  s.addText("TEAM", { x: 0.85, y: 3.6, w: 2, h: 0.25, fontFace: FONT, fontSize: 9.5, color: MUT, bold: true, charSpacing: 2, margin: 0, isTextBox: true });
  s.addText(`${TEAM}  ·  ${TEAM_ID}`, { x: 0.85, y: 3.85, w: 4.8, h: 0.4, fontFace: FONT, fontSize: 16, bold: true, color: TEAM.startsWith("[") ? YEL : WHITE, margin: 0, isTextBox: true });
  s.addText("COLLEGE", { x: 0.85, y: 4.25, w: 2, h: 0.25, fontFace: FONT, fontSize: 9.5, color: MUT, bold: true, charSpacing: 2, margin: 0, isTextBox: true });
  s.addText(COLLEGE, { x: 0.85, y: 4.48, w: 4.8, h: 0.32, fontFace: FONT, fontSize: 13, color: COLLEGE.startsWith("[") ? YEL : TXT, margin: 0, isTextBox: true });
  // three generated shorts, staggered like a feed
  const fw = 1.25, fh = fw * 16 / 9;
  s.addImage({ path: IMG("frames/tech.png"), x: 6.15, y: 1.0, w: fw, h: fh });
  s.addImage({ path: IMG("frames/motivation.png"), x: 7.5, y: 0.65, w: fw, h: fh });
  s.addImage({ path: IMG("frames/hinglish.png"), x: 8.85 - 0.1, y: 1.0, w: fw, h: fh });
  card(s, 6.15, 3.32, 3.35, 0.55);
  s.addText("Three shorts generated by the pipeline tonight: Tech, Motivation, Hinglish presets", { x: 6.25, y: 3.35, w: 3.15, h: 0.5, fontFace: FONT, fontSize: 9.5, color: TXT, align: "center", valign: "middle", margin: 0, isTextBox: true });
  s.addText("Qoneqt × CTRL FREAK 2026", { x: 0.6, y: 5.25, w: 6, h: 0.25, fontFace: FONT, fontSize: 9, color: MUT, margin: 0, isTextBox: true });
  s.addNotes("Title slide. Team details on the left, three real outputs from tonight's run on the right.");
}

// ---------- 2. Problem + gap ----------
{
  const s = base(2, "The Global Feed is hungry. Video is slow.", "PROBLEM  +  EXISTING GAP");
  head(s, 0.5, 1.35, 4.2, "What is the problem?");
  body(s, 0.5, 1.7, 4.2, 1.1, "A social feed lives on fresh video every day. Making one 30-second short by hand means writing a script, finding visuals, recording a voice, editing, and adding captions. A creator manages one a day. The Global Feed needs hundreds.", 12);
  stat(s, 0.5, 2.95, 2.0, "2–4 hrs", "to hand-make one 30-second short");
  stat(s, 2.7, 2.95, 2.0, "0", "Qoneqt-native topic-to-video tools");
  body(s, 0.5, 4.25, 4.2, 0.8, "Result: thin, repetitive video content, creators who burn out, and communities that go quiet between posts.", 11.5, MUT);

  const rx = 5.1, rw = 4.4;
  card(s, rx, 1.3, rw, 1.15); num(s, rx + 0.15, 1.42, "?");
  head(s, rx + 0.65, 1.4, rw - 0.8, "Who is affected");
  body(s, rx + 0.65, 1.72, rw - 0.8, 0.7, "Qoneqt creators and community admins who must post daily, and the platform, whose Global Feed runs on steady video.", 10.5);
  card(s, rx, 2.55, rw, 1.15); num(s, rx + 0.15, 2.67, "~");
  head(s, rx + 0.65, 2.65, rw - 0.8, "Current solutions");
  body(s, rx + 0.65, 2.97, rw - 0.8, 0.7, "Manual editing apps (CapCut, Canva), one-shot AI video generators on paid credits, or hiring an agency. All produce one video at a time.", 10.5);
  card(s, rx, 3.8, rw, 1.3); num(s, rx + 0.15, 3.92, "!");
  head(s, rx + 0.65, 3.9, rw - 0.8, "Key gaps");
  bullets(s, rx + 0.65, 4.22, rw - 0.8, 0.85, ["Not repeatable: no batch, no pipeline", "Not community-aware: generic tone", "Paid per video; no enforced hook or captions"], 10);
  s.addNotes("Problem: feeds need constant video; hand-made shorts take hours. Gap: no repeatable, community-aware, zero-cost pipeline exists for Qoneqt.");
}

// ---------- 3. Proposed solution ----------
{
  const s = base(3, "A video factory, not a video button", "PROPOSED SOLUTION");
  s.addText("Type a topic. Pick a community. Get a publish-ready short and its post text in about a minute.",
    { x: 0.5, y: 1.25, w: 9, h: 0.5, fontFace: FONT, fontSize: 16, bold: true, color: ACC2, margin: 0, isTextBox: true });
  const steps = [
    ["Plan", "The LLM writes 3 hooks, scores them, keeps the best, then a 5–7 scene script with a stock-search query per scene, plus caption and hashtags."],
    ["Produce", "An AI voice reads each scene. An AI still is generated per scene, or a photo fetched, then given motion. Whisper gives word timings for word-pop captions."],
    ["Publish", "ffmpeg assembles a 1080×1920 MP4 with burned-in captions. The app hands you the video, caption, and hashtags ready to paste into Qoneqt."],
  ];
  steps.forEach(([h, t], i) => {
    const x = 0.5 + i * 3.05;
    card(s, x, 1.9, 2.85, 1.45); num(s, x + 0.15, 2.03, i + 1);
    head(s, x + 0.65, 2.05, 2.1, h, 15);
    body(s, x + 0.15, 2.45, 2.55, 0.85, t, 10.5);
  });
  head(s, 0.5, 3.55, 9, "What makes it better than existing options", 13);
  const rows = [
    [{ text: "", options: { fill: { color: BG } } }, "Manual editing", "One-shot AI tools", { text: "Video Factory", options: { bold: true, color: WHITE } }],
    ["Repeatable at scale", "No", "No", { text: "Yes, batch of 10 per click", options: { color: YEL, bold: true } }],
    ["Community-aware tone", "By hand", "No", { text: "6 presets, one dict entry each", options: { color: YEL, bold: true } }],
    ["Hook, captions, post text", "By hand", "Partly", { text: "Built in, every video", options: { color: YEL, bold: true } }],
    ["Cost per video", "Hours", "Paid credits", { text: "₹0 on free tiers", options: { color: YEL, bold: true } }],
  ];
  s.addTable(rows.map((r, ri) => r.map((c, ci) => {
    const o = typeof c === "string" ? { text: c, options: {} } : c;
    o.options = Object.assign({ fontFace: FONT, fontSize: 9.5, color: ri === 0 ? MUT : TXT, bold: ri === 0 || ci === 0 ? true : o.options.bold, fill: { color: ri === 0 ? BG : CARD }, margin: 0.04, valign: "middle" }, o.options);
    return o;
  })), { x: 0.5, y: 3.88, w: 9, colW: [2.4, 1.8, 1.9, 2.9], rowH: 0.16, border: { type: "solid", color: LINE, pt: 0.5 } });
  s.addNotes("Solution in one line, then three steps, then a comparison table against manual editing and one-shot AI tools.");
}

// ---------- 4. Architecture + stack ----------
{
  const s = base(4, "Input → Process → Output", "ARCHITECTURE  +  TECH STACK");
  const flow = [
    ["Input", "Topic + community preset", CARD2],
    ["1  Plan", "Groq gpt-oss-120b\n(fallback qwen, Gemini)", CARD],
    ["2  Images", "Pollinations FLUX\nAI still per scene", CARD],
    ["3  Voice", "ElevenLabs\n(fallback edge-tts)", CARD],
    ["4  Visuals", "AI still or Wikimedia\nphoto, pan-zoom", CARD],
    ["5  Captions", "Groq Whisper\nword timestamps", CARD],
    ["6  Render", "ffmpeg 1080×1920\nburned-in captions", CARD],
    ["Output", "MP4 + thumbnail + post text", CARD2],
  ];
  const bw = 1.03, gap = 0.108, y = 1.35, h = 1.15;
  flow.forEach(([h1, t, fill], i) => {
    const x = 0.5 + i * (bw + gap);
    card(s, x, y, bw, h, fill);
    s.addText(h1, { x: x + 0.05, y: y + 0.08, w: bw - 0.1, h: 0.3, fontFace: FONT, fontSize: 10.5, bold: true, color: i === 0 || i === 7 ? ACC2 : WHITE, align: "center", margin: 0, isTextBox: true });
    s.addText(t, { x: x + 0.05, y: y + 0.4, w: bw - 0.1, h: 0.7, fontFace: FONT, fontSize: 8, color: MUT, align: "center", valign: "top", margin: 0, isTextBox: true });
    if (i < flow.length - 1) arrow(s, x + bw, y + h / 2, gap);
  });
  body(s, 0.5, 2.6, 9, 0.3, "Every stage has a fallback chain, so one flaky free API never kills a job. A single worker thread drains the job queue; batch mode is just N queued topics.", 10.5, TXT);
  const comps = [
    ["Frontend", "One static HTML page. Textarea for topics (one per line), community dropdown, live stage progress, inline player, Copy post text, Download."],
    ["Backend", "FastAPI. POST /generate, GET /jobs, static /out. In-memory job dict, one worker thread, files per job in out/<id>/."],
    ["AI layer", "LLM for plan JSON (validated, guided retry). TTS per scene. Photo or clip search per scene. Whisper word timings aligned to script words."],
    ["Data + deploy", "Outputs as files (mp4, jpg, json). Docker image with ffmpeg and Noto fonts. Deployed on a free Hugging Face Space, keys as secrets."],
  ];
  comps.forEach(([h1, t], i) => {
    const x = 0.5 + i * 2.28;
    card(s, x, 3.0, 2.15, 1.55);
    head(s, x + 0.15, 3.1, 1.9, h1, 13);
    body(s, x + 0.15, 3.42, 1.9, 1.1, t, 9.5);
  });
  s.addText([{ text: "Stack  ", options: { bold: true, color: ACC2 } }, { text: "Python 3.11 · FastAPI · httpx · ffmpeg · Docker · Groq (gpt-oss-120b, Whisper large-v3-turbo) · Pollinations FLUX · Hugging Face Spaces · ElevenLabs · edge-tts · Wikimedia Commons" }],
    { x: 0.5, y: 4.7, w: 9, h: 0.45, fontFace: FONT, fontSize: 10.5, color: TXT, margin: 0, isTextBox: true });
  s.addNotes("Five-stage pipeline with fallbacks. Frontend, backend, AI layer, data and deploy components. Stack line at the bottom.");
}

// ---------- 5. Key features ----------
{
  const s = base(5, "Five things that make it work", "KEY FEATURES");
  const feats = [
    ["Community presets", "Six Qoneqt communities (General, Tech, Fitness, Motivation, Finance, Hinglish Fun). Each sets tone, language, narrator voice, caption style, hashtags, and caption colour. Adding one is a single dict entry."],
    ["Self-scored hooks", "The LLM writes three opening lines, scores each for scroll-stopping power, and the best one opens the video. Quality control inside the prompt, zero extra calls."],
    ["Word-pop captions", "Whisper word timestamps drive karaoke-style captions: each spoken word lights up in the preset colour, aligned back to the script's own spelling. The look that performs on shorts."],
    ["Batch and fallbacks", "Ten topics per click, one worker, no babysitting. Every stage has a fallback (LLM, voice, stock, captions), so the factory keeps producing when a free API blinks."],
    ["Post-ready output", "Not just an MP4. Hook, caption, and hashtags come out together, with a one-click Copy post text button, so publishing to Qoneqt is a 30-second manual step."],
  ];
  const w = 2.85, h = 1.75;
  feats.forEach(([h1, t], i) => {
    const col = i % 3, row = Math.floor(i / 3);
    const x = 0.5 + col * (w + 0.22), y = 1.35 + row * (h + 0.2);
    card(s, x, y, w, h); num(s, x + 0.15, y + 0.15, i + 1);
    head(s, x + 0.65, y + 0.17, w - 0.8, h1, 13.5);
    body(s, x + 0.15, y + 0.6, w - 0.3, h - 0.7, t, 10);
  });
  // slot 6: a real caption frame
  const fx = 0.5 + 2 * (w + 0.22), fy = 1.35 + h + 0.2;
  card(s, fx, fy, w, h, CARD2);
  s.addImage({ path: IMG("frames/hinglish.png"), x: fx + 0.15, y: fy + 0.12, w: 0.85, h: 0.85 * 16 / 9 });
  s.addText("Real output frame", { x: fx + 1.1, y: fy + 0.15, w: w - 1.25, h: 0.3, fontFace: FONT, fontSize: 12, bold: true, color: ACC2, margin: 0, isTextBox: true });
  body(s, fx + 1.1, fy + 0.5, w - 1.25, 1.15, "Hinglish preset, edge-tts fallback voice, Whisper-timed captions, pink accent word. Generated, not mocked.", 9.5, TXT);
  s.addNotes("Five features. The sixth slot shows a real frame from a Hinglish video generated tonight.");
}

// ---------- 6. Impact + feasibility ----------
{
  const s = base(6, "Impact and feasibility", "IMPACT  +  FEASIBILITY");
  stat(s, 0.5, 1.3, 2.1, "₹0", "API cost per video on free tiers");
  stat(s, 2.8, 1.3, 2.1, "~1 min", "to make a 30–45 s short (measured tonight)");
  stat(s, 5.1, 1.3, 2.1, "10", "topics per click in batch mode");
  stat(s, 7.4, 1.3, 2.1, "6", "community presets, one dict entry to add more");
  card(s, 0.5, 2.7, 4.4, 2.35);
  head(s, 0.7, 2.82, 4, "Who benefits and how");
  bullets(s, 0.7, 3.17, 4.05, 1.8, [
    "Creators: turn ideas into daily shorts without editing skills or hours of work",
    "Community admins: on-tone videos in their own voice, Hinglish included",
    "Qoneqt: a steadier, higher-quality stream on the Global Feed, and a tool it can offer creators natively",
    "Real-world: 100 topics in overnight, 100 publish-ready videos out",
  ], 10.5);
  card(s, 5.1, 2.7, 4.4, 2.35);
  head(s, 5.3, 2.82, 4, "Scalability and feasibility");
  bullets(s, 5.3, 3.17, 4.05, 1.8, [
    "One free CPU: ~40–60 videos/hour per worker; scale by adding workers",
    "Free tiers: Groq LLM + Whisper, ElevenLabs (edge-tts fallback), Wikimedia visuals",
    "One Docker container on a free Hugging Face Space; keys stay secret",
    "Working end to end today; live URL and Global Feed post by the finale",
  ], 10.5);
  s.addNotes("Impact for creators, admins, and Qoneqt. Feasibility: measured timings, free-tier limits, one-container deploy.");
}

// ---------- 7. Demo + conclusion ----------
{
  const s = base(7, "Built and running tonight", "DEMO  +  CONCLUSION");
  s.addImage({ path: IMG("ui-top.png"), x: 0.5, y: 1.3, w: 3.3, h: 3.3 * 1120 / 994 });
  const rx = 4.4, rw = 5.1;
  head(s, rx, 1.3, rw, "What the prototype does today");
  bullets(s, rx, 1.65, rw, 1.25, [
    "Batch of three topics queued from the page; each ran plan → images → voice → visuals → captions → render with live progress",
    "34-second videos produced in about 55 seconds each, ElevenLabs voice, word-pop captions, post text ready to copy",
    "Hinglish preset verified on the fallback voice; every stage's fallback exercised",
  ], 10.5);
  card(s, rx, 2.95, rw, 0.95, CARD2);
  s.addText([{ text: "GitHub  ", options: { bold: true, color: ACC2 } }, { text: GITHUB, options: { color: GITHUB.includes("<") ? YEL : TXT } }, { text: "\nLive demo  ", options: { bold: true, color: ACC2 } }, { text: LIVE, options: { color: LIVE.includes("<") ? YEL : TXT } }],
    { x: rx + 0.15, y: 3.02, w: rw - 0.3, h: 0.8, fontFace: FONT, fontSize: 10.5, margin: 0, valign: "middle", isTextBox: true });
  s.addText("Qoneqt doesn't need one AI video. It needs a factory. We built the factory.",
    { x: rx, y: 3.98, w: rw, h: 0.55, fontFace: FONT, fontSize: 15, bold: true, color: WHITE, italic: true, margin: 0, isTextBox: true });
  body(s, rx, 4.58, rw, 0.55, "Why select this: it already ships, costs nothing to run, speaks each community's language, and is built on Qoneqt's real content format, not a concept.", 10, TXT);
  s.addNotes("Live screenshot from tonight on the left. Links, one-line conclusion, and the selection case on the right.");
}

const out = path.join(__dirname, "Qoneqt-Video-Factory.pptx");
pres.writeFile({ fileName: out }).then(() => console.log("wrote", out));
