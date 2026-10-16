# Issue149 — bounded Workflow Integration discriminator follow-up

## Scope

Confirm two W6 atomic-replacement modified-time cases and three W3 entry/operator cases from the producer’s request, against Claude commit67c01157a20716a63a265ce9213afd9b4d948b02. Use a new disposable synthetic project and the injected Workflow Integration object with External Scripting None. Retain full pairs, journals, exact mappings, hashes and attributed outputs; restore owned source bytes/mtime and mapping afterwards.

## Exclusions and frozen contracts

No retained #141 project, protected semi1b.mp4, production reconciler, contracts, frozen fixtures/goldens, dependencies, project deletion, general UI automation or external scriptapp fallback. The new files are experiment-owned fixtures and harness copies, not accepted product fixtures. No package dependencies are added. No issue closure or producer acceptance inferred.

## Planned cases

| Case | Operation | Named required result |
|---|---|---|
| D6-kept | Atomic replace; preservemtime; RelinkClips; render | Original decoded source1 |
| D6-changed | Atomic replace; set newmtime via os.utime; RelinkClips; render | Replacement decoded source2 |
| D3-direct | New never-rendered timeline; WI mapping mute then WI render | Capture mute:true; pilot/words decide support, not setter return |
| D3-console | New timeline; WI mapping mute; operator Console render without remapping | Same output metrics and full Console pair |
| D3-operator | New timeline; WI mapping mute; operator opens Fairlight; WI render | Same output metrics and pair around operator event |

## Checks and acceptance steps

Offline checks validate required phases/source hashes/owned ID guards, exclusive receipts, allowed shape/settings, restoration comparisons and Console helper entry. Native actions remain single dispatch; timeout means collect/poll the same job rather than replay. Independent local analysis uses frame codes, original fixture-word correlations, 1500Hz pilot <=0.001 silence gate, measured SHA256 and terminal render evidence. Context/queue changes are journaled; no silent blanket exclusions to make pairs match.

Producer steps: when staged, run one exact hash-bound Console command using its injected resolve object; on a separate fresh timeline, open Fairlight without changing clips/mapping/controls and reply ready. Detailed project/timeline names and commands will be supplied when their prerequisites have passed. The actor waits for each explicit reply.

Publish five #141 new-result records on #149 and link them from #141’s report. Only if both W6 required results match, retain the adopted bounded design input: detect replacement by content hash; force reload with changed modified time -> RelinkClips -> render verification. #149 remains open for producer review.
