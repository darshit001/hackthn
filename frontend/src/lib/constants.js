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

// An image post has three steps of its own; a card picks its stages and words with stepsFor(job)
export const IMAGE_STAGES = ["plan", "image", "poster"];
export const IMAGE_STEP = {
  plan: ["Text", "Writing the post"],
  image: ["Picture", "Drawing the picture"],
  poster: ["Poster", "Adding the headline"],
};
export const stepsFor = j => (j.kind === "image" ? [IMAGE_STAGES, IMAGE_STEP] : [STAGES, STEP]);

export const LABEL = { general: "General", tech: "Tech & AI", fitness: "Fitness", motivation: "Motivation", finance: "Finance", hinglish_fun: "Hinglish Fun", video: "Video", image: "Image" };
export const ICON = { general: "globe", tech: "cpu", fitness: "dumbbell", motivation: "flame", finance: "rupee", hinglish_fun: "smile" };
export const FORMULA = { question: "Question", bold_claim: "Bold claim", number: "Number", myth: "Myth", story: "Story", warning: "Warning" };

export const PER_PAGE = 12;  // fills whole rows at one, two or three columns
export const MAX_TOPICS = 10;
