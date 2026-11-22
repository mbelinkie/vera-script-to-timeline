# Timeline #60 F19 Compare handoff

Matthew accepted the [F19 Compare interaction](https://github.com/mbelinkie/vera-script-to-timeline/issues/60#issuecomment-7084069824) on November 22, 2026, in the separate [Claude Design r3 pilot](https://claude.ai/design/p/011eee38-8b6b-48aa-a154-d6c0060d4f23?file=S03+60+F19+Compare+pilot+r3.dc.html). It uses the accepted [r36 authoring design](../../issue-59/r36/README.md) as its reference.

## Try it

Open **Update available** on the clip in the script. Preview either range in the same dialog. Playback leaves the saved range intact. **Keep this range** keeps the script's trim. **Use this range** changes that use to the Research range and confirms the change on the card. Closing keeps the old range. On access denial, the comparison clears and focus returns to the update control or the card. Routine media preparation stays in the background, and a failure offers **Try again**.

This is a frontend pilot. Playback is sample media. Project access, media preparation and saving are fixture states. The script card shows the clip range and update flag. The shortcut between multiple uses has its own [design issue #695](https://github.com/mbelinkie/vera-script-to-timeline/issues/695).

## Scope for final conformance

| Scenario | Disposition |
| --- | --- |
| S12 · Research | Use this F19 artifact for range comparison and choice. Reuse the accepted Library search, filters, placement, trim and access presentation from r36 and [#642](https://github.com/mbelinkie/vera-script-to-timeline/issues/642). Production work stays with [#643](https://github.com/mbelinkie/vera-script-to-timeline/issues/643), [#83](https://github.com/mbelinkie/vera-script-to-timeline/issues/83) and [#84](https://github.com/mbelinkie/vera-script-to-timeline/issues/84). The range editor, overlap-based count and pre-save notice, and end-to-end update proof remain in [Research #121](https://github.com/mbelinkie/vera-research-video-clips/issues/121), [#687](https://github.com/mbelinkie/vera-script-to-timeline/issues/687) and [#688](https://github.com/mbelinkie/vera-script-to-timeline/issues/688). |
| S13 · Picture placement | Carry forward **Attach to words**, **Reselect range**, visual types, and visuals-only holds from r36. Defer a separate start/end/duration editor and a broader type-classification pass until a concrete script needs them. |
| S14 · Collections and variants | Carry forward Stash for parked material and ordered visuals for sequences. The extra section-linked Stash view remains deferred under the r36 decision. Defer switchable narration variants, Option sets and Resolve Comparison stacks under [#161](https://github.com/mbelinkie/vera-script-to-timeline/issues/161). The [Propose cut retirement](https://github.com/mbelinkie/vera-script-to-timeline/issues/62#issuecomment-6514560671) governs the old F24 scenario. |

Use these dispositions for [#62](https://github.com/mbelinkie/vera-script-to-timeline/issues/62)'s later integrated conformance review.
