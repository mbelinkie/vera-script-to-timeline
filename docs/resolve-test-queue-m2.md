# Guarded native test queue (M2)

Implementation for #447 extends the M1 queue with an explicit native v2 plan.
M1 plans remain mock-only. A native plan permits one fresh disposable guarded
v2 build and declares save/reopen, events, settings and media obligations.

The queue records dispatch intent and immutable request identity before calling
the existing guarded parent. Every subsequent worker only reconciles that same
operation. Live or uncertain work is never replayed, including after cancellation
or a deadline. Private request paths and raw application evidence stay local;
published queue reports contain only sanitized identities and outcomes.

Native acceptance is pending. This document will record the supported route,
commands and the actual unattended acceptance result before delivery.
