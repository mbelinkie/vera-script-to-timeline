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

**Actual admitted converted source:** The immutable package's source frame
map contains **900 original frames at 30000/1001**, with source origin
`1001/1250` seconds and original probe hash
`sha256:fc5bb2bb98c21bc7c835fe111c95110afca3dfb91004010d34a11e3cd71bfee9`.
Its prepared delivered clip instead has **214 decoded frames at 24000/1001**,
delivered origin zero, and a *distinct* delivered probe hash
`sha256:4286b5c88e3e9ac7af23bac1582a2297c7441ea82ce5eb499084f40856962c2a`.
This distinction was independently read from the retained private admitted
manifest: **requiring original and delivered counts, rates or probe hashes to
be equal would reject the real fixture**. This was corrected in the #472
verifier and mirrored in its converted-source regression.

**Independent read-only media check on the actual Mac:** FFprobe with
`-count_frames` on the retained delivered
`Media/Resolved/42b82702-d6df-59b0-8b9b-201fb3518c64.mp4` measured
`nb_read_frames=214` and `r_frame_rate=24000/1001`. The actual file's
SHA-256 is `803b9a7375d1da5aa52ecac6a9c02071891d8bcb59fddde22410e37f514ce023`,
matching that video's admitted delivered content hash. These checks read
existing bytes only: no Resolve target, result or operation was touched.
Together with the authenticated native full 214-frame record/source time,
this rules out an actually 212-frame delivered file as the cause of the
discrepant integer getter. A *new* native save/reopen experiment is still
needed before calling the application behaviour independently reproduced.

`qualification_output_native_v2._capture_geometry` now recognizes **only** the
two-frame-short integer end at the full decoded-video EOF (not a +/-2
tolerance). It requires the exact admitted full-source range, equal 214-frame
record/source extent, 100% speed, native `Frames` and FPS, the independently
verified decoded count and 24000/1001 rate, original media bytes and matching
delivered hashes and *delivered* probe hashes, matching immutable original
source-frame-map count/rate/probe and mapped source origin, and equal
manifest/view/frame-map mapping and identity. The verified delivered origin is
zero; the original source origin need not be zero. The native source clock
edges must be accurate within one 48 kHz sample of
frame 0 and the *exclusive* decoded EOF. The preexisting native event stamp,
track mapping, media path/hash and subsequent frozen item-UID checks remain
mandatory. No new media decoding, sample-count proof or external evidence is
inferred from Resolve's getter.

The guard rejects interior trims, a genuinely short 212-frame source, an
incorrect end time, an altered start time, any mismatched imported/preparation
rate, hashes, decoded/native counts or invalid original source-map extent,
event/source identity or record
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
