export type RunStatus =
  | "draft"
  | "layer1_running"
  | "layer1_done"
  | "makeup_running"
  | "makeup_done"
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

export interface MakeupOutput {
  character_image_urls: string[];
  makeup_prompts?: string[];
  meta?: Record<string, unknown>;
}

export interface SeedancePromptSegment {
  segment_id: string;
  prompt: string;
  segment_goal?: string;
  camera_notes?: string;
  image_refs?: number[];
  image_roles?: string[];
  duration_sec?: number;
  ratio?: string;
  resolution?: string;
  generate_audio?: boolean;
  camera_fixed?: boolean;
  seed?: number;
}

export interface Layer2Output {
  director_notes?: string;
  character_image_urls: string[];
  image_prompts_used?: string[];
  seedance_prompts: SeedancePromptSegment[];
}

export interface Layer3Output {
  video_url: string;
  model: string;
  duration_sec?: number;
  meta?: {
    product_note?: string;
    segment_urls?: string[];
    storage_object_id?: string;
    upload_error?: string;
    upload_skipped?: boolean;
    merged_bytes?: number;
  };
}

export type SeedanceJobPhase =
  | "idle"
  | "queued"
  | "generating"
  | "merging"
  | "uploading"
  | "done"
  | "failed";

/** GET /api/runs/{id}/seedance/status response (aligned with DB seedance_job) */
export interface SeedanceJobStatus {
  phase: SeedanceJobPhase | string;
  total_segments?: number;
  segment_urls?: string[];
  current_segment_index?: number;
  model?: string;
  merged_bytes?: number;
  video_url?: string;
  storage_object_id?: string;
  upload_skipped?: boolean;
  upload_error?: string;
  error_code?: string;
  error_message?: string;
  run_status?: string;
  message?: string;
  layer3?: Layer3Output;
}

export interface RunRow {
  id: string;
  user_id: string | null;
  status: RunStatus;
  drama_input: string;
  layer1_output: Layer1Output | null;
  makeup_output: MakeupOutput | null;
  layer2_output: Layer2Output | null;
  layer3_output: Layer3Output | null;
  seedance_job?: Record<string, unknown> | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}
