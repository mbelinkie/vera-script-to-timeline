# Manual DeepSeek recovery

Issue #415 adds recovery support to the existing private bounded controller.
The outbound receiver remains mock-only. This contract grants no spending,
dispatch activation or retry authority.

## Preserve the original attempt

An uncertain request keeps its original receipt, manifest, ledger entry and
full reservation. Provider charge evidence can establish that a charge occurred;
it cannot establish a returned response, request ID, usage, candidate or successful
check. A separate immutable reconciliation record documents that distinction and
binds the retained artifacts. It does not rewrite historical accounting or
release held funds.

## A separately authorized new trial

The manual continuation path accepts one new task with its own current Producer
Chat review, exact owner event, immutable manifest and single-use receipt. It
never reopens #411 or the discontinued four-call calibration campaign. A new
task retains the ordinary USD0.25 task ceiling, a USD0.25 single-task campaign
ceiling, and the shared USD10 lifetime ceiling.

Before a provider path, the controller must check the current task, actor and
review; exact source, adapter and manifest; frozen files and checks; approved
model and peak pricing; the shared ledger and lock; all historical costs and
pending reservations. Every unresolved attempt must have matching retained
evidence. Its full reservation still counts. Missing, stale or altered evidence,
duplicate identity, inconsistent accounting or insufficient budget refuses.

## Diagnostics

Future failures retain an allowlisted error category, named execution stage,
whether invocation started, and whether a response was durably retained.
Exception messages, credentials, headers, payloads and private paths are never
part of the safe diagnostic. An interrupted or uncertain provider attempt
remains non-retryable, even if a charge was later observed.

## Verification

Public approval-gate tests use fake GitHub reads. Private controller tests use
temporary ledgers, retained evidence and fake providers. Installed compatibility
is checked without provider access. A future real request needs its own explicit
authorization; a passing offline test does not supply it.
