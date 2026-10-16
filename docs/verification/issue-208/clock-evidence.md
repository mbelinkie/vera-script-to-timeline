# Clock evidence for review B2

No system clock was changed. Host CPython 3.12.14 reports:

| Clock | Actual implementation | Adjustable | Resolution |
| --- | --- | --- | --- |
| wall time | `clock_gettime(CLOCK_REALTIME)` | true | 1 microsecond |
| monotonic | `mach_absolute_time()` | false | 1 nanosecond |

[CPython 3.12 time documentation](https://docs.python.org/3.12/library/time.html#time.monotonic)
states that macOS uses the Mach clock and it is shared between processes since
3.10. This supports the host/installed comparison, but actual installed Python
clock facts still need retention during the later runtime gate; no getter or
interpreter in Resolve has been invoked for this evidence.

[Apple XNU 11215.1.10 `timex.h`](https://github.com/apple-oss-distributions/xnu/blob/xnu-11215.1.10/bsd/sys/timex.h#L74)
sets `MAXFREQ` to 500000 ns/s. That converts to 500 ppm calendar-frequency
adjustment, so the supported elapsed comparison permits that proportional
shortfall plus two microseconds for datetime sample precision. Bracket the
current wall sample between monotonic reads, storing the upper monotonic bound
for the next comparison; scheduling pauses are not an elapsed rollback.

[Apple's calendar adjustment implementation](https://github.com/apple-oss-distributions/xnu/blob/xnu-11215.1.10/bsd/kern/kern_ntptime.c#L520)
also applies phase correction and `adjtime`, including a 5000 ppm mode. The
500 ppm allowance is a conservative supported envelope, not a claim that it
covers every legitimate macOS clock correction. A larger adjustment refuses
as clock uncertainty and requires fresh capture. Ordinary ±50 ppm rate skew
over 1800 seconds is tested; a strict observed wall step backward or monotonic
reset still refuses, independently of this allowance.

Limits: between observations, a backward wall adjustment smaller than the
rate/sampling uncertainty may be indistinguishable from rate correction. Two
adjacent target reads are not a transaction, and these clock checks are not
clock authentication. No arbitrary 0.5-second step tolerance is added and no
30-minute authority/result/capability expiry is extended. Exact historical
authority validity and current completed-receipt expiry are separate checks.
The accepted note is byte-identical; this implementation interpretation and
its limits require independent delta review and actual runtime evidence.
