# Issue 134 — isolated Resolve Free environment evidence

Status: **Preflight in progress; no target selected and no changes made**  
Evidence date: **2026-09-22**  
Acceptance authority: **External**

This record deliberately excludes serials, UUIDs, personal paths, project
names, source media, private screenshots, and the contents of attached disks.

## 1. Read-only preflight

| Check | Public-safe observation | Result |
| --- | --- | --- |
| Mac | MacBookPro16,1 (16-inch, 2019), 8-core Intel Core i9, 16 GB RAM | Recorded |
| Graphics | Intel UHD Graphics 630 and AMD Radeon Pro 5500M 4 GB; both report Metal 3 support | Meets Resolve 20.2.3's stated Metal requirement |
| Current internal system | macOS 15.1, normal boot, internal 1.0 TB APFS startup device, about 11.0 GB container free | Recorded; internal device is never a target |
| Existing Resolve | DaVinci Resolve Studio 21.1.0 application present on the internal system | Recorded; no Studio data was opened or changed |
| T2 | Apple T2 Security Chip present | External-boot policy must be viewed in Recovery; it is not readable with the normal-boot utility on this Intel Mac |
| External physical devices | One 1.0 TB GUID/APFS device and one 8.0 TB GUID/HFS+ device were attached | Inventory only; neither is selected or known disposable |
| 1.0 TB APFS external | About 854.3 GB in use and 145.7 GB unallocated | Fails the 180 GiB usable gate in its present state; no contents were inspected |

### Current-day version compatibility

- Blackmagic's current Free release is **DaVinci Resolve 21.1** (released
  2026-09-08), but its official Mac requirements specify macOS 15 or later and
  an Apple-silicon computer. It is therefore not a valid selection for this
  Intel Mac.
- Resolve Free **20.3.3** also specifies Apple silicon on Mac and is not valid
  for this Intel Mac.
- Resolve Free **20.2.3** remains available from Blackmagic's support catalog.
  Its official requirements specify macOS 14 or later, 8 GB RAM (16 GB when
  using Fusion), and either Apple silicon or a GPU that supports Metal. This
  Mac's 16 GB RAM and Metal-capable Radeon Pro 5500M satisfy those stated
  requirements.
- Apple's current maintained Sequoia release is **macOS 15.8** (released
  2026-09-14). Resolve 20.2.3 allows macOS 14 or later, so the proposed
  compatible pair is **macOS Sequoia 15.8 + Resolve Free 20.2.3**, subject to
  the Producer selecting that exact pair before installation.
- Apple also lists this 16-inch 2019 MacBook Pro as compatible with macOS 26,
  but current Resolve 21.1 and 20.3.3 exclude Intel Macs. macOS 26 is therefore
  not selected merely because the Mac can install it.

Official sources checked on 2026-09-22:

