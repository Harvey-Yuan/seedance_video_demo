import { Palette, Image as ImageIcon, Tag, Loader2 } from "lucide-react";
import { visualOutput } from "@/lib/mockData";
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
  const layer1 = run?.layer1_output ?? null;
  const isLoading = !!runId && !makeup && (
    status === "layer1_done" || status === "makeup_running" ||
    status === "draft" || status === "layer1_running"
  );

  if (isLoading) {
    return (
      <div className="space-y-4 animate-fade-in">
        <PanelSkeleton
          label="Generating character images…"
          hint="ModelArk is rendering makeup reference images. This may take 30–60s."
        />
        <div className="grid gap-3 md:grid-cols-2">
          {[1, 2].map((i) => (
            <div key={i} className="h-48 animate-pulse rounded-xl bg-muted/50" />
          ))}
        </div>
      </div>
    );
  }

  const imageUrls = makeup?.character_image_urls ?? [];
  const makeupPrompts = makeup?.makeup_prompts ?? [];
  const mock = visualOutput;

  const sceneItems = layer1?.storyboard
    ? layer1.storyboard.slice(0, 3).map((s, i) => ({
        name: `Scene ${i + 1}`,
        desc: s.visual,
      }))
    : mock.scenes;

  const styleKeywords = makeupPrompts.length > 0
    ? makeupPrompts.flatMap((p) => p.split(",").map((k) => k.trim()).filter(Boolean)).slice(0, 8)
    : mock.styleKeywords;

  return (
    <div className="space-y-5 animate-fade-in">
      <Section title="Character Art" icon={Palette}>
        {imageUrls.length > 0 ? (
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
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {mock.characters.map((c, i) => (
              <div key={c.name} className="overflow-hidden rounded-xl border-[3px] border-border bg-card">
                <div className={`relative h-28 flex items-center justify-center pixel-grid-bg ${i === 0 ? "bg-gradient-to-br from-primary-glow to-secondary" : "bg-gradient-to-br from-accent to-secondary"}`}>
                  <ImageIcon className="h-8 w-8 text-foreground/30" />
                  <span className="absolute bottom-1 right-2 rounded bg-card/80 px-1.5 py-0.5 font-pixel text-[8px] text-foreground/70">mock</span>
                </div>
                <div className="p-3">
                  <div className="font-pixel text-[10px] text-foreground">{c.name}</div>
                  <p className="mt-1 text-xs text-muted-foreground leading-relaxed">{c.desc}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section title="Scene Art" icon={ImageIcon}>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {sceneItems.map((s, i) => (
            <div key={s.name} className="overflow-hidden rounded-xl border-[3px] border-border bg-card">
              <div className={`relative h-28 flex items-center justify-center pixel-grid-bg ${
                ["bg-gradient-to-br from-primary/30 to-secondary", "bg-gradient-to-br from-peach to-primary-glow", "bg-gradient-to-br from-accent to-secondary"][i % 3]
              }`}>
                <ImageIcon className="h-8 w-8 text-foreground/30" />
              </div>
              <div className="p-3">
                <div className="font-pixel text-[10px] text-foreground">{s.name}</div>
                <p className="mt-1 text-xs text-muted-foreground leading-relaxed">{s.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </Section>

      <div className="grid gap-5 md:grid-cols-2">
        <Section title="Style Direction" icon={Palette}>
          <div className="flex flex-wrap gap-2">
            {styleKeywords.map((k) => (
              <span
                key={k}
                className="rounded-full border-2 border-border bg-gradient-to-br from-primary-glow/40 to-secondary/40 px-3 py-1 text-xs font-semibold text-foreground/80"
              >
                ♡ {k}
              </span>
            ))}
          </div>
        </Section>

        <Section title="Prompt Ingredients" icon={Tag}>
          <ul className="space-y-2">
            {(makeupPrompts.length > 0 ? makeupPrompts : mock.promptIngredients).map((p, i) => (
              <li key={i} className="flex items-start gap-2 rounded-lg bg-muted/40 px-3 py-2 text-sm">
                <span className="mt-0.5 font-pixel text-[9px] text-primary">{String(i + 1).padStart(2, "0")}</span>
                <span className="text-foreground/90">{p}</span>
              </li>
            ))}
          </ul>
        </Section>
      </div>
    </div>
  );
};

export default VisualPanel;
