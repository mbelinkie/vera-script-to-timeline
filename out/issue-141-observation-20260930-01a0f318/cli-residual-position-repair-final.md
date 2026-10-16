The local repair is ready for root review in [independent-residual-sequence.py](independent-residual-sequence.py) and [residual-position-repair-result.json](residual-position-repair-result.json).

The driver now reuses the approved deselection label at either stage and checks its labels against the actual readback module. The optional position checkpoint binds the retained records, checks the recorded state, and takes a fresh read-only context before continuing. The result records that preparation, first cut, and position are skipped.

Compilation, `--check`, and retained-record binding with wrong-checkpoint-SHA refusal passed. No Resolve action or source-media read occurred. Native execution remains pending root review and driver hash registration.