// Local playback experiment only; source time is never inferred from row length.
export function assemble(parts) {
  let end = 0;
  return parts.map((part) => {
    if (!["a", "b"].includes(part.source) || !Number.isFinite(part.in)
      || !Number.isFinite(part.out) || part.in < 0 || part.out <= part.in
      || !["wide", "tight"].includes(part.framing)) throw new Error("Invalid segment");
    const start = end;
    end += part.out - part.in;
    return { ...part, start, end };
  });
}

export function position(parts, time) {
  if (!parts.length || !Number.isFinite(time)) throw new Error("Invalid position");
  const bounded = Math.max(0, Math.min(time, parts.at(-1).end));
  const index = parts.findIndex((part) => bounded < part.end);
  const selected = index < 0 ? parts.length - 1 : index;
  const part = parts[selected];
  return { index: selected, sourceTime: part.in + bounded - part.start, time: bounded };
}

export const cases = {
  continuous: assemble([
    { source: "a", in: 1, out: 3, framing: "wide" },
    { source: "b", in: 3, out: 5, framing: "wide" },
    { source: "a", in: 5, out: 7, framing: "wide" },
  ]),
  partial: assemble([
    { source: "a", in: 1, out: 4, framing: "wide" },
    { source: "b", in: 2, out: 4, framing: "tight" },
    { source: "a", in: 4, out: 7, framing: "wide" },
  ]),
  distant: assemble([
    { source: "a", in: 1, out: 3, framing: "wide" },
    { source: "a", in: 8, out: 10, framing: "tight" },
    { source: "a", in: 3, out: 5, framing: "wide" },
  ]),
};
