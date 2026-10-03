export const STAGES = ["plan", "images", "voice", "visuals", "captions", "render"];

// stage -> [word on the phone screen and step bar, sentence under the bars]
export const STEP = {
  plan: ["Script", "Writing the script"],
  images: ["Images", "Generating images"],
  voice: ["Voice", "Recording the voice"],
  visuals: ["Scenes", "Building the scenes"],
  captions: ["Captions", "Timing the captions"],
  render: ["Render", "Rendering the video"],
};

export const LABEL = { general: "General", tech: "Tech & AI", fitness: "Fitness", motivation: "Motivation", finance: "Finance", hinglish_fun: "Hinglish Fun" };
export const ICON = { general: "globe", tech: "cpu", fitness: "dumbbell", motivation: "flame", finance: "rupee", hinglish_fun: "smile" };
export const FORMULA = { question: "Question", bold_claim: "Bold claim", number: "Number", myth: "Myth", story: "Story", warning: "Warning" };

export const PER_PAGE = 9;  // three rows of three on a wide screen
export const MAX_TOPICS = 10;
