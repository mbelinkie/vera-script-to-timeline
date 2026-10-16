# Issue #34 producer acceptance

The retained Studio evidence is
[`studio-assembly-20260922-final.json`](studio-assembly-20260922-final.json).
The dedicated audit project is **VERA Studio build
13000000-0000-4000-8000-000000000036**. It is not a production project.

1. In DaVinci Resolve Free, import the final package's `timeline.otio`.
   **Expected:** the timeline imports without substituting UI automation or
   altering an existing timeline.
2. Inspect the imported timeline. **Expected:** 24 fps, 72 frames, 1920x1080;
   one 72-frame unresolved-visual slate on V1; one 72-frame narration clip on
   A1; and the `Opening` marker at frame 0.
3. Play the timeline. **Expected:** the slate and narration span the full 72
   frames with no extra frame or default 120-frame still duration.
4. Compare those results with the retained Studio evidence. **Expected:** the
   imported Free timeline agrees with the verified Studio assembly in timing,
   tracks, marker, and media placement.

Reply `Accepted Issue #34 Studio/Free assembly.` if all four steps pass.
Otherwise report the first mismatched item and frame.

## Closure exception

On 2026-09-22, the producer authorized closure without the Resolve Free
comparison because only Resolve Studio is installed and Free cannot be
installed alongside it. The successful Studio save/reopen verification remains
the retained External acceptance evidence; the missing Free parity observation
is explicitly recorded in the evidence JSON rather than represented as passed.
