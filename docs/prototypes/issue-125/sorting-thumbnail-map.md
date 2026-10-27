# Sorting thumbnail assets and fixture mapping

Generated with the built-in image-generation tool as fictional sample imagery for the Sorting comparison, not acquired production media. Generation brief: one square, zero-gutter 4×6 contact sheet of natural documentary photographs; each 3:2 tile has one centrally framed subject from the ordered table below; no people, captions, numbers, labels or watermarks. The original narration, OC/VO spans and visual ordering are unchanged.

Asset: `sorting-thumbnail-atlas.png` (1254×1254 pixels). Exactly 4 columns × 6 rows, numbered 1–24 left-to-right then top-to-bottom. Display only the mapped photo in each thumbnail and its hover preview; never display the full sheet inside a thumbnail. CSS atlas positioning is sufficient; use the same tile for repeated visual identities.

The source grid has no gutters. With a 3:2 thumbnail/preview box, use `background-size: 400% 600%`; x positions by column are 0%, 33.333333%, 66.666667%, 100%; y positions by row are 0%, 20%, 40%, 60%, 80%, 100%. Use the attached image asset URL available within the design project, not a local filesystem path.

OC means a neutral On Camera slot, without an orange/gold fill and without hover enlargement. `Unavailable` is the intentional missing s10 first thumbnail; do not fill it with another tile.

| Tile | Row | Column | Planned visual |
| --- | --- | --- | --- |
| 1 | 1 | 1 | harbor entrance overview |
| 2 | 1 | 2 | ticket window detail |
| 3 | 1 | 3 | tide notebook and waterline observation page |
| 4 | 1 | 4 | recipe card |
| 5 | 2 | 1 | jar of pale salt crystals |
| 6 | 2 | 2 | folded letter inside a clear sleeve |
| 7 | 2 | 3 | blank card beside the sleeve |
| 8 | 2 | 4 | red light on a worktable |
| 9 | 3 | 1 | paper shoreline model with a painted signal wheel |
| 10 | 3 | 2 | knot notebook and short length of soft cord |
| 11 | 3 | 3 | rope spool detail |
| 12 | 3 | 4 | small basket of chalk |
| 13 | 4 | 1 | raincoat cuff and yellow pocket patch |
| 14 | 4 | 2 | shallow tray of smooth gray stones |
| 15 | 4 | 3 | workbench overview |
| 16 | 4 | 4 | folded blue cloth and paper pattern |
| 17 | 5 | 1 | chalk-marked pattern and repaired seam |
| 18 | 5 | 2 | amber lantern resting on a shelf |
| 19 | 5 | 3 | chalk crescent on a slate |
| 20 | 5 | 4 | slate with changing chalk marks and blue paper star |
| 21 | 6 | 1 | empty chair beside a dark window |
| 22 | 6 | 2 | row of paper lanterns |
| 23 | 6 | 3 | quiet table with one lantern |
| 24 | 6 | 4 | harbor doorway and daylight window |

## Complete ordered visual sequences

Fixture IDs are internal mapping keys only; never display them as row numbers. For one visual show one right-side thumbnail; for multiple visuals show first and last with +N between them when middle beats are hidden. Do not deduplicate equal endpoints.

| Fixture row | Ordered tiles / camera states |
| --- | --- |
| s01 | 1 → 2 → 1 |
| s02 | 1 → OC → 3 |
| s03 | OC |
| s04 | OC → 4 → 5 |
| s05 | 6 → OC → 7 |
| s06 | 8 → 9 |
| s07 | OC → 10 → OC |
| s08 | 1 → 11 → 3 |
| s09 | OC |
| s10 | Unavailable → 12 |
| s11 | OC → 13 → OC |
| s12 | 14 |
| s13 | 15 → OC → 15 |
| s14 | OC |
| s15 | 16 → OC → 17 |
| s16 | 18 |
| s17 | 19 → OC → 20 |
| s18 | OC |
| s19 | 21 |
| s20 | 22 → OC → 23 |

Short controls: On Camera = OC; visual-only harbor door = tile 24; short VO/window + lower-third overlay = tile 24 (overlay adds no foreground beat).

Acceptance: all available non-OC slots show actual photo content; hover/focus shows the same mapped tile enlarged without shifting rows; s01 uses tile 1 at both ends, s02 ends with tile 3, s13 uses tile 15 at both ends; s10 remains unavailable at its first endpoint.
