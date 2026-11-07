# #336 Phase 4 — immutable native OTIO Studio delivery

Phase 4 adds a **separate whole-timeline import** to the normal v2 release and
attestation consumer. When any event has explicit frozen `imageMotion`, the
injected runtime reads the exact already-attested `Builds/<id>/timeline.otio`,
checks its track/event/gap/source/effect/marker structure against the verified
delivery view, and calls `MediaPool.ImportTimelineFromFile` **once** in a new,
explicitly authorized nonproduction project. No `AppendToTimeline` mixing,
fallback, replay, replacement OTIO or modification of earlier package bytes.

The adapter refuses unexpected imported media paths or IDs, missing/duplicate
tracks, events, gaps, duration, target UIDs or Dynamic Zoom state before
stamping the new timeline. It verifies the imported inventory again after
save/close/reopen. Imported timeline markers at exactly expected frames are
restamped on that new target; unexpected markers stop delivery. An uncertain
import leaves the partial named target in place; it must not be retried.

The normal legacy package/Append route remains unchanged when no `imageMotion`
is present. The release includes the native motion module in its byte-pinned
inventory; independent package attestation still checks the original v2 OTIO
and all source media. Fake-Resolve tests demonstrate one-use import, collision
refusal, no duplication/Append, deterministic marker handling and failure
retention. Package/stage tests cover immutable output and tamper refusals.

**Not a production qualification.** The phase-3 synthetic Studio raster results
prove only their particular focus/geometry and black-matte envelope. The
production `native_image_motion.production_qualification()` remains `None`:
arbitrary real authored source/profile/matte combinations cannot yet yield a
motion-bearing production package. Tests inject a synthetic qualification,
never an operator-supplied or automatically trusted one. The installed Resolve
import of a **normal v2 package** (including its relative source references),
duration, clip identity and reopen/render pixels still requires phase-5 Studio
qualification. Failed import/media resolution must remain a refusal, not an
unverified substitute or a success claim.
