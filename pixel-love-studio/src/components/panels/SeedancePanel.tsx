import { Play, Download, Film, Clock, Sparkles, Loader2, AlertCircle } from "lucide-react";
import { seedanceOutput } from "@/lib/mockData";
import { useRun } from "@/context/RunContext";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

const PanelSkeleton = ({ label, hint }: { label: string; hint?: string }) => (
  <div className="flex items-start gap-3 rounded-2xl border-2 border-dashed border-primary/30 bg-primary/5 p-5">
    <Loader2 className="mt-0.5 h-5 w-5 shrink-0 animate-spin text-primary" />
    <div>
      <p className="font-pixel text-[11px] text-foreground">{label}</p>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </div>
  </div>
);

const SeedancePanel = () => {
  const { runId, run, status } = useRun();

  const layer3 = run?.layer3_output ?? null;
  const layer2 = run?.layer2_output ?? null;
  const isLoading = !!runId && !layer3 && (
    status === "draft" || status === "layer1_running" || status === "layer1_done" ||
    status === "makeup_running" || status === "makeup_done" ||
    status === "layer2_running" || status === "layer2_done" ||
    status === "layer3_running"
  );

  const mock = seedanceOutput;

  // Build render queue from real data or mock
  const queueItems = layer2?.seedance_prompts
    ? layer2.seedance_prompts.map((p, i) => ({
        id: i + 1,
        title: p.segment_id,
        duration: p.duration_sec ? `0:${String(p.duration_sec).padStart(2, "0")}` : "—",
        done: !!(layer3?.meta?.segment_urls?.[i] || layer3),
      }))
    : mock.scenes.map((s) => ({ ...s, done: true }));

  const videoUrl = layer3?.video_url;
  const modelName = layer3?.model ?? mock.model;
  const durationSec = layer3?.duration_sec;
  const uploadError = layer3?.meta?.upload_error;

  if (isLoading) {
    return (
      <div className="space-y-5 animate-fade-in">
        <PanelSkeleton
          label={status === "layer3_running" ? "Rendering segments with Seedance…" : "Waiting for pipeline to reach render stage…"}
          hint={status === "layer3_running"
            ? "Each segment is being rendered, then merged with ffmpeg. This typically takes several minutes."
            : "Scripting and makeup must complete before rendering begins."}
        />

        {/* Animated pending queue */}
        {layer2?.seedance_prompts && (
          <div className="pixel-card p-4">
            <div className="mb-3 flex items-center gap-2">
              <Clock className="h-4 w-4 text-primary" />
              <span className="font-pixel text-[10px] uppercase text-foreground">Render Queue</span>
            </div>
            <div className="space-y-2">
              {layer2.seedance_prompts.map((p, i) => (
                <div key={p.segment_id} className="flex items-center gap-3 rounded-lg border-2 border-border bg-muted/40 p-2.5">
                  <div className="relative h-10 w-10 shrink-0 overflow-hidden rounded-md bg-gradient-to-br from-primary-glow to-secondary pixel-grid-bg">
                    <span className="absolute inset-0 grid place-items-center font-pixel text-[10px] text-foreground/70">{i + 1}</span>
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-semibold text-foreground">{p.segment_id}</div>
                    <div className="text-[10px] text-muted-foreground truncate">{p.prompt.slice(0, 60)}…</div>
                  </div>
                  {i === 0 && status === "layer3_running" ? (
                    <span className="flex items-center gap-1 rounded-full bg-primary/15 px-2 py-0.5 font-pixel text-[8px] text-primary">
                      <Loader2 className="h-2.5 w-2.5 animate-spin" /> RENDERING
                    </span>
                  ) : (
                    <span className="rounded-full bg-muted px-2 py-0.5 font-pixel text-[8px] text-muted-foreground">QUEUED</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-5 animate-fade-in">
      {/* Status row */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border-[3px] border-border bg-card p-4">
        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-primary to-primary-glow text-primary-foreground">
            <Film className="h-5 w-5" />
          </div>
          <div>
            <div className="font-pixel text-[10px] uppercase text-muted-foreground">Model</div>
            <div className="text-sm font-semibold text-foreground">{modelName}</div>
          </div>
        </div>
        <span className="flex items-center gap-1.5 rounded-full border-2 border-foreground/15 bg-gradient-to-r from-primary to-primary-glow px-3 py-1 font-pixel text-[10px] text-primary-foreground shadow-md">
          <span className="h-2 w-2 animate-pulse rounded-full bg-card" />
          {layer3 ? "COMPLETED" : mock.status.toUpperCase()}
        </span>
      </div>

      {uploadError && (
        <div className="flex items-center gap-2 rounded-xl border-2 border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>Storage upload failed: {uploadError}</span>
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-[2fr_1fr]">
        {/* Video player */}
        <div className="pixel-card overflow-hidden p-0">
          <div className="border-b-2 border-border bg-muted/40 px-4 py-2 flex items-center justify-between">
            <span className="font-pixel text-[10px] uppercase text-foreground">Final Video Preview</span>
            {durationSec && (
              <span className="font-pixel text-[9px] text-muted-foreground">{durationSec}s</span>
            )}
          </div>

          {videoUrl ? (
            <div className="p-4">
              <video
                src={videoUrl}
                controls
                playsInline
                className="w-full rounded-xl border-[3px] border-border bg-black"
              />
            </div>
          ) : (
            <div className="flex items-center justify-center bg-gradient-to-br from-secondary/30 to-primary-glow/30 p-6">
              <div className="relative w-full max-w-[260px] aspect-[9/16] overflow-hidden rounded-2xl border-[4px] border-foreground/15 bg-gradient-to-br from-foreground/90 via-secondary-foreground/40 to-primary/60 pixel-grid-bg shadow-[6px_6px_0_0_hsl(var(--primary)/0.4)]">
                <div className="absolute inset-0 bg-gradient-to-t from-foreground/60 via-transparent to-transparent" />
                <div className="absolute top-3 left-3 rounded bg-card/20 px-2 py-0.5 font-pixel text-[8px] text-card backdrop-blur">♡ DRAMA</div>
                <div className="absolute bottom-3 left-3 right-3 text-card text-xs leading-snug">
                  <p className="italic opacity-90">"i was wrong. i miss you."</p>
                </div>
                <button
                  onClick={() => toast.success("Playing preview ♡")}
                  className="absolute inset-0 grid place-items-center group"
                >
                  <span className="grid h-14 w-14 place-items-center rounded-full border-[3px] border-card bg-primary text-primary-foreground shadow-lg transition-transform group-hover:scale-110">
                    <Play className="h-6 w-6 fill-current ml-0.5" />
                  </span>
                </button>
                <div className="absolute bottom-0 left-0 right-0 h-1 bg-card/30">
                  <div className="h-full w-1/3 bg-primary" />
                </div>
              </div>
            </div>
          )}

          <div className="flex flex-wrap gap-2 border-t-2 border-border bg-muted/30 p-3">
            {videoUrl ? (
              <Button
                asChild
                className="gap-1.5 rounded-xl border-[3px] border-foreground/15 bg-primary text-primary-foreground shadow-[3px_3px_0_0_hsl(var(--primary)/0.4)]"
              >
                <a href={videoUrl} download>
                  <Download className="h-4 w-4" /> Download
                </a>
              </Button>
            ) : (
              <Button onClick={() => toast.success("Preview ♡")} className="gap-1.5 rounded-xl border-[3px] border-foreground/15 bg-primary text-primary-foreground shadow-[3px_3px_0_0_hsl(var(--primary)/0.4)]">
                <Play className="h-4 w-4" /> Preview
              </Button>
            )}
          </div>
        </div>

        {/* Side: render queue + summary */}
        <div className="space-y-4">
          <div className="pixel-card p-4">
            <div className="mb-3 flex items-center gap-2">
              <Clock className="h-4 w-4 text-primary" />
              <span className="font-pixel text-[10px] uppercase text-foreground">Render Queue</span>
            </div>
            <div className="space-y-2">
              {queueItems.map((s) => (
                <div key={s.id} className="flex items-center gap-3 rounded-lg border-2 border-border bg-muted/40 p-2.5">
                  <div className="relative h-10 w-10 shrink-0 overflow-hidden rounded-md bg-gradient-to-br from-primary-glow to-secondary pixel-grid-bg">
                    <span className="absolute inset-0 grid place-items-center font-pixel text-[10px] text-foreground/70">{s.id}</span>
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-semibold text-foreground">{s.title}</div>
                    <div className="text-[10px] text-muted-foreground">{s.duration}</div>
                  </div>
                  <span className={`rounded-full px-2 py-0.5 font-pixel text-[8px] ${s.done ? "bg-primary/15 text-primary" : "bg-muted text-muted-foreground"}`}>
                    {s.done ? "DONE" : "PENDING"}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border-[3px] border-border bg-gradient-to-br from-primary-glow/30 to-secondary/30 p-4">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles className="h-4 w-4 text-primary animate-sparkle" />
              <span className="font-pixel text-[10px] uppercase text-foreground">Summary</span>
            </div>
            <dl className="space-y-1.5 text-xs">
              {durationSec ? (
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Duration</dt>
                  <dd className="font-semibold text-foreground">{durationSec}s</dd>
                </div>
              ) : (
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Duration</dt>
                  <dd className="font-semibold text-foreground">{mock.duration}</dd>
                </div>
              )}
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Scenes</dt>
                <dd className="font-semibold text-foreground">{queueItems.length}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Model</dt>
                <dd className="font-semibold text-foreground truncate max-w-[120px]">{modelName}</dd>
              </div>
            </dl>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SeedancePanel;
