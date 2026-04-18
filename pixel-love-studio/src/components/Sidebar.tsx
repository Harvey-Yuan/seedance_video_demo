import { ArrowLeft, Clapperboard, Palette, Sparkles, Film, FolderHeart, Download, ScrollText } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { PixelHeart } from "./PixelDecor";

interface Props {
  storySnippet: string;
}

const navItems = [
  { icon: ScrollText, label: "Story Input", route: "/" },
  { icon: Sparkles, label: "Workflow", active: true },
  { icon: FolderHeart, label: "Assets" },
  { icon: Download, label: "Export" },
];

const Sidebar = ({ storySnippet }: Props) => {
  const navigate = useNavigate();
  return (
    <aside className="hidden lg:flex w-64 shrink-0 flex-col gap-5 border-r-[3px] border-border bg-sidebar p-5">
      {/* Logo */}
      <div className="flex items-center gap-2">
        <div className="grid h-9 w-9 place-items-center rounded-lg bg-primary text-primary-foreground pixel-border">
          <PixelHeart className="h-4 w-4 text-primary-foreground" />
        </div>
        <div>
          <div className="font-pixel text-[10px] leading-tight text-sidebar-foreground">DAILY</div>
          <div className="font-pixel text-[10px] leading-tight text-primary">REEL</div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex flex-col gap-1.5">
        {navItems.map(({ icon: Icon, label, active, route }) => (
          <button
            key={label}
            onClick={() => route && navigate(route)}
            className={`group flex items-center gap-3 rounded-xl border-[3px] px-3 py-2.5 text-left text-sm font-semibold transition-all ${
              active
                ? "border-foreground/15 bg-primary text-primary-foreground shadow-[3px_3px_0_0_hsl(var(--primary)/0.4)]"
                : "border-transparent text-sidebar-foreground hover:bg-sidebar-accent hover:border-sidebar-border"
            }`}
          >
            <Icon className="h-4 w-4" />
            <span>{label}</span>
          </button>
        ))}
      </nav>

      {/* Current story */}
      <div className="pixel-card p-3 text-xs">
        <div className="mb-2 flex items-center gap-1.5">
          <Clapperboard className="h-3.5 w-3.5 text-primary" />
          <span className="font-pixel text-[9px] uppercase tracking-wider text-foreground/80">
            Current Story
          </span>
        </div>
        <p className="line-clamp-5 whitespace-pre-line text-muted-foreground leading-relaxed">
          {storySnippet}
        </p>
      </div>

      <div className="flex-1" />

      {/* Decorative */}
      <div className="rounded-xl bg-gradient-to-br from-primary-glow/40 to-secondary/40 p-3 text-center">
        <Palette className="mx-auto h-5 w-5 text-primary" />
        <p className="mt-1 font-pixel text-[8px] uppercase tracking-wider text-foreground/70">
          v1.0 · pixel build
        </p>
      </div>

      <Button
        variant="outline"
        className="gap-2 rounded-xl border-[3px] border-border bg-card font-semibold"
        onClick={() => navigate("/")}
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Input
      </Button>
    </aside>
  );
};

export default Sidebar;
