# #472 — guarded 214/212 Studio video EOF readback

The first authenticated #312 M4 `construct` result is immutable **partial**
(SHA-256 `828300c7eff029091bb76c0a9cca06195797db73a290fb1b9e42d46f272b3578`).
Its video:1 event `f5871317-bdb5-558b-8c05-6ed0fe4b6889` had an admitted
source range `[0,214)` at 24000/1001, a real 214-frame record at unit speed,
`GetSourceStartFrame()=0`, `GetSourceEndFrame()=212`, media `Frames='214'`,
and `GetSourceStartTime()=0.0`, `GetSourceEndTime()=8.925583333333332`.
The latter is the 214-frame exclusive EOF at this rate, **not** the 212-frame
source time. The originally admitted full-frame count, source identity and
hash bindings must remain independently validated. The native integer getter
alone cannot establish that the media was truncated; the partial result itself
does not certify a completed native edit or prove the entire fixture.

`qualification_output_native_v2._capture_geometry` now recognizes **only** the
two-frame-short integer end at the full decoded-video EOF (not a +/-2
tolerance). It requires the exact admitted full-source range, equal 214-frame
record/source extent, 100% speed, native `Frames` and FPS, the independently
verified decoded count and 24000/1001 rate, original media bytes and matching
delivered/probe hashes, equal manifest/view/frame-map mapping and identity,
zero origin, and source clock edges accurate within one 48 kHz sample of
frame 0 and the *exclusive* decoded EOF. The preexisting native event stamp,
track mapping, media path/hash and subsequent frozen item-UID checks remain
mandatory. No new media decoding, sample-count proof or external evidence is
inferred from Resolve's getter.

The guard rejects interior trims, a genuinely short 212-frame source, an
incorrect end time, an altered start time, any mismatched imported/preparation
rate, hashes, decoded/frame-map/native counts, event/source identity or record
duration. Other integer end getters retain prior strict behaviour. Tests use
the immutable observation as a **mocked readback**, not as a new live Studio
experiment; see `tests/test_issue145_native_range.py` and existing #209/#215
regressions.

**Safety and acceptance:** The original partial target, operation ID, result,
evidence and PR #323 were not changed or replayed. A new authenticated
same-target Studio save/reopen readback **has not been performed by this code
change**. Any new physical experiment must use a newly authorized disposable
target and the exclusive native owner lock, not the historical M4 target. #473
owns unattended orchestration and is untouched here. #312 remains **Blocked**
until a wholly new full M4 acceptance succeeds, independently of this PR.
