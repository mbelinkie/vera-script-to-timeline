# VERA Research Sources: functionality spec

Accepted by the Producer (Matthew) on 17 November 2026. Goal: #640. Written by Claude from the
chatbot draft (`VERA_Unified_Research_Sources_Spec.docx`), an adversarial
review against the real code, and Matthew's answers. It replaces the chatbot
draft and is the product source for the issues in section 13.

## 0. Decisions made while reviewing the draft

- A second quote from the same article, placed right after the first,
  stretches the existing background instead of adding another (§8.3).
- Shortened text belongs to each use, like a clip's trim; the Library offers
  your latest version as the default (§5.1).
- The quote box uses the existing transparent Graphic rules (§8.2).
- There's no Place… menu: drag, then delete any piece you don't want.
- Research's third tab and the editor panel are both called **Library**.
- A typed quote with no picture of its own gets a placeholder background
  card of the existing Need to Find type (§8.4).
- Citations follow MLA 9th edition (§10).

## 1. Goal and scope

Research becomes one library for everything a video uses: footage, quotes,
stills and audio, from YouTube, web pages, files on your Mac and typed-in
offline sources. The editor's Footage panel becomes a **Library** panel over
that library. Everything is captured as issues now. Matthew picks the first
group to build; **quotes are high priority for the first working release.**

Out of scope: importing quotes or links from existing Google Doc scripts;
social posts; charts; scheduled re-checking of web pages.

## 2. Concepts

- **Source**: where something came from. One YouTube video, one web page, one
  PDF, one book or other offline source, one image, one audio file, one local
  video file. Holds the bibliographic details (title, author, publication,
  publisher, date, URL) once.
- **Item**: something you logged from a source and can use: a **clip**, a
  **quote**, a **still** or an **audio** selection. One source can have many
  items of different kinds, for example a YouTube video with clips and an
  audio selection, or an article with quotes and a still.
- **Use**: one placement of an item in a script. One item can be used many
  times, with different treatments and different trims or shortened text.
  Placing never copies or changes the item.
- **Topics**: Research's existing tags. Every item kind uses them; filters
  work the same everywhere.
- Every item records who logged it (the logger filter keeps working).

## 3. Ways in

### 3.1 VERA Chrome extension (the main way in)

You browse in your own Chrome, logged in to your subscriptions, so paywalls
and bot blockers stop mattering.

| On a… | You do | VERA gets |
|---|---|---|
| Article or any web page | Highlight a passage → **Log quote** (toolbar button, right-click or shortcut) | Exact text, URL, page details (§4.2), the two pictures (§6) and where the highlight sits on the passage picture. A small pop-up shows the quote and lets you add speaker name, title, Topics and a note before saving. |
| Image | Right-click → **Save as still** | Image file (VERA keeps a copy), its URL, the page it was on, alt text and any credit it can find |
| Web page, nothing highlighted | **Save page** | The page as a source with its two pictures, ready for later quotes |
| YouTube video | **Send to VERA** | The video added to Research Sources, the same as pasting its URL, then queued for transcription |
| Audio or video file link | Right-click → **Save audio** | Audio source from that link |

- The first quote from an article creates its source. Later quotes from the
  same article (same address, ignoring tracking bits) join that source.
- The extension signs in to your VERA. It's installed unpacked for Matthew;
  publishing it for colleagues needs a one-time $5 Chrome Web Store developer
  fee.
- Chrome's built-in PDF viewer doesn't let extensions read your highlight, so
  PDFs come in through §3.2.

### 3.2 Research "+ Add"

YouTube URL · web page URL · image URL · audio URL · file from this Mac
(video, image, audio) · PDF (scheduled after web quotes) · **typed quote**.

### 3.3 Editor Library panel "+ Add file"

Adds a file from your Mac to the same library. It's the same thing as Research
"+ Add" › file, with two ways in. This replaces a separate editor-only import
screen.

## 4. Source kinds

### 4.1 YouTube video
As today. New: any logged clip can also be placed as **audio only** (§8.6).
There is no separate audio logging for YouTube.

