export function cueExcerpt(cues: unknown, startMs: number, endMs: number, fullText: string): {
  kind: "full" | "cue"; text: string; note: string;
};
