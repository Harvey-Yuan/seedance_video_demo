export const SAMPLE_STORY = `1:23 AM. He suddenly texts: "you up?"
I stared at the screen for a long time. Three months of silence. I thought I was over him.
The last time we met was at that little café — he said he "needed some time." Then nothing. No call, no message, no closure.
Now he says he misses me. Says he was wrong.
My fingers hover over the keyboard. I type, I delete, I type again.
The rain outside is loud — louder than all the things I never said back then.
Do I reply? Should I? And if I do… is it just going to be another beautiful mistake?`;

export const directorOutput = {
  summary:
    "A late-night text from an ex reopens a wound the protagonist thought had healed. Across three rainy minutes she relives a café goodbye, weighs hope against memory, and decides whether to reply.",
  beats: [
    { label: "Hook", text: "1:23 AM. A single 'You up?' lights up her phone." },
    { label: "Conflict", text: "Three months of carefully built silence cracks open." },
    { label: "Turning Point", text: "Flashback to the café — his quiet 'I need time'." },
    { label: "Twist", text: "He admits he was wrong, asks for a second chance." },
    { label: "Ending", text: "Her thumb hovers. The screen dims. Cut to black." },
  ],
  shots: [
    { id: "S1", desc: "Close-up: phone screen glowing in the dark, single message bubble." },
    { id: "S2", desc: "Medium: girl in bed, blanket pulled up, eyes wide and wet." },
    { id: "S3", desc: "Flashback: café window, rain streaks, two coffees going cold." },
    { id: "S4", desc: "Insert: thumb hovering over keyboard, message half-typed." },
    { id: "S5", desc: "Wide: bedroom dark, only phone light. Rain on window." },
  ],
  dialogue: [
    { who: "HIM (text)", line: "you up?" },
    { who: "HIM (text)", line: "i was wrong. i miss you." },
    { who: "HER (V.O.)", line: "Three months. I built a life out of not answering." },
    { who: "HER (V.O.)", line: "And he writes nine letters and I'm seventeen again." },
  ],
  roles: [
    {
      name: "LIN — Female Lead",
      desc: "24, soft-spoken graphic designer. Wears oversized sweaters. Heart on sleeve, walls around it.",
    },
    {
      name: "CHEN — Male Lead",
      desc: "26, ambitious, emotionally late. The kind who realizes love only after losing it.",
    },
  ],
};

export const visualOutput = {
  characters: [
    { name: "Lin", desc: "Pastel lavender sweater, messy bun, mascara-smudged eyes, soft blush." },
    { name: "Chen", desc: "Charcoal hoodie, tired eyes, faint stubble, illuminated by phone glow." },
  ],
  scenes: [
    { name: "Bedroom @ 1AM", desc: "Warm fairy lights, navy walls, rain on window, phone-glow on face." },
    { name: "Café Flashback", desc: "Golden hour, two ceramic mugs, condensation, soft jazz mood." },
    { name: "Rainy Street", desc: "Neon reflections in puddles, umbrella, lavender-pink sky." },
  ],
  styleKeywords: ["cinematic", "pastel romance", "pixel-cinematic", "soft bokeh", "rainy night", "anime-inspired", "16:9 → 9:16", "warm rim light"],
  promptIngredients: [
    "subject: young woman, 24, lavender sweater",
    "lighting: phone-glow + warm fairy lights",
    "mood: nostalgic, hesitant, tender",
    "palette: pastel pink, lavender, deep navy",
    "lens: 50mm, shallow depth, soft bokeh",
  ],
};

export const promptOutput = {
  finalImage:
    "cinematic still, young asian woman in oversized lavender sweater lying in bed at 1am, illuminated by phone screen glow, single tear, fairy lights, rainy window, pastel romance palette, shallow depth of field, 50mm, ultra detailed",
  finalVideo:
    "9:16 short drama clip, 8 seconds, slow push-in on protagonist staring at phone, rain ambience, subtle hand tremor, pastel cinematic grade, romantic melancholy",
  scenes: [
    {
      title: "Scene 1 — The Notification",
      prompt:
        "close-up shot, smartphone screen at 1:23 AM, single message bubble 'you up?', soft bokeh bedroom background, rain on window, cinematic, pastel grade",
      camera: "static close-up, slow zoom in",
    },
    {
      title: "Scene 2 — The Flashback",
      prompt:
        "café interior, golden hour, two coffee cups between a young couple, woman looking down, man looking out window, melancholic, 35mm film grain",
      camera: "slow dolly in, rack focus from cup to face",
    },
    {
      title: "Scene 3 — The Decision",
      prompt:
        "overhead shot, hand hovering over phone keyboard, message half-typed 'I—', screen dims, dark bedroom, rim light",
      camera: "top-down, slow pull back",
    },
  ],
  styleTag: "cinematic · romantic · pastel · pixel-inspired · 9:16",
};

export const seedanceOutput = {
  status: "Completed",
  duration: "00:24",
  resolution: "1080 × 1920 (9:16)",
  model: "Seedance v2.1 — Cinematic",
  scenes: [
    { id: 1, title: "Notification", duration: "0:06" },
    { id: 2, title: "Flashback Café", duration: "0:08" },
    { id: 3, title: "Hesitation", duration: "0:06" },
    { id: 4, title: "Cut to Black", duration: "0:04" },
  ],
};
