import { useState } from "react";
import Sidebar from "@/components/Sidebar";
import WorkflowStrip, { StepKey, STEPS } from "@/components/WorkflowStrip";
import DirectorPanel from "@/components/panels/DirectorPanel";
import VisualPanel from "@/components/panels/VisualPanel";
import PromptPanel from "@/components/panels/PromptPanel";
import SeedancePanel from "@/components/panels/SeedancePanel";
import { useRun } from "@/context/RunContext";
import { ArrowLeft, Loader2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";

const STATUS_LABELS: Record<string, string> = {
  draft: "Queued",
  layer1_running: "Scripting…",
  layer1_done: "Script done",
  makeup_running: "Makeup imaging…",
  makeup_done: "Makeup done",
  layer2_running: "Directing…",
  layer2_done: "Direction done",
  layer3_running: "Rendering video…",
  done: "Complete ♡",
  failed: "Failed",
};

const Workflow = () => {
  const [active, setActive] = useState<StepKey>("director");
  const navigate = useNavigate();
  const { run, status, runId, error } = useRun();

  const story = sessionStorage.getItem("dss-story") ?? "";
  const activeStep = STEPS.find((s) => s.key === active)!;
  const statusLabel = status ? (STATUS_LABELS[status] ?? status) : null;
  const isRunning = status && status !== "done" && status !== "failed";

  const renderPanel = () => {
    switch (active) {
      case "director": return <DirectorPanel />;
      case "visual": return <VisualPanel />;
      case "prompt": return <PromptPanel />;
      case "seedance": return <SeedancePanel />;
    }
  };

  return (
    <div className="flex min-h-screen w-full bg-background pixel-grid-bg">
      <Sidebar storySnippet={story} />

      <main className="flex-1 overflow-x-hidden">
        <div className="sticky top-0 z-20 flex items-center justify-between gap-3 border-b-[3px] border-border bg-background/85 px-4 py-3 backdrop-blur md:px-8">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate("/")}
              className="lg:hidden gap-1.5"
            >
              <ArrowLeft className="h-4 w-4" /> Back
            </Button>
            <div>
              <div className="font-pixel text-[10px] uppercase tracking-wider text-muted-foreground">
                Studio
              </div>
              <h1 className="font-pixel text-sm text-foreground md:text-base">
                ♡ {activeStep.label} <span className="text-primary">— {activeStep.subtitle}</span>
              </h1>
            </div>
          </div>

          {runId && statusLabel ? (
            <span className="hidden md:flex items-center gap-1.5 rounded-full border-2 border-border bg-card px-3 py-1 font-pixel text-[9px] text-foreground/70">
              {isRunning && <Loader2 className="h-3 w-3 animate-spin text-primary" />}
              {statusLabel}
            </span>
          ) : !runId ? (
            <span className="hidden md:flex items-center gap-1.5 rounded-full border-2 border-border bg-card px-3 py-1 font-pixel text-[9px] text-foreground/70">
              mocked outputs
            </span>
          ) : null}
        </div>

        {error && (
          <div className="mx-auto max-w-6xl px-4 pt-4 md:px-8">
            <div className="rounded-xl border-2 border-destructive/40 bg-destructive/10 p-3 font-pixel text-[10px] text-destructive">
              {error}
            </div>
          </div>
        )}

        <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-8">
          <WorkflowStrip active={active} onSelect={setActive} run={run} />

          <section className="relative">
            <div className="absolute -top-3 left-6 z-10 rounded-full border-[3px] border-foreground/15 bg-card px-3 py-1 font-pixel text-[9px] uppercase tracking-wider shadow-sm">
              <span className="text-primary">▸</span> {activeStep.label} Output
            </div>
            <div key={active} className="rounded-3xl border-[3px] border-border bg-gradient-to-br from-card to-muted/30 p-4 pt-7 md:p-6 md:pt-8 shadow-[6px_6px_0_0_hsl(var(--secondary))]">
              {renderPanel()}
            </div>
          </section>
        </div>
      </main>
    </div>
  );
};

export default Workflow;
