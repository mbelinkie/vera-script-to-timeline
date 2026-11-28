# Research Music sources for Timeline

Research Music selections come from the same project Library API as clips, stills
and quotes. Timeline authorizes the current account against both projects. It
prepares only audio with a verified kept original. Research file imports expose
a low-resolution preview and report that the original needs Relink.

## Pre-work check

1. Writers can choose a named Research Music selection through the #764 editor.
2. Research Sources §§4.5, 5.3 and 8.6 specify named selections and Music spans.
   S03 r29 D143 specifies the row-menu cue workflow.
3. Prepare the exact saved interval as an immutable project WAV. Reuse the
   existing cue, event locator, Prep Media handoff and A5 delivery.
4. Keep the work inside one issue and one implementation day.
5. Use generated fixtures in the existing tests and run the existing Linux gate.
6. Finish when the authorized source resolves through ordinary Prep Media and
   Build, and the deployed code contract is documented for #764.
7. Verify one generated 24 fps cue after saving, closing and reopening a
   disposable Resolve project.
8. #772 is the remaining prerequisite for the #764 picker.
