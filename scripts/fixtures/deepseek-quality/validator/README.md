# Small input validator

Implement solve(payload) in target.py. The public task is only this file; do
not change the visible check or wrapper.

The payload must be a JSON object with exactly three keys:
start_frame, duration_frames, and track. All three values must be integers.
Booleans are not integers for this contract, even though Python treats bool as
a subclass of int.

Inclusive ranges:

- start_frame: 0 through 1,000,000
- duration_frames: 1 through 180,000
- track: 1 through 16

Return exactly {"valid": true, "errors": []} when every rule passes.
Otherwise return {"valid": false, "errors": [...]}.

For a non-object payload, errors is ["object"]. For an object with missing or
extra keys, errors is ["keys"] and no value checks are performed. With exact
keys, check fields in this order: start_frame, duration_frames, track. An
incorrect value type adds KEY:type. An integer outside its range adds
KEY:range. Include all field errors in that order. The function must be
deterministic and must not mutate the input.