### 4.2 Web page
- Details VERA fills in automatically, and you can correct: title, author(s),
  publication, publish date, URL. Every automatic value shows that it was
  found automatically until you confirm or edit it. VERA never invents a
  missing value; it stays blank.
- Clean article text, extracted where possible, so you can log more quotes in
  Research without the extension (§7.3). If extraction fails, Research says so
  and you can still type a quote against this source.
- The two pictures (§6).

### 4.3 Offline source (for typed quotes)
Kind (book, print article, interview, letter, document, other), title,
author(s), publication or publisher, date, URL (optional), notes, optional
picture (for example a photo of the cover). A second quote from the same book
only needs its own text and page.

### 4.4 Image
From a URL, the extension, a file, or cropped from a web page's picture.
VERA keeps a copy, so a dead link doesn't break a build. Fields: original URL,
page it came from, credit, licence or usage note. Having a copy doesn't mean
permission to use it. On-screen credit is optional for each use and off by
default.

### 4.5 Audio
File or URL. Waveform, playback, named selections with in/out, Topics. Role,
optional: Sound effect, Ambience, Music or Speech. Speech is transcribed like
YouTube video, so you can select a passage by its words.

### 4.6 Local video file
Logged like a YouTube video (clips with in/out, transcript) but played from
the file. See §11 for what others can see.

### 4.7 PDF (after web quotes)
Research shows the pages; you highlight on the page. The page image is the
quote's background and Spotlight picture, so Spotlight comes almost free.

## 5. Item kinds and their fields

### 5.1 Quote
| Field | Notes |
|---|---|
| Original text | Exactly as in the source. Required. Never changed by placing. |
| Speaker name | Optional. A quote doesn't need a speaker. |
| Speaker title | Optional, separate field (for example "CEO of Acme"). Templates decide how to show it; the EV24 box joins it as "Name, Title". |
| Page / location | Optional (book page, PDF page, section). |
| Surrounding words | Saved automatically with web quotes, so VERA can find the passage again. |
| Highlight position | Where the passage sits on the passage picture (extension) or PDF page. |
| Topics, note, logger | As for clips. |
| Citation | Built from the source (§10); can be overridden on the quote. |

Each **use** has its own **display text**. It starts as the latest version you
used, else the original text, and you edit it freely: VERA adds no "…" and
doesn't enforce a match. The original always stays in Research.

### 5.2 Still
Image, title, Topics, credit, licence or usage note, link to its source.

### 5.3 Audio selection
In/out, name, role, Topics, transcript excerpt (Speech).

### 5.4 Clip
Unchanged.

## 6. Web page pictures

Every web page source gets two pictures:

1. **Top of article**: the first screen of the page. This is the default
   quote background.
2. **Passage picture** (one per quote): the screen scrolled so the passage is
   in view, plus the highlight's position. This is used for Spotlight.

- From the extension: whatever your Chrome window shows, at Retina sharpness
  (usually 2560 pixels wide or more). Extension pictures count as pictures you
  supplied, so pages behind logins are fine.
- From a pasted URL: VERA's own capture browser (#39) at 1920×1080 at double
  sharpness (3840×2160), public pages only. It's extended to scroll to the
  passage for the passage picture. Today it only takes the top of the page.
- Pictures never change once taken. **Recapture** makes a new version, and
  existing uses keep theirs until you switch.
- If a page can't be captured (blocked or paywalled with no extension), the
  source and quotes still work. You can drop in your own screenshot, and the
  quote box works with any background.

## 7. Research screens (Research #75 design)

### 7.1 Sources tab
One list mixing every source kind, with a kind icon, filterable by kind
(YouTube, Web page, File, Offline, Image, Audio) and Topic. "+ Add" as in §3.2.
Extension arrivals show up here immediately.

### 7.2 Workspace tab, by source kind
- **YouTube / local video**: as today (player, transcript, log clips).
- **Web page**: clean text on one side, the pictures on the other, with the
  source's details and citation editor. Highlight text to log a quote. The
  page's existing quotes are listed and clicking one shows it on the text and
  passage picture.
- **Offline source**: the details form and its quotes; "New quote" form.
- **Image**: big preview, credit and licence, crop to a new still.
- **Audio**: waveform, transcript (Speech), named selections.
- **PDF** (later): page view with highlight.

