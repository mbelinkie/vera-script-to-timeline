# First interrupted prefix

Implement solve(payload) in target.py. The public task is only this file; do
not change the visible check or wrapper.

Every payload is a JSON object with exactly these keys:

- covered_ids: a non-empty array of unique strings in the original order.
- current_order: an array containing every covered ID exactly once, possibly
  with unrelated string IDs between or around them.
- review: any JSON value.
- settings: any JSON value.

Project current_order onto covered_ids by removing unrelated IDs. Return an
object with exactly these keys:

- retained_ids: the longest prefix of covered_ids that exactly matches the
  start of the projected current order.
- review: the input review value, unchanged.
- settings: the input settings value, unchanged.

For example, covered IDs A, B, C, D, E with projected current order
A, B, C, E, D retain A, B, C. If the entire original run moves together,
unrelated IDs before or after it do not shorten the retained prefix.
Preserve review state and settings, including legacy-review-alert states and
unknown fields. Do not mutate the input.
