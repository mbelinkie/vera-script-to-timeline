# Slice 0.2 handcrafted input

`timeline-manifest.json` is Slice 0.2 package test data, deliberately outside
the producer-accepted frozen `/fixtures` tree. It references those immutable
media bytes through project-relative `media/...` paths and is resolved with
`--media-root fixtures`.

The audio event uses `fixtures/media/audio-ambient-bed.wav` as **synthetic test
narration** solely for OTIO interoperability. It is not generated speech and
must not be interpreted as a narration-provider fixture.

The track list instantiates the adjustable D-0005 default map. It demonstrates
the accepted defaults; it does not make those IDs, labels, indices, or counts
converter invariants.
