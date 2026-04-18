import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";

/** JSON viewer with copy (optional panels). */
export function ApiJsonBlock({ title, data }: { title: string; data: unknown }) {
  const [copied, setCopied] = useState(false);
  const text = JSON.stringify(data ?? null, null, 2);
  const copy = () => {
    void navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <div className="overflow-hidden rounded-xl border-[3px] border-border bg-muted/20">
      <div className="flex items-center justify-between gap-2 border-b-2 border-border bg-muted/50 px-3 py-2">
        <span className="font-pixel text-[9px] uppercase tracking-wider text-muted-foreground">{title}</span>
        <Button type="button" variant="outline" size="sm" className="h-7 gap-1 font-pixel text-[9px]" onClick={copy}>
          {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
          {copied ? "OK" : "Copy"}
        </Button>
      </div>
      <ScrollArea className="h-[min(50vh,420px)]">
        <pre className="p-3 font-mono text-[10px] leading-relaxed text-foreground/90">{text}</pre>
      </ScrollArea>
    </div>
  );
}
