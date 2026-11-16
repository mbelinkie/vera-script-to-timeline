# Presenter timeline from approved takes (#48)

One command builds a new Resolve timeline in which the presenter's approved
takes replace the temporary voice. Each take's picture and cleaned sound are
cut from the recording's graded source clip
([presenter-source.md](presenter-source.md)), so a grade made there reaches
every take. Pictures tied to a spoken word land on that word as the presenter
said it.

## Before it

1. Find the takes and approve one per row
   ([presenter-takes.md](presenter-takes.md)).
2. Freeze the timing with `recorded_conform_cli`
   ([same guide](presenter-takes.md#recorded-timing-from-approved-takes-47)).
   Its output folder is `--snapshot` below, and the prepared inputs it read
   are `--prepared`.
3. Clean the audio ([presenter-audio.md](presenter-audio.md)) and build the
   source clip ([presenter-source.md](presenter-source.md)). Leave that
   project open in Resolve Studio.

## The command

Run it from the repository root:

```sh
uv run --frozen python -m vera_timeline_agent.presenter_conform \
  --snapshot "/path/to/recorded preview" \
  --prepared "/path/to/prepared inputs" \
  --video "/path/to/recording.mp4" --audio "/path/to/clean.wav" \
  --existing-project "recording presenter source" \
  --output "/path/to/a new folder"
```

Add `--resolve-app "/Applications/DaVinci Resolve 21.1.1/DaVinci Resolve.app"`
when Resolve is not at the standard path.

It always makes a new timeline, in the project that holds the source, then
saves, closes, reopens and checks it. Earlier timelines are left alone, and
the command checks that they still read the same.

## What the timeline holds

- **V1 "Presenter":** each approved take, cut from `<video> SOURCE` at the
  approved frames. Wide is zoom 1; tight is pixel for pixel (zoom 2 for a 4K
  recording). Wide takes are blue and named `OC WIDE <row>`; tight takes are
  orange and named `OC TIGHT <row>`, so either kind can be selected at once.
- **A1 "Presenter sound":** the cleaned sound of the same take, linked to its
  picture and cut at the same frames, so they cannot drift.
- **V2 and up:** the script's own pictures, exactly as the normal build
  places them, at the recorded word times. Where the script says the
  presenter is on camera, nothing covers V1.
- **A2 "Narration":** the temporary voice, only for rows approved to keep it.
  Those rows also keep their temporary presenter picture.

A take runs for its whole row on V1. A change between presenter and footage
inside a row is a picture on V2 over it, not a cut in the take. Two rows cut
from neighbouring frames of the recording play through without a jump.

## When it stops

It stops before touching Resolve, and says which, when:

- a row still needs a decision;
- the video is not the recording the takes were found in (it names both);
- the open project has no source for the recording;
- the recording and the script's timeline have different frame rates
  (nothing is retimed);
- a clip is too short for where the recorded words put it. The clip is named.
  Nothing is looped, frozen or slowed; choose a longer clip or another
  picture and freeze the takes again;
- recorded timing changed what a trimmed clip must cover. Prepared clips are
  trimmed for the temporary voice's timing; prepare the media again for the
  new timing.

If Resolve fails after the timeline exists, the command says the unfinished
timeline is left in the project; delete it before trying again.

## Limits

- Frame rates are the normal build's: 24, 25 and 30 fps. A 29.97 or 23.976
  fps recording cannot be built into its source project yet.
- Stills and slates verify on Studio 21.1.1; the normal build does not yet
  verify them on 21.2.
- A script with a music bed keeps the normal build's fixed music track; that
  combination was not checked.

## Checked in Resolve

Studio 21.1.1 build 10, November 16, 2026, synthetic 4K 24 fps recording and
a four-row script in a throwaway project: three takes (one tight, two cut
from neighbouring frames), one row left on the temporary voice, a slate
anchored to a word whose recorded time moved, and clips over a take. Details
are in [RK-52](RESOLVE_KNOWLEDGE_GUIDE.md#rk-52--presenter-takes-cut-into-a-normal-build-from-a-graded-compound).
