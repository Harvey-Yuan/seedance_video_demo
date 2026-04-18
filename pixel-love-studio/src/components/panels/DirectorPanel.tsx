import { Clapperboard, FileText, Pencil, Users, Loader2 } from "lucide-react";
import { directorOutput } from "@/lib/mockData";
import { useRun } from "@/context/RunContext";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const SectionTitle = ({ icon: Icon, children }: { icon: React.ElementType; children: React.ReactNode }) => (
  <div className="mb-3 flex items-center gap-2">
    <div className="grid h-7 w-7 place-items-center rounded-lg bg-primary/15 text-primary">
      <Icon className="h-4 w-4" />
    </div>
    <h3 className="font-pixel text-[11px] uppercase tracking-wider text-foreground">{children}</h3>
  </div>
);

const PanelSkeleton = ({ label, hint }: { label: string; hint?: string }) => (
  <div className="flex items-start gap-3 rounded-2xl border-2 border-dashed border-primary/30 bg-primary/5 p-5">
    <Loader2 className="mt-0.5 h-5 w-5 shrink-0 animate-spin text-primary" />
    <div>
      <p className="font-pixel text-[11px] text-foreground">{label}</p>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </div>
  </div>
);

const DirectorPanel = () => {
  const { runId, run, status } = useRun();

  const live = run?.layer1_output ?? null;
  const isLoading = !!runId && !live && (status === "draft" || status === "layer1_running" || status === "layer1_done" || status === "makeup_running");

  if (isLoading) {
    return (
      <div className="space-y-4 animate-fade-in">
        <PanelSkeleton
          label="Scripting…"
          hint={status === "draft" ? "Task queued — LLM is generating storyboard and dialogue…" : "Generating storyboard, script, characters and dialogue (≈30s)…"}
        />
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-14 animate-pulse rounded-xl bg-muted/50" />
        ))}
      </div>
    );
  }

  // Use live data if available, else fall back to mock for demo mode
  const storyboard = live?.storyboard ?? null;
  const script = live?.script ?? null;
  const characters = live?.characters ?? null;
  const dialogue = live?.dialogue ?? null;
  const mock = directorOutput;

  const beats = storyboard
    ? storyboard.map((s, i) => ({ label: `Shot ${i + 1}`, text: `${s.visual}${s.camera_notes ? ` — ${s.camera_notes}` : ""}` }))
    : mock.beats;

  const shots = storyboard
    ? storyboard.map((s) => ({ id: s.shot_id, desc: `${s.visual} (≈${s.duration_hint_sec}s)` }))
    : mock.shots;

  const dialogueItems = dialogue
    ? dialogue.map((d) => ({ who: d.speaker, line: d.line }))
    : mock.dialogue;

  const roles = characters
    ? characters.map((c) => ({ name: c.name, desc: c.description }))
    : mock.roles;

  const summary = script ?? mock.summary;

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="pixel-card-lavender bg-gradient-to-br from-secondary/40 to-primary-glow/30 p-5">
        <SectionTitle icon={Clapperboard}>Story Script</SectionTitle>
        <p className="text-sm leading-relaxed text-foreground/90 md:text-base whitespace-pre-wrap">
          {summary.length > 400 ? summary.slice(0, 400) + "…" : summary}
        </p>
      </div>

      <Tabs defaultValue="beats" className="w-full">
        <TabsList className="h-auto flex-wrap gap-1 rounded-xl border-[3px] border-border bg-muted/40 p-1.5">
          <TabsTrigger value="beats" className="rounded-lg font-pixel text-[10px] data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">Beats</TabsTrigger>
          <TabsTrigger value="shots" className="rounded-lg font-pixel text-[10px] data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">Shots</TabsTrigger>
          <TabsTrigger value="dialogue" className="rounded-lg font-pixel text-[10px] data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">Dialogue</TabsTrigger>
          <TabsTrigger value="roles" className="rounded-lg font-pixel text-[10px] data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">Roles</TabsTrigger>
        </TabsList>

        <TabsContent value="beats" className="mt-4">
          <div className="pixel-card p-5">
            <SectionTitle icon={Clapperboard}>Story Beats</SectionTitle>
            <ol className="space-y-3">
              {beats.map((b, i) => (
                <li key={i} className="flex gap-3 rounded-xl border-2 border-border bg-muted/30 p-3">
                  <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-primary font-pixel text-[10px] text-primary-foreground">
                    {i + 1}
                  </span>
                  <div>
                    <div className="font-pixel text-[10px] uppercase tracking-wider text-primary">{b.label}</div>
                    <div className="text-sm text-foreground/90">{b.text}</div>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </TabsContent>

        <TabsContent value="shots" className="mt-4">
          <div className="pixel-card p-5">
            <SectionTitle icon={FileText}>Storyboard / Shot List</SectionTitle>
            <div className="grid gap-3 sm:grid-cols-2">
              {shots.map((s) => (
                <div key={s.id} className="rounded-xl border-2 border-border bg-gradient-to-br from-card to-muted/40 p-3">
                  <div className="mb-1 inline-block rounded-md bg-secondary px-2 py-0.5 font-pixel text-[9px] text-secondary-foreground">
                    {s.id}
                  </div>
                  <p className="text-sm text-foreground/90">{s.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </TabsContent>

        <TabsContent value="dialogue" className="mt-4">
          <div className="pixel-card p-5">
            <SectionTitle icon={Pencil}>Dialogue Draft</SectionTitle>
            <div className="space-y-3">
              {dialogueItems.map((d, i) => (
                <div key={i} className="rounded-xl border-l-4 border-primary bg-muted/30 p-3">
                  <div className="font-pixel text-[9px] uppercase tracking-wider text-primary">{d.who}</div>
                  <div className="mt-1 text-sm italic text-foreground/90">"{d.line}"</div>
                </div>
              ))}
            </div>
          </div>
        </TabsContent>

        <TabsContent value="roles" className="mt-4">
          <div className="pixel-card p-5">
            <SectionTitle icon={Users}>Character / Role Script</SectionTitle>
            <div className="grid gap-3 md:grid-cols-2">
              {roles.map((r) => (
                <div key={r.name} className="rounded-xl border-[3px] border-border bg-gradient-to-br from-primary-glow/30 to-secondary/30 p-4">
                  <div className="font-pixel text-[10px] text-foreground">{r.name}</div>
                  <p className="mt-2 text-sm text-foreground/90">{r.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default DirectorPanel;
