import { ChevronRight, Loader2 } from "lucide-react";
import director from "@/assets/char-director.png";
import visual from "@/assets/char-visual.png";
import prompt from "@/assets/char-prompt.png";
import seedance from "@/assets/char-seedance.png";
import { RunRow } from "@/lib/api";

export type StepKey = "director" | "visual" | "prompt" | "seedance";

export const STEPS: { key: StepKey; label: string; subtitle: string; img: string; tint: string }[] = [
  { key: "director", label: "Director", subtitle: "Story → Structure", img: director, tint: "from-primary-glow to-primary/30" },
  { key: "visual", label: "Visual", subtitle: "Character / Scene / Style", img: visual, tint: "from-secondary to-secondary/40" },
  { key: "prompt", label: "Prompt", subtitle: "Prompt Assembly", img: prompt, tint: "from-accent to-accent/40" },
  { key: "seedance", label: "Seedance", subtitle: "Video Output", img: seedance, tint: "from-peach to-primary-glow" },
];

function stepState(key: StepKey, run: RunRow | null): "done" | "running" | "pending" {
  if (!run) return "pending";
  const s = run.status;
  if (key === "director") {
    if (run.layer1_output) return "done";
    if (s === "draft" || s === "layer1_running") return "running";
  }
  if (key === "visual") {
    if (run.makeup_output) return "done";
    if (s === "makeup_running") return "running";
    if (run.layer1_output && !run.makeup_output && s !== "failed") return "running";
  }
  if (key === "prompt") {
    // Require makeup before showing Prompt as done (matches pipeline order)
    if (!run.makeup_output) return "pending";
    if (run.layer2_output) return "done";
    if (s === "layer2_running") return "running";
  }
  if (key === "seedance") {
    if (run.layer3_output) return "done";
    if (s === "layer3_running") return "running";
    if (!run.layer2_output || !run.makeup_output) return "pending";
  }
  return "pending";
}

interface Props {
  active: StepKey;
  onSelect: (key: StepKey) => void;
  run?: RunRow | null;
}

const WorkflowStrip = ({ active, onSelect, run = null }: Props) => {
  const activeIdx = STEPS.findIndex((s) => s.key === active);
  return (
    <div className="pixel-card relative p-4 md:p-6">
      <div className="mb-4 flex items-center gap-2 px-1">
        <span className="font-pixel text-[9px] uppercase tracking-wider text-muted-foreground">Pipeline</span>
        <div className="flex flex-1 items-center gap-1">
          {STEPS.map((_, i) => (
            <div
              key={i}
              className={`h-1.5 flex-1 rounded-full transition-all ${i <= activeIdx ? "bg-primary" : "bg-muted"}`}
            />
          ))}
        </div>
        <span className="font-pixel text-[9px] text-primary">
          {activeIdx + 1}/{STEPS.length}
        </span>
      </div>

      <div className="flex items-stretch justify-between gap-2 overflow-x-auto md:gap-4">
        {STEPS.map((step, idx) => {
          const isActive = step.key === active;
          const isDone = idx < activeIdx;
          const state = stepState(step.key, run);
          return (
            <div key={step.key} className="flex items-center gap-2 md:gap-3">
              <button
                onClick={() => onSelect(step.key)}
                className={`group relative flex w-28 shrink-0 flex-col items-center gap-2 rounded-2xl border-[3px] p-3 transition-all md:w-36 ${
                  isActive
                    ? "border-primary bg-gradient-to-br " + step.tint + " shadow-[4px_4px_0_0_hsl(var(--primary)/0.5)] -translate-y-1"
                    : "border-border bg-card hover:border-primary/50 hover:-translate-y-0.5"
                }`}
              >
                <span
                  className={`absolute -top-3 left-1/2 -translate-x-1/2 rounded-full border-[3px] px-2 py-0.5 font-pixel text-[8px] ${
                    isActive
                      ? "border-foreground/15 bg-primary text-primary-foreground"
                      : isDone
                      ? "border-foreground/15 bg-secondary text-secondary-foreground"
                      : "border-border bg-card text-muted-foreground"
                  }`}
                >
                  0{idx + 1}
                </span>

                <img
                  src={step.img}
                  alt={step.label}
                  loading="lazy"
                  width={512}
                  height={512}
                  className={`pixelated h-16 w-16 md:h-20 md:w-20 ${
                    isActive ? "animate-bounce-soft" : "group-hover:animate-wiggle"
                  }`}
                />

                <div className="text-center">
                  <div className={`font-pixel text-[10px] uppercase ${isActive ? "text-foreground" : "text-foreground/80"}`}>
                    {step.label}
                  </div>
                  <div className="mt-0.5 text-[10px] leading-tight text-muted-foreground md:text-xs">
                    {step.subtitle}
                  </div>
                </div>

                {/* Live state badges */}
                {state === "running" ? (
                  <span className="absolute -bottom-2 left-1/2 -translate-x-1/2 flex items-center gap-1 rounded-full bg-primary px-2 py-0.5 font-pixel text-[8px] text-primary-foreground shadow-md">
                    <Loader2 className="h-2.5 w-2.5 animate-spin" /> RUNNING
                  </span>
                ) : state === "done" && !isActive ? (
                  <span className="absolute -bottom-2 left-1/2 -translate-x-1/2 rounded-full bg-secondary px-2 py-0.5 font-pixel text-[8px] text-secondary-foreground shadow-md">
                    ✓ DONE
                  </span>
                ) : isActive ? (
                  <span className="absolute -bottom-2 left-1/2 -translate-x-1/2 rounded-full bg-primary px-2 py-0.5 font-pixel text-[8px] text-primary-foreground shadow-md">
                    ● ACTIVE
                  </span>
                ) : null}
              </button>

              {idx < STEPS.length - 1 && (
                <ChevronRight
                  className={`h-5 w-5 shrink-0 ${idx < activeIdx ? "text-primary" : "text-muted-foreground/40"}`}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default WorkflowStrip;
