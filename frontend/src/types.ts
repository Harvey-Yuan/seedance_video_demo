export type RunStatus =
  | "draft"
  | "layer1_running"
  | "layer1_done"
  | "layer2_running"
  | "layer2_done"
  | "layer3_running"
  | "done"
  | "failed";

export interface StoryboardShot {
  shot_id: string;
  visual: string;
  duration_hint_sec: number;
  camera_notes?: string;
}

export interface Layer1Output {
  storyboard: StoryboardShot[];
  script: string;
  characters: { name: string; description: string; voice_notes?: string }[];
  dialogue: { speaker: string; line: string; shot_ref?: string }[];
}

export interface Layer2Output {
  character_image_urls: string[];
  image_prompts_used?: string[];
  seedance_prompts: {
    segment_id: string;
    prompt: string;
    image_refs?: number[];
  }[];
}

export interface Layer3Output {
  video_url: string;
  model: string;
  duration_sec?: number;
  meta?: { product_note?: string };
}

export interface RunRow {
  id: string;
  user_id: string | null;
  status: RunStatus;
  drama_input: string;
  layer1_output: Layer1Output | null;
  layer2_output: Layer2Output | null;
  layer3_output: Layer3Output | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}
