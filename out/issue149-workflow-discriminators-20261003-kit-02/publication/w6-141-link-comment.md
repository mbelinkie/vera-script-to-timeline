## #149 Workflow Integration replacement discriminators

Both W6 atomic replacement cases reproduced on Studio 21.1.1.10 through the injected Workflow Integration path, with External Scripting None in a new disposable synthetic project. Kept modified time rendered source ID 1; modified time +1 second followed by RelinkClips rendered source ID 2. Both original files/times and restored rendered source ID 1 were independently verified, with complete captures and terminal job records.

The [complete two-case records](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5966033331) explain the earlier W6 discrepancy for these tested setups and support this bounded #141 design input: **detect replacement by content hash; force reload with changed modified time → RelinkClips → render verification**. Online status, displayed Date Modified and RelinkClips=True do not prove a source switch. Other codecs/cache paths remain unproved.

The #141 report and second-opinion handoff now cite these records. W3 discriminators remain in progress. No issue closure or producer acceptance is inferred.
