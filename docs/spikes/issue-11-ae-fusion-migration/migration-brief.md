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
- The exact producer-approved safe area, canvas size, frame rate, duration
  policy, and supported resolutions. None is extractable from the current
  evidence, so none is approved yet.

## Preferred similarity

- Match the producer-approved reference renders for the visible construction of
  the icon, text hierarchy, graphic line/circle treatment, and entrance/exit
  rhythm.
- Preserve country/year association and the visual distinction between primary
  and secondary text.
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
| Canonical duration | No duration is approved; test 72 and 120 frames in the matrix. | Select one policy/minimum duration and protected timing boundaries. |
| Supported resolution(s) | Unknown. | Record canvas size and supported output resolutions. |
| Safe area/layout | Unknown. | Approve margins and long-copy behavior from R04–R06. |
| Full-circle, icon-label, and override variants | Keep as candidate semantic variants, not guaranteed v1 features. | Accept, defer, or remove each after R07–R12. |
| Custom identity assets | No asset is cleared for packaging. | Approve required assets and license/provenance evidence. |
| Candidate improvement | Prefer auto-layout and typed country identity instead of source dropdown indices/sliders. | Accept only if the matrix demonstrates brand equivalence. |

## Handoff gate for the first Fusion rebuild

The producer accepts this brief only after reviewing the structured inspection
report and completing the reference-render matrix. At that point, record the
approved fonts/colors/logos, safe area, resolutions, canonical duration policy,
and selected semantic variants. Until then, do not create the Fusion template
or move this investigation to Done.
