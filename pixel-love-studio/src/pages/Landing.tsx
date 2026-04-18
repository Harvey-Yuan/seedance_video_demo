import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Heart, Loader2, Sparkles, Wand2, BookHeart } from "lucide-react";
import { Button } from "@/components/ui/button";
import { FloatingDecor, PixelHeart, PixelStar } from "@/components/PixelDecor";
import { SAMPLE_STORY } from "@/lib/mockData";
import { useRun } from "@/context/RunContext";
import mascot from "@/assets/mascot-heart.png";

const PLACEHOLDER = `e.g. 1:23 AM. He texts out of nowhere: "you up?"
We hadn't spoken in three months…
I thought I was over it, but my fingers just hover over the keyboard — type, delete, type again.
The rain outside is loud, like everything I never said back then.`;

const Landing = () => {
  const [story, setStory] = useState("");
  const navigate = useNavigate();
  const { submit, isSubmitting, error } = useRun();

  const handleGenerate = async () => {
    const text = story.trim() || SAMPLE_STORY;
    sessionStorage.setItem("dss-story", text);
    try {
      await submit(text);
      navigate("/workflow");
    } catch {
      // error displayed below
    }
  };

  const handleSample = () => setStory(SAMPLE_STORY);

  return (
    <div className="relative min-h-screen w-full overflow-hidden gradient-dream pixel-grid-bg">
      <FloatingDecor />

      <header className="relative z-10 flex items-center justify-between px-6 py-5 md:px-12">
        <div className="flex items-center gap-2">
          <div className="grid h-9 w-9 place-items-center rounded-lg bg-primary text-primary-foreground pixel-border">
            <Heart className="h-5 w-5 fill-current" />
          </div>
          <span className="font-pixel text-xs text-foreground">DSS</span>
        </div>
        <span className="font-pixel text-[10px] text-muted-foreground hidden sm:block">
          ♡ HACKATHON DEMO ♡
        </span>
      </header>

      <main className="relative z-10 mx-auto flex min-h-[calc(100vh-80px)] max-w-3xl flex-col items-center justify-center px-6 pb-16">
        <img
          src={mascot}
          alt="Pixel heart mascot"
          className="pixelated mb-4 h-24 w-24 animate-bounce-soft"
          width={512}
          height={512}
        />

        <div className="mb-3 flex items-center gap-2">
          <PixelStar className="h-5 w-5 animate-sparkle" />
          <span className="font-pixel text-[10px] uppercase tracking-widest text-primary">
            Press Start to Romance
          </span>
          <PixelStar className="h-5 w-5 animate-sparkle" style={{ animationDelay: "0.3s" }} />
        </div>

        <h1 className="font-pixel text-center text-2xl leading-tight text-foreground text-shadow-pixel sm:text-3xl md:text-4xl">
          Dating Story
          <br />
          <span className="text-primary">Studio</span>
        </h1>

        <p className="mt-5 max-w-xl text-center text-base text-muted-foreground md:text-lg">
          Turn real dating stories into AI-generated short drama videos —
          <span className="text-foreground font-semibold"> directed by adorable pixel souls.</span>
        </p>

        <div className="relative mt-10 w-full">
          <PixelHeart className="absolute -left-3 -top-3 h-6 w-6 animate-float z-10" />
          <PixelStar className="absolute -right-3 -top-3 h-6 w-6 animate-sparkle z-10" />

          <div className="pixel-card p-5 md:p-7">
            <div className="mb-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <BookHeart className="h-4 w-4 text-primary" />
                <span className="font-pixel text-[10px] uppercase tracking-wider text-foreground/80">
                  Your Story
                </span>
              </div>
              <button
                onClick={handleSample}
                className="font-pixel text-[9px] uppercase tracking-wider text-primary underline-offset-4 hover:underline"
              >
                ✨ Use Sample
              </button>
            </div>

            <textarea
              value={story}
              onChange={(e) => setStory(e.target.value)}
              placeholder={PLACEHOLDER}
              className="min-h-[200px] w-full resize-none rounded-xl border-2 border-border bg-muted/40 p-4 text-sm leading-relaxed text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none md:min-h-[240px] md:text-base"
            />

            {error && (
              <p className="mt-2 rounded-lg border-2 border-destructive/40 bg-destructive/10 px-3 py-2 font-pixel text-[10px] text-destructive">
                {error}
              </p>
            )}

            <div className="mt-5 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
              <Button
                onClick={() => void handleGenerate()}
                disabled={isSubmitting}
                size="lg"
                className="group h-12 w-full gap-2 rounded-xl border-[3px] border-foreground/15 bg-primary px-8 text-base font-bold text-primary-foreground shadow-[4px_4px_0_0_hsl(var(--primary)/0.5)] transition-all hover:-translate-x-0.5 hover:-translate-y-0.5 hover:shadow-[6px_6px_0_0_hsl(var(--primary)/0.5)] disabled:opacity-50 disabled:cursor-not-allowed sm:w-auto"
              >
                {isSubmitting ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  <Wand2 className="h-5 w-5 transition-transform group-hover:rotate-12" />
                )}
                {isSubmitting ? "Creating run…" : "Generate Structure"}
                <Sparkles className="h-4 w-4 animate-sparkle" />
              </Button>
            </div>
          </div>
        </div>

        <div className="mt-10 flex items-center gap-3 text-xs text-muted-foreground">
          <span className="h-px w-12 bg-border" />
          <span className="font-pixel text-[9px] uppercase tracking-widest">made with ♡ + pixels</span>
          <span className="h-px w-12 bg-border" />
        </div>
      </main>
    </div>
  );
};

export default Landing;
