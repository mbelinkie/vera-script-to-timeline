Workflow Integration Phase10 W7 re-confirmation. Producer acceptance remains pending; neither issue is closed. Full local record SHA-256 `348daab053cf437c9276b0c53a6545210c5cb6cf0be3145f0e6bbf1ace352b27`. Raw synthetic artifacts are retained locally under out/issue149-workflow-reruns-20261002-kit-01.

# Task ID #149 — W7 lock and UI guard result

## Challenged claim

With a non-empty owned selection, locking all four timeline tracks should guard an Edit-page `Delete Selected` attempt. The API `SetClipEnabled(False)` call should also be refused; unlocking should restore the editable state without changing item identity or content.

## Classification

**Reproduced for the bounded lock and Delete Selected flow.** The owned selection contained V1 `df179a83-7455-4184-a909-0bbbac2500bd` and linked A1 `abd3e5f5-c209-491d-84b1-d82a87e770a2`. The locked proof recorded all four tracks locked and `SetClipEnabledReturn: false`. The exact Hammerspoon `Delete Selected` receipt reports `triggered: true`; the post-observation retained four items, the same item UIDs, unchanged enabled state, and the same canonical content. Unlock readback showed all four tracks unlocked, and the final save returned `True`.

## Run identity and native binding

Injected Workflow Integration run: DaVinci Resolve Studio `21.1.1.10`; CPython `3.14.7`; x86_64 macOS `15.1`; External Scripting `None`. Project UID `1a05ff3a-8b04-43e3-95ab-c970b93b6415`; timeline `W7-lock`, UID `14a27cb4-0ecd-4daa-9e90-38c1ff12bdb5`. V1/A1 share MPI `a25cfcec-f490-4151-a608-6088dae3c5ec`; A2 is `1e34ee0b-76cf-42c5-a7b2-680a97d7c65a`, MPI `a23c9a6e-1640-4db8-b380-b16870ced30c`; A3 is `2e7e9984-762a-4ad7-839e-a6b0adf17410`, MPI `aa4454ba-ce62-4511-976e-e4d1ff92689d`.

The retained injected launcher SHA is `e4f58381c398bc0ce13130fddb25c956876f7754dc877346fe389dfb826c2450`; W7 dispatches use harness probe SHA `a19a79d684f8dbaed6d36bda0d493eed964d37888bddf7749e3bbdf601f59ab5`. The Delete/selection helper is `hammerspoon-lock-test.lua`, SHA `6fafe12a946dfad139c0bd469f6d254337ee2bcfa2ddad0a576ff5c7e27ef054`. The distinct Workflow Integration launch macro recorded in native dispatch receipts is SHA `bc8ca493e2193218208cb43bafaaf90514da9faae4ba51be05b620f5b01ccd02`.

Installed scripting references: README SHA `5f58c94da8ec3c1f390d77ad9c60675263591dc101159b302e50b5774513830b`; stub SHA `2755259ef5f57b5d477786f799892e5b86ed3945db84bf88fb69bf751b36e651`. No render was needed for this structural lock test; no audio or visibility inference is drawn from it.

## Native and UI evidence

| phase | retained evidence |
|---|---|
| timeline selection | `select-timeline-w7-lock-01-20261002-kit-01`; result SHA `ec0322dfbd490cbde23cc2b64b90f2819010b7a4e0b9a551e129312abe7ffac6`; readback page `edit` |
| selection observation | two adjacent `GetSelectedClips` reads; proof SHA `7311926a66d11bd01782a4c759ff9706b204aaa2c3753e98c211235dd6cc2ca7`; canonical pre/post SHA `d17adb63d122307871e4a99624adbdc6f909006509f2a1894bc14a685d14b1e9` |
| lock/setter proof | `w7-locked-proof-01-20261002-kit-01.json`, SHA `4cf171973a89329a32dab2c281709b8af3792fd845e811bd185291b5862a73c0`; all four post locks `true`, `SetClipEnabled` return `false` |
| menu attempt | `w7-menu-deleteSelected-01-20261002-kit-01.json`, SHA `cfa7a8f3b79e805c572693acd1b0c5b84e40937a2074f66ad4a04930242df11c`; receipt `triggered: true`, menu path `Edit → Delete Selected` |
| post-delete observation | result SHA `267c77bc0bd85b9142e89effa32ea43b24e07329990a820bbdc3d99c1d13ced4`; delete-proof SHA `a6cd3dc3bd9fde1faf8d7a2cb548e8c94c8af8bfe3ba407bda504d950a20fba2` |
| unlock and save | unlock journal SHA `3e78bd387c9ad2558b0f81db3e2d13434eb6e0672b9783b74bae35531d973450`; save journal SHA `2a9cc058473622dd0891e729f53a993c973ca236bd51eb73eb4dcb7bbd9748f8`; `SaveProject` returned `True` |

The lock proof's pre/post track state was video 1 and audio 1–3: `false → true`; the unlock pair reads all four as `false` with track enabled still `true`. The Delete Selected receipt was the one actual menu trigger; focus/selection helper receipts are retained separately, and no further mutation is inferred from them.

## State comparison

The delete proof reports item count `4 → 4`, identical item UID sets, selected UIDs unchanged, all four `GetClipEnabled` values unchanged at `true`, and selected V1/A1 names/MPI/link relationships unchanged. A read-only canonical extraction of all four W7 clips and four track lock/enabled states produced identical pre/post SHA `6065d0e6f659a3a79711c1a8c1bd1443a87f8083009e70b4ed58349925f71000`. Raw snapshots differ only in volatile `PyRemoteObject.__repr__` addresses in selected-clip values; the proof explicitly records that limitation.

This supports the selected locked UI path and the `SetClipEnabled(False)` guard. It does not establish that every Resolve edit command, every selection context, or every lock-related API is guarded by the same mechanism.

For VERA's guarded reconciliation, these locks can narrow the risk of the named structural edit while selection, exact ownership and fresh complete captures remain explicit prerequisites. This is not an atomic transaction or revision token. Other API setters and the time between the last check and a later apply remain outside this result; locks alone cannot authorize arbitrary automation. No core script-to-timeline authoring failure was reproduced.

## Retained raw pair hashes

- Selection pair: journal `f233916c6a47d4c07f15e31fe5f60be37fef53372f75444e78fa2b10ca35f613`; pre/post `b1bffc0a23ec870fb28f382720b7059e6566f54b11f80d39e7824ab2f9909ff3` / `7d3a047e500755313dce255151b607f6b0b0c3425026840f1e4956931a65c133`.
- Locked pair: pre/post `d29178da12e12fdaa2bde06c8c616f34da65d657a7c546e81c23fa400214d62f` / `8b805f921d234dbc024fade045304371c4f381a5751b2fe5d18cd6631d6c149d`.
- Delete-observe pair: journal `8ed5151c632f46a6e5082f15193d6d38a4ab2398bd5e4158b11a1ded0a6cd486`; pre/post `e275be86e48ab18cd3fc9b31e1666100c338d8e5bf25f468750debdd9e7392e0` / `1164e813aadaeeefe3f6336715a1239af5e86a37d16878a0db051610940a04d6`.
- Unlock pair: pre/post `394baccd85f5a03e228afc196156190d23160dced77d56bb577ceb96a8171416` / `bcfcd8511415c447b522572953fdb8f47e1233d2c33a30f4534b08c2dbce18f2`.
- Save pair: pre/post `a1ac235d9a3c0b7c05a40341aac331fa8fbaf1dead908c8291db93e5cbb138e8` / `d21f5db4b00b0e60d2d99c792b7d4857b134e3902dcd6d7ba59349fe0a132787`.
