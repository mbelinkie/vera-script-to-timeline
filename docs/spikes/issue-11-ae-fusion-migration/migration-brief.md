# OEV lower third — Fusion migration brief

## Scope and evidence boundary

This is an investigation brief for the producer-supplied `OEV lower third.aep`.
It is not a Fusion `.setting`/`.drfx`, shared contract, compiler change, Resolve
placement integration, or authoring UI. The source and its collected assets,
fonts, logos, and media were inspected read-only and are not copied into this
repository.

The inspection evidence is in [inspection-report.json](inspection-report.json)
and the render coverage/producer capture protocol is in
[reference-render-matrix.md](reference-render-matrix.md).

## Purpose and information hierarchy

The template is a lower third for identifying a song/performance and its
country/year context. Preserve this reading order:

1. `primary_text` — the principal title, evidenced by the source Main Text
   control and its larger serialized font setting.
2. `secondary_text` — supporting artist/performer information.
3. `country_identity` plus `year_label` — contextual identification tied to
   a country asset/identity selector.
4. Optional icon-label and custom/override treatments — only when the producer
   accepts their visual behavior in the reference matrix.

## Observed 1080p baseline construction

The producer-supplied B00 render is a visual reference, not an approved safe
area, color token set, or responsive layout rule. At its stable hold frame 90,
the render measures as follows (inclusive 1920×1080 canvas coordinates):

| Element | Observed geometry | Preserve as visual behavior |
| --- | --- | --- |
| Whole graphic | `x=73..1061`, `y=738..996`; 989×259 | Bottom-left lower third; observed left/bottom margins are 73/83 px. This is evidence, not a safe-area decision. |
| Badge/anchor | Center ≈`(223,887)`; white circular badge ≈219×219 | Badge is the shared visual anchor and masks the left edges of both bars. |
| Country/year ring | Upper-left annular arc, radii ≈112/150 px; ≈38 px band | Curved uppercase country/year label sits over the arc; retain its circular relationship to the badge. |
| Heart/flag | ≈168×176 inside badge | Thick black heart outline with the country flag inside; B00 proves the heart-flag only. |
| Primary bar and type | Bar `x=320..1061`, `y=806..907` (742×102); one-line black primary copy | Hard-edged blue bar begins behind badge; primary type is visually dominant. |
| Secondary bar and type | Bar ≈`x=283..696`, `y=916..996` (≈414×81); 8 px clear gap below primary bar | Hard-edged translucent-black bar begins behind badge; uppercase white secondary copy is subordinate. |

Observed z-order is: bars and annular ribbon behind badge; country/year label
above the ribbon; heart/flag above badge; and each text layer above its bar.

## Observed motion choreography

The baseline begins visible at frame 1, reaches stable hold at frames 78–120,
and exits at frames 121–146; frame 90 is the forensic hold reference. The PNG
sequence has no authoritative FPS metadata, so these are frame observations,
not timecode or a duration policy.

- Entrance: a radial white stroke/donut grows from badge center; the heart/flag
  grows centrally, turns from left-facing to downward around frames 39–41 with
  directional blur, and the annular ribbon/label rotates and trims into place.
  The primary bar wipes left-to-right across frames 43–68; its text follows
  around seven frames later. The secondary bar begins near frame 59, its text
  near frame 64, and both settle by 78.
- Hold: construction is visually stationary; preserve hierarchy, overlap, and
  readable curved country/year label.
- Exit: text, bars, and ring retract right-to-left through frame 137; the
  text disappears before the backgrounds. A badge-only state begins at 138,
  then collapses around the fixed center with an expo-like scale/opacity finish
  through 146. The exit is intentionally shorter than the entrance.

These are visual motion requirements for reference comparison, not a demand to
recreate the After Effects expressions, keyframe values, or node graph.

## Stable semantic editor inputs

These are intentionally independent of AEP paths, source layer names, Fusion
node names, filesystem paths, and dropdown positions.

| Semantic ID | Type | Rule | Source evidence |
| --- | --- | --- | --- |
| `primary_text` | required text | Must fit the approved source-reference layout. | Main Text |
| `secondary_text` | optional text | May be absent only if the producer accepts the resulting layout. | Sub-Text |
| `country_identity` | required controlled choice | Persist a stable value such as `luxembourg`, never a source dropdown index. | Country, 50 options |
| `year_label` | required text | Preserve the approved country/year reading relationship. | year |
| `icon_style` | producer-confirmed choice | Candidate values are `heart_flag` and `full_circle`; labels must be confirmed from R01/R07. | full circle + layer-selection expression |
| `country_name_in_icon_enabled` | producer-confirmed boolean | Include only if R10 shows a deliberate viewer-facing variant. | circle text |
| `country_name_override_enabled` | conditional boolean | Enables the following value; otherwise it has no effect. | override |
| `country_name_override` | conditional text | Required when the override is enabled; validate it as human-readable. | override text |

