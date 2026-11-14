# Presenter source: grade a recording once (#94)

One command puts a presenter recording and its cleaned audio
([presenter-audio.md](presenter-audio.md)) into a single source clip in
Resolve, at the recording's own size. The edit is cut from that clip, so a
grade made inside it reaches every piece.

```sh
uv run --frozen python -m vera_timeline_agent.presenter_source \
  "/path/to/video.mp4" --audio "/path/to/clean.wav" --sample
```

Resolve Studio must be running. By default this makes a new project named
`<video> presenter source`; use `--project NAME` to choose the name, or
`--existing-project NAME` to add to the project that is open in Resolve (it
must be at the recording's frame rate). `--sample` also cuts one tight and one
wide piece into a `<video> FRAMING SAMPLE` timeline to try a grade on.

It creates, then saves, closes, reopens and checks:

- `<video> SOURCE`: a compound clip holding the whole video on V1 and the
  cleaned audio on a mono A1, starting together and the same length.
- `<video> GRADE HERE`: a timeline at the recording's size holding that clip.

**To grade:** open `<video> GRADE HERE`, right-click the clip, choose **Open
in Timeline**, and grade the video there. Nothing is baked into a file.

## Framing

Pieces are cut from `<video> SOURCE` into the 1080p edit
(`presenter_source.place_piece`):

- **Wide** is zoom 1: the source fitted to the frame, showing all of it.
- **Tight** is zoom 2 for a 4K recording in a 1080p edit (source width ÷ edit
  width): pixel for pixel.

A recording smaller than 4K is built at its own size and the command says so.
If it is no larger than the edit, tight and wide are the same picture.

This replaces the per-clip calibrated transform profile from #119 for
presenter framing. #119 framed the raw recording, so a grade could not be
shared; its Wide and Tight were stored numbers with no fixed meaning. Here
they follow from the two sizes.

## What Resolve would not let a script do

Checked on Studio 21.1.1 build 10; details are in
[RK-19](RESOLVE_KNOWLEDGE_GUIDE.md#rk-19--transparent-presenter-proof-is-not-continuous-presenter-reframing).

- **A nested 4K timeline is not pixel for pixel.** Resolve shrinks a timeline
  placed inside a 1080p timeline to 1080p before any zoom. A compound clip
  keeps its full size, so the source is a compound clip.
- **Open the compound clip to grade it.** A script can put a grade on the
  video before the compound clip is made, but cannot reach inside it
  afterwards. Opening it (**Open in Timeline**) and grading is done by hand.
- **Move or trim a piece that is already placed** (vendor answer on #490). The
  script places new pieces only.