### 7.3 Typed quote (manual logging)
"+ Add › Typed quote" opens one form. First choose the source: pick one you
already have (search) or create an offline source (§4.3). Then: quote text
(required), speaker name, speaker title, page, Topics, note, optional picture.
Save and **Save and add another** (keeps the source). The same form edits any
quote, including extension quotes with wrong details.

### 7.4 Library tab (today "Clips")
Research reads Sources → Workspace → Library: where things came from, where
you work on one, and everything you've logged.
Every logged item, filterable by kind and Topic, with type-appropriate cards:
clip thumbnail, quote text with speaker and citation, still image, audio
waveform.

### 7.5 Extension pop-up
Part of the same design: the quote confirmation pop-up, the still pop-up and
the "sent" toast.

## 8. Editor (the #125 r30 design, #642)

### 8.1 Library panel
Rename Show footage › **Show library**. It's the same Library as Research's
third tab. Kind filter: All, Footage, Quotes,
Stills, Audio. Search covers clip titles and transcripts, quote text,
speakers, source titles and credits. Logger, Topic and usage filters, Sort,
thumbnail slider, "Used N times" with step-through, Place in script… and drag
all work for every kind. ⌘⇧F quick search covers every kind. "+ Add file" as
in §3.3.

### 8.2 The quote box is a transparent Graphic (no new layering design)
The quote box uses the existing transparent Graphic rules (#123): a fine
dashed card outline and its own range marks; cards are ordered by first word;
the range can overlap the picture beneath; and the base stays continuous, so
it is never a cutaway and never triggers "On Camera resumes". Two boxes in
turn over one long background are simply two transparent Graphics.

### 8.3 Placing a quote
**Drag a quote into the script (default)** does three things in one Undo:

1. inserts the quote text into the narration as spoken words, at the drop
   point;
2. adds a **background** visual (the article's top-of-article picture) on
   those words;
3. adds a **quote box** overlay on the same words.

- The narration is ordinary text afterwards; editing it never touches the box.
- Both visuals keep their own range brackets: drag the background's start
  earlier so the article shows first, then the box comes in.
- Placing right after another quote from the same article extends the
  existing background instead of adding a second one.
- No Place… variants: to use only some pieces, drag normally and delete the
  card you don't want. Inserted words remember their quote even with both
  cards deleted, so the source still appears in the source list (§10).
- Dropping onto existing words (not between them) attaches to those words
  and inserts no text.

### 8.4 The background visual
A Web Capture or Still Image visual like any other: replaceable with any
still, slow drift by default (#336 motion), and usable without a quote.
**Spotlight** is an option on it, off by default: "Highlight the passage"
switches it to that quote's passage picture with the highlight. That covers
"article with the passage highlighted, then the box comes in". A typed quote
uses the picture you attached to it or its source. Without one, it gets a
**placeholder** background card: the existing Need to Find type, so it shows
up as something still to find and builds as a slate until you replace it.

### 8.5 The quote box card
Shows the display text (editable on the card), speaker name and title, the
citation (editable) and the template. Shortening the text is a card edit.

### 8.6 Stills and audio
- Stills place as Still Image visuals, exactly as today.
- Audio places by role:
  - Sound effect: at a word;
  - Ambience or Music: spanning words, using the music-cue work (#326);
  - Speech: spanning words, like a clip's sound.

  The exact audio rules (fades, levels, overlap with narration) need their own
  design pass before audio placement is built.

### 8.7 Stash
Quotes, stills and audio can sit in Stash and be attached to notes, the same
way as footage.

## 9. Build in Resolve

- **Quote box**: the EV24 Quote Box Fusion title on the graphics track, over
  the background on a lower track. VERA fills its fields:
  - Quote: the display text;
  - Name: "Name, Title";
  - Citation: §10;
  - Italic Start and End: computed;
  - Quote Size: chosen from length.

  Its length follows the linked words.
- **Background**: the picture with drift; with Spotlight, the existing
  Spotlight route (#29, #41) using the saved highlight position.
- **Missing pieces** are flagged in the build report and never silently
  dropped: no picture, or an original file not on this Mac.
- **Proofs needed early**, in real Resolve:
  1. the title sits above a still on the right track (the template's notes
     say Resolve's scripting can't aim the insert);
  2. the longest quote that fits at each size;
  3. a quote box over a drifting background.

## 10. Citations

- **MLA 9th edition**, built automatically from the source details. Missing
  parts drop out the way MLA says, with no stray punctuation. Examples:
  - Web or print article: Last, First. "Article Title." *Publication*, 14
    Mar. 2023.
  - Book: Last, First. *Book Title*. Publisher, 2019, p. 42.
  - Article with no author: "Article Title." *Publication*, 14 Mar. 2023.
  - YouTube or other video: "Video Title." *YouTube*, uploaded by Channel,
    14 Mar. 2023.
- **On screen**, the citation leaves out the URL and access date. The source
  list export gives the full MLA entry, including the URL.
- **Italic:** MLA italicises only the container title (the publication, book
  or website). That's one run per citation, which is exactly what the EV24 box
  supports. VERA computes the template's Italic Start and End, so you never
  touch the sliders.
- Editable on the quote (all uses) and on a single use.
- **Source list export**: every source used in a script, in full citation
  form, as text to paste into a YouTube description.
- Later: project-chosen citation pattern and quote template (§12).

## 11. Files on your Mac

- Originals stay on the owner's Mac. VERA stores identity, metadata, a
  thumbnail and a low-quality preview (images: a thumbnail; video and audio: a
  short low-res preview), so colleagues can see and hear what it is.
- Building needs the originals on the Mac doing the build. Missing or moved
  files are flagged with **Relink**.
- Research is hosted on Matthew's MacBook (Research #53), so "server storage" is that
  disk, not a paid service.

## 12. Later (captured as issues, not first)

PDF sources · project-chosen quote templates (template registry, field
contract: quote, speaker name, speaker title, citation, italic runs) and
citation pattern · on-screen still credits · audio placement rules · local
video logging · extension in the Chrome Web Store.

## 13. Issues

Filed 17 November 2026, all Priority P1. Unprefixed numbers are in this repo;
"Research #" numbers are in `mbelinkie/vera-research-video-clips`. Tiers:
Zodex (simple), Codex (medium), Astra (trickiest).

| Issue | What | Tier |
|---|---|---|
| Research #75 | Research design: every source kind, typed quotes, extension pop-ups (scope expanded) | Producer design |
| #642 | Design: #125 r30 — Library panel and quote placement | Producer design |
| Research #76 | General source and item model: one library for clips, quotes, stills and audio | Astra |
| Research #77 | Quote records and API | Codex |
| Research #78 | Web page sources: page details, clean text and citation fields | Codex |
| #641 | Page pictures for quotes: top of article, passage picture and user-supplied pictures | Astra |
| Research #79 | VERA Chrome extension: log quotes, stills, pages and YouTube videos from your own browser | Astra |
| Research #80 | Typed quotes and offline sources | Zodex |
| Research #81 | Research UI: mixed Sources list, web page workspace and Library tab | Codex |
| #629 | Quote box in the script and Resolve build (revised) | Astra |
| #630 | MLA citations and source list export (revised) | Codex |
| #643 | Editor Library panel: every kind, and three-part quote placement | Codex |
| #644 | Spotlight option on quote backgrounds | Codex |
| Research #82 | Stills: image sources, kept copies, credit and crop from a page picture | Codex |
| #645 | Stills from the Library in the editor and build | Zodex |
| Research #83 | Audio sources: waveform, named selections, roles and speech transcription | Codex |
| #646 | Audio placement by role, including YouTube clips as audio only | Astra |
| Research #84 | Files on your Mac: register by reference, previews for others, missing-file relink | Astra |
| Research #85 | PDF sources: page view, highlight to log a quote, page picture for Spotlight | Codex |
| #647 | Project-chosen quote templates | Codex |
| #648 | Stash holds quotes, stills and audio | Zodex |

Also: #85 (local-file import screen) now registers into the same Library.

Shortest route to quotes in the first working release: Research #75, #642, Research #76, Research #77, Research #78, #641, Research #79, Research #80, Research #81, #629, #630, #643.
