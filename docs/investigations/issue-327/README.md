# Resolve finishing preservation

Native results are pending for [#327](https://github.com/mbelinkie/vera-script-to-timeline/issues/327).
The installed application bundle is DaVinci Resolve 21.1.1 build 10. The
experiment uses a disposable two-row build with synthetic picture and tone.

Use the row map delivered by #522 to identify the original items, and the
save, close and reopen check from #520 to verify persistence. Duplicate the
finished timeline to make an archive. Start each variant from a separate
duplicate and compare its finished items and the archive after reopening.

| Hand finishing | Same length, different clip | Longer second row | Rows swapped |
| --- | --- | --- | --- |
| Row 1 grade | Pending | Pending | Pending |
| Row 1 clip volume | Pending | Pending | Pending |
| Row 1 effect | Pending | Pending | Pending |
| Transition at the row boundary | Pending | Pending | Pending |
| Resolve-only clip on a spare track | Pending | Pending | Pending |
| Archive comparison | Pending | Pending | Pending |

[Blackmagic Developer Support](https://github.com/mbelinkie/vera-script-to-timeline/issues/490#issuecomment-6826230215)
confirmed that Studio 21.1.1 build 10 has no supported in-place scripted move
or trim for the edit they were asked about. The offset and position setters
and `Timeline.MoveItems` first appeared in 21.1.2. Support described a roll
that should retain item IDs but changes the second clip’s source start, and
advised checking handles and persistence. This experiment will establish
which finishing carries through the tested 21.1.1 routes.