The source layout sliders (`textshift*`, `boxheight*`, `boxshift*`) are
implementation controls, not editor inputs. The Fusion implementation should
derive layout from the semantic copy and approved constraints rather than expose
those source mechanics.

## Must preserve

- The information hierarchy and semantic inputs above.
- Country identity behavior, including an explicit custom identity path only if
  R12 is accepted.
- The approved source motion intent: entrance, protected hold, and exit, with
  an in/out-expo reference present in the AEP.
- Approved typography, color treatment, logos, and country imagery after the
  producer identifies licensed, shippable artifacts.
- The observed 1920×1080 construction, badge/ring anchor, overlap/masking,
  hard-edged bar shapes, curved country/year label, staggered wipes, heart
  quarter-turn/blur, and asymmetric exit—subject to producer confirmation in
  B00.
- The exact producer-approved safe area, source frame rate, duration policy,
  scaling behavior, and supported resolutions. The 1920×1080 B00 output is
  evidence only; none of those decisions is approved yet.

## Preferred similarity

- Match the producer-approved reference renders for the visible construction of
  the icon, text hierarchy, graphic line/circle treatment, and entrance/exit
  rhythm.
- Preserve country/year association and the visual distinction between primary
  and secondary text.
- Match B00's rendered colors only after the producer approves color-managed
  brand tokens: observed evidence is blue `#86A9D8` at approximately 85.1%
  alpha, black at the same approximate alpha for the secondary bar, opaque
  white/black type, and the observed heart-flag red/navy. These are not yet
  authoritative tokens.
- Treat the `Ease and Wizz 2.0.6` in/out-expo expression as motion evidence,
  not a requirement to reproduce an After Effects expression or node graph.

## Fusion-native flexibility

- Rebuild the motion using Fusion-native tools, an approved in/out-expo-like
  easing, and data-driven layout; node-for-node conversion is explicitly out
  of scope.
- Use internal auto-sizing/overflow handling instead of the exposed source
  layout sliders, provided it passes R04–R06.
- Use a versioned semantic mapping only in the later approved package work;
  this brief does not create that contract or a template asset.

## Asset and license dependencies

| Dependency | Inspection evidence | Current decision |
| --- | --- | --- |
| Fonts | Arial Narrow; ITC Franklin Gothic LT Pro; serialized Franklin Gothic IDs | License/redistribution status unknown. Do not package or substitute without producer approval. |
| Country artwork | 99 collected references; country icon/flag variants | Retain as producer-owned/licensed source; choose only approved shippable assets in a later slice. |
| Logo/portrait | Custom logo and portrait references are present | Rights, required variant, and production use are unknown; R12 and producer approval decide. |
| Color treatment | Color Control and Tint effects are present | Exact approved values are not recoverable here; sample only from producer-authorized reference renders. |

## Decisions that require producer judgment

| Decision | Default for this brief | Producer acceptance required |
| --- | --- | --- |
| Canonical duration | B00 is 152 frames with unknown FPS; it does not establish a policy. Test 72 and 120 frames in the matrix. | Select one policy/minimum duration and protected timing boundaries. |
| Supported resolution(s) | B00 is 1920×1080 only. | Record source canvas, scaling behavior, and supported output resolutions. |
| Safe area/layout | B00 uses an observed 73 px left / 83 px bottom placement. | Approve safe-area/scaling policy; decide wrap, shrink, truncate, or expansion for long copy and behavior with empty secondary text. |
| Full-circle, icon-label, and override variants | Keep as candidate semantic variants, not guaranteed v1 features. | Accept, defer, or remove each after R07–R12. |
| Custom identity assets | No asset is cleared for packaging. | Approve required assets and license/provenance evidence. |
| Candidate improvement | Prefer auto-layout and typed country identity instead of source dropdown indices/sliders. | Accept only if the matrix demonstrates brand equivalence. |

## Handoff gate for the first Fusion rebuild

The producer accepts this brief only after reviewing the structured inspection
report, B00 baseline, and completed reference-render matrix. At that point,
record the source frame rate; approved fonts/colors/logos; safe area/scaling;
resolutions; canonical duration policy; responsive/empty-copy behavior; and
selected semantic variants. Until then, do not create the Fusion template or
move this investigation to Done.
