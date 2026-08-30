# Issue #11 reference-render matrix

This matrix is the required source-reference capture set for the first Fusion
rebuild. It deliberately contains no copied source frames or media. The AEP
and producer-supplied PNG render sequence were inspected read-only. The latter
provides the B00 baseline below; every unrendered variant remains a
producer-supervised source-render check rather than an invented visual result.

## Capture protocol

- Render the named source composition, `EV23 lower third 2-2-24`, from the
  producer-supplied AEP without changing or saving it.
- Use source controls only. Record the frame/timecode for first visible pixel,
  end of entrance, start and end of protected hold, start of exit, and last
  visible pixel.
- Retain the reference renders only in the producer-approved source location;
  do not add them to this repository. Record the approved location and checksum
  in the producer acceptance note.
- Inspect at the source canvas size. B00 proves a 1920×1080 output baseline,
  but frame rate, composition duration, source timecodes, and scaling policy
  must still be confirmed in After Effects.

| ID | Phase | Text case | Control variant | Requested duration | Source evidence to inspect | Status |
| --- | --- | --- | --- | --- | --- | --- |
| B00 | Baseline sequence | `“Song Title Goes Here”` / `SINGER GOES HERE` | Observed UK/2024 heart-flag with curved country/year ring; values inferred from visible render | 152 frames; FPS unknown | 1920×1080 PNG sequence; first visible 1; entrance 1–77; stable hold 78–120; forensic measurement anchor 90; **producer-approved placement reference 100 for #12**; exit 121–146; blank 147–151. See inspection report for geometry/motion. | Producer accepted as the #12 placement reference; not a substitute for R01–R12 behavior coverage |
| R01 | Entrance | Short: `Song Title` / `Artist` | `country_identity=Luxembourg`; default icon treatment | 72 frames | first visible pixel, icon/text ordering, trim/scale/opacity progression | Awaiting producer source render |
| R02 | Hold | Short: `Song Title` / `Artist` | Same as R01 | 72 frames | protected hold, alignment, country/year legibility, no residual motion | Awaiting producer source render |
| R03 | Exit | Short: `Song Title` / `Artist` | Same as R01 | 72 frames | exit direction, final visible pixel, overlap with protected hold | Awaiting producer source render |
| R04 | Entrance | Long: `A Very Long Song Title That Exercises Wrapping` / `A Long Performer Credit` | Same as R01 | 72 frames | overflow/wrap/scale behavior and entrance readability | Awaiting producer source render |
| R05 | Hold | Long text | Same as R01 | 72 frames | text safe area and hierarchy under maximum observed copy | Awaiting producer source render |
| R06 | Exit | Long text | Same as R01 | 72 frames | whether exit preserves long-text legibility | Awaiting producer source render |
| R07 | Entrance | Short text | `icon_style=full-circle` | 120 frames | contrast the icon treatment with R01; verify timing scale versus duration | Awaiting producer source render |
| R08 | Hold | Short text | `icon_style=full-circle` | 120 frames | country asset selection and visual balance | Awaiting producer source render |
| R09 | Exit | Short text | `icon_style=full-circle` | 120 frames | exit choreography and final visible pixel | Awaiting producer source render |
| R10 | Hold | Short text | `country_name_in_icon_enabled=true` | 120 frames | whether icon text is an intended viewer-facing variant | Awaiting producer source render |
| R11 | Hold | Short text | `country_name_override_enabled=true`; explicit override value | 120 frames | override precedence, custom-name legibility, country/year relationship | Awaiting producer source render |
| R12 | Hold | Short text | `country_identity=Otis / Custom (w full)` | 120 frames | custom portrait/logo behavior and any source-asset dependency | Awaiting producer source render |

## Matrix completion rule

No row may be silently dropped. A non-renderable source configuration is a
result: mark it **unsupported**, preserve the control values and observed
failure, and request producer judgment. B00 is a geometry and motion comparison
target only: it does not supply 72/120-frame coverage or prove any unrendered
copy/variant behavior. R01–R09 establish the required entrance/hold/exit,
short/long-copy, control-variant, and two-duration coverage; R10–R12 cover the
meaningful semantic variants found during inspection.

## Acceptance observations to record

The producer must decide and record:

1. The canonical duration(s), protected timing boundaries, source frame rate,
   scaling policy, safe-area margins, and supported resolutions. B00's observed
   placement is not an approved safe-area policy.
2. Whether every variant in R07–R12 belongs in the first rebuild, is
   intentionally deferred, or should be removed from the future editor.
3. Whether the visual reference agrees with the migration brief's hierarchy,
   typography, color, and logo assumptions.
