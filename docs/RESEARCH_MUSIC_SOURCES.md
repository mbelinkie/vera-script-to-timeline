# Research Music sources for Timeline

The local authoring host uses the same project-scoped Research Library as
Footage, Stills and Quotes. Configure its existing Research catalog bearer and
loopback URL. Set **VERA_RESEARCH_MEDIA_PROJECT** to the Timeline project UUID,
**VERA_RESEARCH_MEDIA_ROOT** to that project's absolute, non-symlink **Media**
directory, and **VERA_RESEARCH_MEDIA_PYTHON** to the host's VERA Python
interpreter. The workstation uses its existing FFmpeg. The Media directory
must be the one used by Prep Media and accessible to the build workstation.

## Picker API

Use the existing authoring session headers and the visible Research projects
from **GET /authoring/research/{timelineProjectId}/projects**. For each chosen
Research project, read
**GET /authoring/research/{timelineProjectId}/projects/{researchProjectId}/music?offset=0**.
The response is **{ music, nextOffset }**. Follow **nextOffset** even when
**music** is empty. The offset tracks Research's item page before the Music
filter. Each entry contains a **status** and **selection**.

| Status | Meaning |
| --- | --- |
| **candidate** | Research reports a kept original. Selecting it triggers server verification. |
| **relink_required** | Research has the file's preview. The original requires a workstation Relink handoff. |
| **unavailable** | The selection has no eligible kept original. |

Show **selection.title** and its **startMs** and **endMs** on the Research
source clock. Every entry includes **researchProjectId**, **sourceId**,
**itemId** and **itemVersion**. Candidates also carry **sourceVersion** and
**playbackHash**, the SHA-256 of Research's verified kept bytes. The
Research object-store version stays internal to its playback route.
Any other audio role is outside this API.

## Server integration for #764

1. Merge current main into the retained #764 branch. Keep the domain command
   and row UI from **9db63ba3** and **8c771044**.
2. Replace the unavailable picker content with the list above. Submit the
   candidate's complete **selection** as an untrusted selector with the
   existing command's row ID, row version, row edit revision and cue ID.
   Keep Cancel and Escape on the existing focus path.
3. In the authenticated **/authoring/command** adapter, validate the document
   and row command envelope as usual. Call
   **resolveResearchMusicSource(research, researchMedia, document.projectId,
   researchProjectId, selection)** from **research-music-authoring.ts**.
   The resolver rechecks Timeline edit permission and Research visibility,
   compares the current item, source and kept hash with the submitted
   selector, verifies the downloaded bytes, and checks again before returning.
   Map **ProjectAuthError** and **ResearchReadError** to the host's normal
   refusal responses. Offer a reload on 409 and explain the Relink or
   unavailable state on 422. Continue through the serialized command and
   revision-checked save only after successful resolution.
4. Construct the domain command with the returned **source**, and supply
   **[source]** as its separate server-owned **eligibleMusicSources** input.
   Extend #764's retained exact-key source validator to allow the generated
   **researchSelection** property on the canonical source. Keep the full
   pin in the saved cue and in trusted source equality. A browser selector
   cannot authorize a source pin or supply the eligible list.
5. Keep the existing row-bounded initial cue, −12 dB and legacy fade. The
   prepared WAV begins at **selection.startMs** and ends before
   **selection.endMs**, so source frame zero is the selection's first
   sample. **durationSamples** is verified at 48 kHz. Later cue edits can
   use the existing sample-to-frame helper and the prepared selection as
   their source bounds. Preserve the surrounding document and normal Undo.
   Prove creation, save/reload, refusal and one Undo at both #764 viewports.

Prep Media derives the existing **event:** locator from the document, cue and
artifact IDs and verifies the project WAV and exact sample count. Its frozen
script and music binding carry the same **RowAudioSourceV2**, including the
Research selection provenance. Build and signed-package verification use the
existing A5 path. Previous four-field local WAV pins use their original
explicit locator contract.

## Generated native acceptance

In a bootstrapped checkout on the Resolve Mac, launch Studio 21.2 with
external scripting set to Local. Use a new scratch directory and run the
ordinary Build command against the generated 24 fps fixture.

~~~sh
proof_dir="$(mktemp -d)"
prepared="$(PYTHONPATH=tests npm exec --yes --package=node@24.19.0 -- \
  .venv/bin/python -c 'from pathlib import Path; import sys
from test_research_music import prepare_fixture
print(prepare_fixture(Path(sys.argv[1]).resolve())[0])' "$proof_dir" | tail -1)"
npm exec --yes --package=node@24.19.0 -- .venv/bin/python \
  -m vera_timeline_agent.build_timeline_cli \
  --script "$prepared/script.json" --inputs "$prepared" \
  --output "$proof_dir/build" \
  --resolve-app "/Applications/DaVinci Resolve 21.2/DaVinci Resolve.app"
~~~

The command creates a disposable project and performs the save, close and
reopen verification. Expect one A5 cue at source and record frames [0,96),
−12 dB and six-frame fades. Its WAV contains exactly original samples
[48000,240000). The check takes a single short build and uses synthetic media.
