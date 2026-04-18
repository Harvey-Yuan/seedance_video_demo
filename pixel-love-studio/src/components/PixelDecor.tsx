import { Heart, Sparkles, Star } from "lucide-react";

export const PixelHeart = ({ className = "", style }: { className?: string; style?: React.CSSProperties }) => (
  <Heart className={`fill-primary text-primary ${className}`} style={style} />
);

export const PixelStar = ({ className = "", style }: { className?: string; style?: React.CSSProperties }) => (
  <Star className={`fill-accent text-accent ${className}`} style={style} />
);

export const PixelSparkle = ({ className = "", style }: { className?: string; style?: React.CSSProperties }) => (
  <Sparkles className={`text-secondary-foreground/70 ${className}`} style={style} />
);

export const FloatingDecor = () => (
  <div className="pointer-events-none absolute inset-0 overflow-hidden">
    <PixelHeart className="absolute top-[8%] left-[6%] h-5 w-5 animate-float" style={{ animationDelay: "0s" }} />
    <PixelStar className="absolute top-[14%] right-[10%] h-4 w-4 animate-sparkle" style={{ animationDelay: "0.4s" }} />
    <PixelSparkle className="absolute top-[40%] left-[4%] h-6 w-6 animate-sparkle" style={{ animationDelay: "1s" }} />
    <PixelHeart className="absolute bottom-[18%] right-[8%] h-4 w-4 animate-float" style={{ animationDelay: "1.5s" }} />
    <PixelStar className="absolute bottom-[10%] left-[12%] h-5 w-5 animate-sparkle" style={{ animationDelay: "2s" }} />
    <PixelSparkle className="absolute top-[30%] right-[20%] h-4 w-4 animate-float" style={{ animationDelay: "2.5s" }} />
  </div>
);
