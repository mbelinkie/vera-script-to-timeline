# Checkpoint11 initial result correction

The posted segment prompt claimed a current 37-pass run before its output was
inspected. That sentence was premature and incorrect; the full posted command
output already showed 36 passed / 1 failed. Corrected prompt/source now retain
the actual failure: the cross-narration test asserted that the old document
validated, but the accepted validator already forbids narration-owned visuals
anchored to another row. The test now asserts validator refusal and original
input preservation. The implementation did not need a correction. New actual
focused result follows, never count the failed run as passing evidence.

## Original output

```text

 RUN  v4.1.11 /Users/matthewbelinkie/.codex/worktrees/d404/VERA Script to Timeline/packages/contracts

 ❯ test/issue-144-text-revision.test.ts (37 tests | 1 failed) 139ms
     × refuses anchors owned by another narration row rather than altering it 9ms

⎯⎯⎯⎯⎯⎯⎯ Failed Tests 1 ⎯⎯⎯⎯⎯⎯⎯

 FAIL  test/issue-144-text-revision.test.ts > Issue144 accepted omission canonical transformation (no acceptance/proof authority) > refuses anchors owned by another narration row rather than altering it
AssertionError: expected false to be true // Object.is equality

- Expected
+ Received

- true
+ false

 ❯ test/issue-144-text-revision.test.ts:103:52
    101|     second.visualEvents[0]!.id=id(221);
    102|     document.activeDraft.blocks.push(second);
    103|     expect(validateScriptDocument(document).valid).toBe(true);
       |                                                    ^
    104|     const original=canonicalJson(document);
    105|     expect(()=>omit(document)).toThrow(/cross-narration/);

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[1/1]⎯


 Test Files  1 failed (1)
      Tests  1 failed | 36 passed (37)
   Start at  01:36:27
   Duration  806ms (transform 141ms, setup 0ms, import 478ms, tests 139ms, environment 0ms)


```

## Corrected focused result

```text

 RUN  v4.1.11 /Users/matthewbelinkie/.codex/worktrees/d404/VERA Script to Timeline/packages/contracts


 Test Files  1 passed (1)
      Tests  37 passed (37)
   Start at  01:38:24
   Duration  808ms (transform 126ms, setup 0ms, import 465ms, tests 118ms, environment 0ms)


```
