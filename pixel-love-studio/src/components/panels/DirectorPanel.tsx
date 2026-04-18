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
        <PanelSkeleton label="Writing script…" hint="LLM is generating storyboard, script, characters, and dialogue." />
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-14 animate-pulse rounded-xl bg-muted/50" />
        ))}
      </div>
    );
  }

  if (runId && status === "failed" && !live) {
    return (
      <div className="rounded-2xl border-2 border-destructive/40 bg-destructive/10 p-5 font-pixel text-[11px] text-destructive">
        <p className="font-semibold">Writer failed</p>
        <p className="mt-2 whitespace-pre-wrap text-xs opacity-90">{run?.error_message ?? "Run failed"}</p>
      </div>
    );
  }

  const storyboard = live?.storyboard ?? null;
  const script = live?.script ?? null;
  const characters = live?.characters ?? null;
  const dialogue = live?.dialogue ?? null;
  const mock = directorOutput;

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
  const useApi = !!live;

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="pixel-card-lavender bg-gradient-to-br from-secondary/40 to-primary-glow/30 p-5">
        <SectionTitle icon={Clapperboard}>Story Script</SectionTitle>
        <p className="text-sm leading-relaxed text-foreground/90 md:text-base whitespace-pre-wrap">{useApi ? summary : summary.length > 400 ? `${summary.slice(0, 400)}…` : summary}</p>
      </div>

      <Tabs defaultValue="shots" className="w-full">
        <TabsList className="h-auto flex-wrap gap-1 rounded-xl border-[3px] border-border bg-muted/40 p-1.5">
          <TabsTrigger value="shots" className="rounded-lg font-pixel text-[10px] data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
            Shots
          </TabsTrigger>
          <TabsTrigger value="dialogue" className="rounded-lg font-pixel text-[10px] data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
            Dialogue Draft
          </TabsTrigger>
          <TabsTrigger value="roles" className="rounded-lg font-pixel text-[10px] data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
            Character / Role Script
          </TabsTrigger>
        </TabsList>

        <TabsContent value="shots" className="mt-4">
          <div className="pixel-card p-5">
            <SectionTitle icon={FileText}>Shots</SectionTitle>
            <div className="grid gap-3 sm:grid-cols-2">
              {shots.map((s) => (
                <div key={s.id} className="rounded-xl border-2 border-border bg-gradient-to-br from-card to-muted/40 p-3">
                  <div className="mb-1 inline-block rounded-md bg-secondary px-2 py-0.5 font-pixel text-[9px] text-secondary-foreground">{s.id}</div>
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
                  <div className="mt-1 text-sm italic text-foreground/90">&ldquo;{d.line}&rdquo;</div>
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
