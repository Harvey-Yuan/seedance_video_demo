import { Palette, Image as ImageIcon, Loader2 } from "lucide-react";
import { useRun } from "@/context/RunContext";

const Section = ({ title, icon: Icon, children }: { title: string; icon: React.ElementType; children: React.ReactNode }) => (
  <div className="pixel-card p-5">
    <div className="mb-3 flex items-center gap-2">
      <div className="grid h-7 w-7 place-items-center rounded-lg bg-secondary text-secondary-foreground">
        <Icon className="h-4 w-4" />
      </div>
      <h3 className="font-pixel text-[11px] uppercase tracking-wider text-foreground">{title}</h3>
    </div>
    {children}
  </div>
);

const PanelSkeleton = ({ label, hint }: { label: string; hint?: string }) => (
  <div className="flex items-start gap-3 rounded-2xl border-2 border-dashed border-secondary/50 bg-secondary/10 p-5">
    <Loader2 className="mt-0.5 h-5 w-5 shrink-0 animate-spin text-secondary-foreground" />
    <div>
      <p className="font-pixel text-[11px] text-foreground">{label}</p>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </div>
  </div>
);

const VisualPanel = () => {
  const { runId, run, status } = useRun();

  const makeup = run?.makeup_output ?? null;
  const failed = status === "failed";
  const waitingMakeup =
    !!runId &&
    !makeup &&
    !failed &&
    (status === "draft" || status === "layer1_running" || status === "layer1_done" || status === "makeup_running");

  if (failed) {
    return (
      <div className="rounded-2xl border-2 border-destructive/40 bg-destructive/10 p-5 font-pixel text-[11px] text-destructive">
        <p className="font-semibold">Makeup step failed</p>
        <p className="mt-2 whitespace-pre-wrap text-xs opacity-90">{run?.error_message ?? "Run failed"}</p>
      </div>
    );
  }

  if (waitingMakeup) {
    return (
      <div className="space-y-4 animate-fade-in">
        <PanelSkeleton label="Generating reference stills…" hint="Character + scene images (ModelArk). This may take 30–90s." />
        <div className="grid gap-3 md:grid-cols-2">
          {[1, 2].map((i) => (
            <div key={i} className="h-48 animate-pulse rounded-xl bg-muted/50" />
          ))}
        </div>
      </div>
    );
  }

  const imageUrls = (makeup?.character_image_urls ?? []).filter(Boolean);
  const sceneUrls = (makeup?.scene_image_urls ?? []).filter(Boolean);
  const sceneIds = (makeup?.meta?.scene_shot_ids as string[] | undefined) ?? [];

  if (makeup && imageUrls.length === 0) {
    return (
      <div className="rounded-2xl border-2 border-amber-500/50 bg-amber-500/10 p-5 font-pixel text-[11px] text-foreground">
        <p className="font-semibold text-amber-800 dark:text-amber-200">No character_image_urls</p>
        <p className="mt-2 text-xs text-muted-foreground">Makeup returned empty URLs; Seedance will be rejected. Check backend logs.</p>
      </div>
    );
  }

  if (!makeup) {
    return (
      <div className="rounded-2xl border-2 border-border bg-muted/30 p-5 font-pixel text-[10px] text-muted-foreground">
        No makeup data yet. Run the pipeline from the home screen.
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-fade-in">
      <Section title="Character Art" icon={Palette}>
        <div className="flex flex-wrap gap-3">
          {imageUrls.map((url, i) => (
            <a key={i} href={url} target="_blank" rel="noreferrer">
              <img
                src={url}
                alt={`Character ${i + 1}`}
                className="h-48 rounded-xl border-[3px] border-border object-cover shadow-md transition-transform hover:scale-105"
              />
            </a>
          ))}
        </div>
      </Section>

      <Section title="Scene Art" icon={ImageIcon}>
        {sceneUrls.length > 0 ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {sceneUrls.map((url, i) => (
              <div key={i} className="overflow-hidden rounded-xl border-[3px] border-border bg-card">
                <a href={url} target="_blank" rel="noreferrer" className="block">
                  <img src={url} alt={`Scene ${i + 1}`} className="h-40 w-full object-cover" />
                </a>
                <div className="p-2">
                  <div className="font-pixel text-[9px] text-muted-foreground">
                    {sceneIds[i] ?? `Scene ${i + 1}`}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No scene stills in this run (backend will add scene_image_urls when generation succeeds).</p>
        )}
      </Section>
    </div>
  );
};

export default VisualPanel;
