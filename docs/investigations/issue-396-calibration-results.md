# DeepSeek calibration: partial results and delivery decision

Observed 2 November 2026, America/New_York. This supplements the
[quality research and independent Claude critique](issue-396-deepseek-quality-review.md).
It does not qualify a general primary coding agent or authorize another paid call.

## What ran

The Producer approved three synthetic episodes, each with two independent
single-call attempts on `deepseek-v4-pro` and two on `deepseek-flash`, at high
effort and a 65,536-token output ceiling. The whole-episode limit was USD0.80,
the three-episode limit USD2.40, and the existing lifetime limit USD10.
The same private ledger and pre-call reservations governed every attempt.

[#409](https://github.com/mbelinkie/vera-script-to-timeline/issues/409) tests
the first interrupted prefix while preserving review/settings state.
[#410](https://github.com/mbelinkie/vera-script-to-timeline/issues/410) tests
strict input validation. Both are small standalone Python tasks. Each candidate
had frozen visible checks and independently expected hidden results, with only
its target file editable. Repeats began from independent baselines; no repair
or retry was allowed. The model order was ABBA, mirrored on the second task.

| Completed responses on #409 and #410 | Pro | Flash |
| --- | ---: | ---: |
| Candidates passing visible and hidden checks | 4/4 | 4/4 |
| Hidden-case comparisons passed | 32/32 | 32/32 |
| Recorded peak-rate usage charge, USD | 0.021316680 | 0.003778248 |
| Total measured provider time, seconds | 73.41 | 15.57 |
| Completion tokens, including reported reasoning | 4,681 | 2,554 |
| Largest completion, tokens | 1,325 | 856 |

On these completed responses, Flash's recorded charge was about 5.6 times
lower and its measured provider time about 4.7 times lower. These are observed
totals on two tasks, not a controlled estimate for larger VERA work. Cache hits
and different generated token counts also affect the comparison. Provider time
does not include GitHub approval-check quota waits or all host-side checks.
The charge column applies verified usage to conservative peak rates; provider
billing reconciliation remains separate. The total recorded charge for the
eight completed calls is USD0.025094928.

## The incomplete third task

[#411](https://github.com/mbelinkie/vera-script-to-timeline/issues/411) is a
self-contained TypeScript workflow-run policy task with all required types.
Its first Pro request ended after 180.386 seconds without a retained response
or verifiable usage. The runner saved an `ambiguous_no_retry` state and retained
the full USD0.28592256 reservation. It did not run the remaining three trials.
No TypeScript candidate exists to grade or compile.

The receipt binds the reviewed runner, manifest, source and campaign plan.
The missing artifact is the provider response, not the receipt. The runner's
configured provider timeout is 1,800 seconds, so the elapsed time alone does
not establish a configured timeout. Its generic error handler discarded the
underlying exception. Retained evidence cannot distinguish a provider/network
interruption from a caught outer interrupt. This is an execution/accounting
failure of unknown cause, not a demonstrated coding mistake by Pro.

The conservative new commitment remains USD0.311017488, including the unknown
request. The separate prior-account upper bound remains USD6.02. Reservations
are not confirmed charges. No retry or release of the uncertain reservation is
authorized by this report; reconcile provider-side evidence first.

## Recommendation for #396

1. Complete the reviewed secure transport and its separately authorized
   no-provider-call proof. Preserve the outbound-only receiver, native candidate
   confinement, current exact-task review, single-use receipts, frozen checks,
   pre-call reservation, lifetime cap and fail-stop behavior. Keep normal paid
   dispatch disabled after delivery. This calibration is not the transport proof.
2. Prefer Flash at high effort for the next separately authorized small,
   self-contained implementation tasks. The results support that bounded next
   step. They do not establish Flash's reliability on TypeScript, multi-file
   changes, real external applications or a tool-using agent harness.
3. Keep the existing ordinary task/output limits. These successful responses
   provide no evidence that a 65k ceiling is needed for similar small tasks.
   They also do not prove a lower ceiling would produce identical generations;
   evaluate a lower limit separately rather than inferring a causal result.
4. Require complete types, behavioral requirements and relevant frozen checks
   in each task packet. Keep meaningful bounded failure diagnostics. Larger
   inspect/edit/test harness changes remain a separately scoped comparison,
   behind the same trusted spending and isolation boundary.
5. Preserve a safe error classification and stage on future uncertain outcomes
   so transport, host interruption and provider errors can be distinguished.
   Never log credential values or treat an unknown result as permission to retry.

The earlier research and Claude strategy reviews remain applicable. These
partial results strengthen the case for a low-cost Flash implementation worker;
they do not justify declaring the primary-agent qualification complete. #396
delivery can be assessed against its transport acceptance criteria without
replaying #411 or silently dropping any of those criteria.
