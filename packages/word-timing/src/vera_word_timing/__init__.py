"""vera_word_timing: the shared VERA word-timing engine (#183).

One package for the whole suite (Producer, 2026-10-10). It implements the
Producer-approved #168 ports and contracts: recognisers (Parakeet, Canary,
ElevenLabs, YouTube captions) produce `recognition-artifact/v1`; script
reconciliation produces `script-reconciliation/v1`; aligners (MFA, Qwen
agreement) produce `alignment-artifact/v1`; failures are `port-refusal/v1`.
Script to Timeline imports it; the Research worker calls the JSON CLI.
Engines run in external, configured runtimes and never fall back silently.
"""
