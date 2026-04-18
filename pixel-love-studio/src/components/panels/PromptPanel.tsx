import { Copy, Check, Code2, Loader2 } from "lucide-react";
import { useState } from "react";
import { promptOutput } from "@/lib/mockData";
import { useRun } from "@/context/RunContext";
import { toast } from "sonner";
import type { SeedancePromptSegment } from "@/lib/api";

const KNOWN_SEGMENT_KEYS = new Set([
  "segment_id",
  "prompt",
  "segment_goal",
  "camera_notes",
  "image_refs",
  "image_roles",
  "duration_sec",
  "ratio",
  "resolution",
  "generate_audio",
  "camera_fixed",
  "seed",
]);

function formatValue(v: unknown): string {
  if (v === null || v === undefined) return "";
  if (typeof v === "boolean") return v ? "true" : "false";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function segmentParamRows(seg: SeedancePromptSegment): { key: string; value: string }[] {
  const rows: { key: string; value: string }[] = [];
  const push = (key: string, v: unknown) => {
    if (v === null || v === undefined) return;
    if (typeof v === "string" && !v.trim()) return;
    if (Array.isArray(v) && v.length === 0) return;
    rows.push({ key, value: formatValue(v) });
  };

  push("segment_goal", seg.segment_goal);
  push("camera_notes", seg.camera_notes);
  push("duration_sec", seg.duration_sec);
  push("ratio", seg.ratio);
  push("resolution", seg.resolution);
  push("image_refs", seg.image_refs);
  push("image_roles", seg.image_roles);
  push("generate_audio", seg.generate_audio);
  push("camera_fixed", seg.camera_fixed);
  push("seed", seg.seed);

  const raw = seg as Record<string, unknown>;
  for (const k of Object.keys(raw)) {
    if (KNOWN_SEGMENT_KEYS.has(k)) continue;
    const v = raw[k];
    if (v === null || v === undefined) continue;
    rows.push({ key: k, value: formatValue(v) });
  }

  return rows;
}

const SegmentCard = ({ seg }: { seg: SeedancePromptSegment }) => {
  const [copiedPrompt, setCopiedPrompt] = useState(false);
  const [copiedJson, setCopiedJson] = useState(false);
  const paramRows = segmentParamRows(seg);

  const copyPrompt = () => {
    navigator.clipboard.writeText(seg.prompt);
    setCopiedPrompt(true);
    toast.success("Prompt copied");
    setTimeout(() => setCopiedPrompt(false), 1500);
  };

  const copyJson = () => {
    navigator.clipboard.writeText(JSON.stringify(seg, null, 2));
    setCopiedJson(true);
    toast.success("Segment JSON copied");
    setTimeout(() => setCopiedJson(false), 1500);
  };

  return (
    <div className="overflow-hidden rounded-xl border-[3px] border-border bg-card">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b-2 border-border bg-muted/50 px-4 py-2">
        <div className="flex min-w-0 items-center gap-2">
          <Code2 className="h-3.5 w-3.5 shrink-0 text-primary" />
          <span className="truncate font-pixel text-[10px] uppercase text-foreground">{seg.segment_id}</span>
        </div>
        <div className="flex shrink-0 gap-1">
          <button
            type="button"
            onClick={copyPrompt}
            className="flex items-center gap-1 rounded-md border-2 border-border bg-card px-2 py-1 font-pixel text-[9px] hover:bg-primary hover:text-primary-foreground transition-colors"
          >
            {copiedPrompt ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
            {copiedPrompt ? "OK" : "Copy prompt"}
          </button>
          <button
            type="button"
            onClick={copyJson}
            className="flex items-center gap-1 rounded-md border-2 border-border bg-card px-2 py-1 font-pixel text-[9px] hover:bg-secondary hover:text-secondary-foreground transition-colors"
          >
            {copiedJson ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
            {copiedJson ? "OK" : "Copy JSON"}
          </button>
        </div>
      </div>
      <div className="bg-gradient-to-br from-card to-muted/30 p-4">
        <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-foreground/90">{seg.prompt}</pre>
      </div>
      {paramRows.length > 0 ? (
        <div className="border-t-2 border-border bg-muted/20 px-4 py-3">
          <div className="mb-2 font-pixel text-[9px] uppercase tracking-wider text-muted-foreground">Parameters</div>
          <dl className="space-y-2 font-mono text-[11px]">
            {paramRows.map(({ key, value }) => (
              <div key={key} className="grid gap-1 sm:grid-cols-[minmax(0,140px)_1fr] sm:gap-3">
                <dt className="shrink-0 text-primary/90">{key}</dt>
                <dd className="min-w-0 break-all text-foreground/85">{value}</dd>
              </div>
            ))}
          </dl>
        </div>
      ) : null}
    </div>
  );
};

const PanelSkeleton = ({ label, hint }: { label: string; hint?: string }) => (
  <div className="flex items-start gap-3 rounded-2xl border-2 border-dashed border-accent/50 bg-accent/5 p-5">
    <Loader2 className="mt-0.5 h-5 w-5 shrink-0 animate-spin text-accent-foreground" />
    <div>
      <p className="font-pixel text-[11px] text-foreground">{label}</p>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </div>
  </div>
);

const PromptPanel = () => {
  const { runId, run, status } = useRun();

  const layer2 = run?.layer2_output ?? null;
  const isLoading = !!runId && !layer2 && (
    status === "draft" ||
    status === "layer1_running" ||
    status === "layer1_done" ||
    status === "makeup_running" ||
    status === "makeup_done" ||
    status === "layer2_running"
  );

  if (isLoading) {
    return (
      <div className="space-y-4 animate-fade-in">
        <PanelSkeleton label="Director: building seedance_prompts…" hint="LLM output for each video segment." />
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-24 animate-pulse rounded-xl bg-muted/50" />
        ))}
      </div>
    );
  }

  if (runId && status === "failed" && !layer2) {
    return (
      <div className="rounded-2xl border-2 border-destructive/40 bg-destructive/10 p-5 font-pixel text-[11px] text-destructive">
        <p className="font-semibold">Director failed</p>
        <p className="mt-2 whitespace-pre-wrap text-xs opacity-90">{run?.error_message ?? "Run failed"}</p>
      </div>
    );
  }

  const segments = layer2?.seedance_prompts ?? null;
  const mock = promptOutput;

  if (!segments || segments.length === 0) {
    return (
      <div className="space-y-3">
        <p className="font-pixel text-[10px] uppercase text-muted-foreground">seedance_prompts</p>
        <div className="space-y-3">
          {mock.scenes.map((s) => (
            <div key={s.title} className="rounded-xl border-[3px] border-dashed border-border bg-muted/20 p-4">
              <div className="font-pixel text-[10px] text-foreground">{s.title}</div>
              <pre className="mt-2 whitespace-pre-wrap font-mono text-xs text-muted-foreground">{s.prompt}</pre>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4 animate-fade-in">
      <div className="font-pixel text-[10px] uppercase tracking-wider text-muted-foreground">seedance_prompts</div>
      <div className="space-y-4">
        {segments.map((seg) => (
          <SegmentCard key={seg.segment_id} seg={seg} />
        ))}
      </div>
    </div>
  );
};

export default PromptPanel;
