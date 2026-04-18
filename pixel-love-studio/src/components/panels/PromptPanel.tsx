import { Copy, Check, Camera, Package, Code2, Loader2 } from "lucide-react";
import { useState } from "react";
import { promptOutput } from "@/lib/mockData";
import { useRun } from "@/context/RunContext";
import { toast } from "sonner";

const PromptCard = ({ title, prompt, camera }: { title: string; prompt: string; camera?: string }) => {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(prompt);
    setCopied(true);
    toast.success("Prompt copied ♡");
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <div className="overflow-hidden rounded-xl border-[3px] border-border bg-card">
      <div className="flex items-center justify-between border-b-2 border-border bg-muted/50 px-4 py-2">
        <div className="flex items-center gap-2">
          <Code2 className="h-3.5 w-3.5 text-primary" />
          <span className="font-pixel text-[10px] uppercase text-foreground">{title}</span>
        </div>
        <button
          onClick={copy}
          className="flex items-center gap-1 rounded-md border-2 border-border bg-card px-2 py-1 font-pixel text-[9px] hover:bg-primary hover:text-primary-foreground transition-colors"
        >
          {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
          {copied ? "OK" : "COPY"}
        </button>
      </div>
      <div className="bg-gradient-to-br from-card to-muted/30 p-4">
        <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-foreground/90">{prompt}</pre>
        {camera && (
          <div className="mt-3 flex items-center gap-1.5 text-xs text-muted-foreground">
            <Camera className="h-3 w-3" />
            <span className="italic">{camera}</span>
          </div>
        )}
      </div>
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
    status === "draft" || status === "layer1_running" || status === "layer1_done" ||
    status === "makeup_running" || status === "makeup_done" || status === "layer2_running"
  );

  if (isLoading) {
    return (
      <div className="space-y-4 animate-fade-in">
        <PanelSkeleton
          label="Assembling prompts…"
          hint="Director LLM is combining storyboard + makeup refs into per-segment video prompts."
        />
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-24 animate-pulse rounded-xl bg-muted/50" />
        ))}
      </div>
    );
  }

  const mock = promptOutput;
  const segments = layer2?.seedance_prompts ?? null;
  const directorNotes = layer2?.director_notes;

  const scenes = segments
    ? segments.map((p) => ({
        title: p.segment_id,
        prompt: p.prompt,
        camera: [p.camera_notes, p.ratio, p.resolution, p.duration_sec ? `${p.duration_sec}s` : null]
          .filter(Boolean)
          .join(" · ") || undefined,
      }))
    : mock.scenes;

  const styleTag = segments
    ? [...new Set(segments.map((p) => p.ratio).filter(Boolean))].join(" · ") || mock.styleTag
    : mock.styleTag;

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border-[3px] border-primary bg-gradient-to-r from-primary-glow/40 to-secondary/40 p-4">
        <div className="flex items-center gap-2">
          <Package className="h-5 w-5 text-primary" />
          <span className="font-pixel text-[11px] text-foreground">Prompt Packaging</span>
        </div>
        <span className="rounded-full border-2 border-foreground/15 bg-primary px-3 py-1 font-pixel text-[9px] text-primary-foreground animate-glow-pulse">
          ♡ PROMPT READY
        </span>
      </div>

      {directorNotes ? (
        <PromptCard title="Director Notes" prompt={directorNotes} />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          <PromptCard title="Final Image Prompt" prompt={mock.finalImage} />
          <PromptCard title="Final Video Prompt" prompt={mock.finalVideo} />
        </div>
      )}

      <div>
        <div className="mb-3 flex items-center gap-2">
          <span className="font-pixel text-[11px] uppercase tracking-wider text-foreground">Scene-by-Scene Blocks</span>
          <span className="h-px flex-1 bg-border" />
        </div>
        <div className="space-y-3">
          {scenes.map((s) => (
            <PromptCard key={s.title} title={s.title} prompt={s.prompt} camera={s.camera} />
          ))}
        </div>
      </div>

      <div className="rounded-xl border-2 border-dashed border-primary/40 bg-primary/5 p-3 text-center">
        <span className="font-pixel text-[9px] uppercase tracking-wider text-primary">style tag</span>
        <p className="mt-1 font-mono text-xs text-foreground/80">{styleTag}</p>
      </div>
    </div>
  );
};

export default PromptPanel;