- [Blackmagic Resolve 21.1 release notes](https://www.blackmagicdesign.com/support/readme/59dd4eef1f4941c29fb8dc48b33f5c87)
- [Blackmagic Resolve 20.3.3 release notes](https://www.blackmagicdesign.com/support/readme/ecc878f9c6aa45399296e75a464ac586)
- [Blackmagic Resolve 20.2.3 release notes](https://www.blackmagicdesign.com/support/readme/857bc3ef1cae4412bccc1c52d21002ea)
- [Blackmagic Resolve support catalog](https://www.blackmagicdesign.com/support/family/davinci-resolve-and-fusion)
- [Apple: macOS Sequoia updates](https://support.apple.com/en-au/120283)
- [Apple: macOS Tahoe compatibility](https://support.apple.com/en-in/122727)
- [Apple: external startup disk](https://support.apple.com/en-au/111336)
- [Apple: Startup Security Utility on T2 Macs](https://support.apple.com/en-ca/102522)

## 2. Mandatory Producer confirmation — external target

**Not yet supplied. Do not erase or format anything.**

With Disk Utility set to **View → Show All Devices**, the Producer must identify
one external *physical device* by public-safe make/model, connection type, and
capacity; confirm that every byte on it is disposable; and state:

> I confirm that `<public-safe make/model, connection, capacity>` is the
> dedicated disposable Resolve Free test SSD. I authorize erasing that whole
> external physical device as GUID/APFS now. The internal 1.0 TB startup device
> is not the target.

Immediately before the erase, re-check that the selected top-level device is
external and matches all three recorded attributes. If any attribute differs,
stop.

| Required target evidence | Recorded value |
| --- | --- |
| Public-safe make/model | Pending |
| Connection type | Pending |
| Nominal capacity | Pending |
| External physical-device identity shown in Disk Utility | Pending |
| Producer confirms all contents disposable | Pending |
| Producer's immediate erase authorization | Pending |
| GUID/APFS after format | Pending |
| Usable capacity after format (must be at least 180 GiB) | Pending |

## 3. Mandatory Producer confirmation — T2 policy

1. Restart into macOS Recovery using Command-R.
2. Open **Utilities → Startup Security Utility** and authenticate locally.
3. Record the selected **Secure Boot** and **Allowed Boot Media** options without
   changing either one.
4. If **Disallow booting from external or removable media** is selected, stop.
   Before changing it, the Producer must state:

> I authorize changing Allowed Boot Media on this Mac to permit external boot
> for the isolated Resolve Free test. Restore it to `<recorded original value>`
> when the external environment is retired.

| T2 evidence | Recorded value |
| --- | --- |
| Original Secure Boot value | Pending |
| Original Allowed Boot Media value | Pending |
| Change required? | Pending |
| Producer's immediate policy-change authorization, if needed | Pending |
| Restoration value | Pending |

Changing the Secure Boot level is not part of the default plan. If the signed
Apple macOS installer fails under the recorded Secure Boot setting, stop and
obtain a separate explicit decision; do not lower security speculatively.

## 4. External-only setup and baseline proof

Perform these steps only after sections 2 and 3 are complete.

| Step | Action | Expected result | Evidence |
| ---: | --- | --- | --- |
| 1 | Erase only the confirmed external physical SSD as GUID/APFS. | Internal startup device remains untouched; external disk has at least 180 GiB usable. | Pending |
| 2 | Install the selected macOS onto the external APFS destination. | The Mac can boot the separate external system. | Pending |
| 3 | Create one test-only local user and decline Migration Assistant/data transfer. | No Studio user, project, database, preference, or media is copied. | Pending |
| 4 | Create one external test root with child locations for project-library, media-storage, cache-proxy, gallery, renders, and VERA-test. | Every test working location is visibly under the external root. | Pending |
| 5 | From the external system, acquire the selected Resolve Free installer from Blackmagic and record the exact version before running it. | Only the selected Free build is installed on the external system. | Pending |
| 6 | Launch Free and record the edition/version and macOS version from the external boot. | The application identifies as Free and matches the selected versions. | Pending |
| 7 | Point project/library, media storage, cache/proxy, gallery, render, and VERA test locations to their external-root children. | No internal or Studio-owned location is selected. | Pending |
| 8 | Create a disposable external project/library, close Free, reopen Free, and reopen the disposable project. | The project/library reopens successfully. | Pending |
| 9 | Shut down, boot the internal startup system, and open existing Studio. | Studio 21.1.0 opens and the Producer sees the prior projects in their existing locations. | Pending |

This proves only the isolated environment baseline. Do not import a #10 or #36
package and do not record acceptance for either issue here.

## 5. Removal and restoration handoff

1. Shut down the external test system and boot the internal Studio system.
2. Confirm Studio opens and the prior projects remain available before any
   removal decision.
3. Shut down before physically disconnecting the external SSD. Do not erase it
   merely to remove it from service.
4. If the Producer later chooses to retire the environment, first export any
   public-safe acceptance evidence under its retention policy. Then re-identify
   the same external physical device in Disk Utility and obtain a fresh,
   immediate erase authorization. Never select the internal startup device.
5. If Allowed Boot Media was changed, restart into Recovery, restore the exact
   recorded original value, restart to the internal system, and re-check Studio.
6. Do not delete or move any Studio application, project, database, media,
   cache, preference, internal APFS volume, or internal file as cleanup.

## 6. Acceptance state

All setup and return-to-Studio evidence is pending. #134 must not move to In
review until the external environment is actually provisioned and every
pending field relevant to the acceptance criteria is filled with public-safe
evidence.
