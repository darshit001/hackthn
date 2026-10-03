# Frontend redesign: a studio, not a form

Date: 2026-10-02. Replaces the light "paper" UI in `static/index.html`. API unchanged.

## Why

The first UI was a form with a progress table under it. For a live demo the video is the product, so the
page should look like the thing it makes: dark, cinematic, phone-shaped, matching the glass deck.

## Tokens

| Token | Value | Role |
|---|---|---|
| `--bg` | `#120826` | page; the deck's card ink and the video's own gradient card |
| `--glass` / `--line` | `rgba(255,255,255,.06)` / `.14` | control panel, inputs |
| `--ink` / `--muted` / `--dim` | `#F6F2FF` / `#B3A6D9` / `#7D6FA6` | text hierarchy |
| `--violet` / `--violet-2` | `#7C4DFF` / `#9B7BFF` | brand, primary button, phone fill |
| `--yellow` | `#FFD400` | the one "live" accent: fill edge, live dot, focus ring, post-text rule (same yellow as the captions) |
| `--danger` | `#FF6B6B` | failed jobs |

Type: Unbounded 700 for the wordmark, headline, section titles and the stage word inside a phone; DM Sans for
everything else. Scale 12 / 14 / 15 / 17 / 19–20 / 27.

Radii carry hierarchy: phone 28, panel 22, controls 12, pills 999.

## Layout

Desktop: sticky 420 px control panel left; output right. Mobile: one column, panel first.

```
┌ wordmark ─────────────────────────────── ● 2 in progress, 5 ready ┐
│ ┌ panel (glass) ───────┐  Making now                               │
│ │ headline             │  ┌────┐ ┌────┐   phones fill bottom-up    │
│ │ topics textarea      │  │▒▒▒▒│ │    │   one step per stage       │
│ │ Suggest topics  …    │  │████│ │▒▒▒▒│                            │
│ │ ideas chips          │  └────┘ └────┘                            │
│ │ Community  ○○○○○○    │  Ready to post                            │
│ │ Language   ○○○       │  ┌────┐ topic                             │
│ │ Length     ○○○○      │  │vid │ post text  [Copy] Download  Delete│
│ │ [ Make 1 video ]     │  └────┘                                   │
│ └──────────────────────┘                                           │
```

## The one bold element

A job in progress is a phone silhouette. A violet fill rises one sixth per finished stage with a thin yellow
edge; the stage word sits in the middle in Unbounded, with "stage n of 6" under it. Queued phones sit at 4 %.
A failed phone turns its border red, shows where it stopped and a "Try again" button. When done, the fill is
replaced by the real video. Nothing else on the page animates except the pulse on the stage word and a toast
for copy/delete; reduced motion turns both off.

## Features added

- Ctrl/Cmd+Enter starts the videos from the textarea.
- Header tally: "2 in progress, 5 ready" with a live dot.
- Toasts confirm copy, delete and start instead of relabelling buttons.
- Empty state invites action; errors say where the job stopped and what went wrong.

## Checked against generic tells

No tinted near-black, no caps eyebrows, no middle-dot meta strings, no arrows in buttons, no identical card
grid. Glass panels and the mesh glow are the deck's established look (brief-grounded, one static glow, no
floating blobs). Stage numbering is kept because the stages are a real sequence.

## Revision, same day: ui-ux-pro-max design system applied

The user asked for the colour and UI type recommended by the ui-ux-pro-max design intelligence for this
product ("AI short video generator for a social feed, creator tool, Indian audience, live demo"). Its
recommendation, applied in full:

| | |
|---|---|
| Style | Vibrant & Block-based: solid colour blocks, high contrast, large type (28-34 px headings), 48 px+ section gaps, bold hover colour shifts at 200-300 ms |
| Colours | primary `#7C3AED` (AI purple), secondary `#6366F1`, accent/CTA `#EC4899` (generation pink), background `#FAF5FF`, foreground `#0F172A`, muted `#F7F3FD`, border `#EFE7FC`, destructive `#DC2626` |
| Type | Space Grotesk (headings, stage word, CTA) / DM Sans (everything else) |

How it maps: the control panel is one solid primary block with white controls and a pink CTA; the output
column sits on the light ground with white content blocks; phones are slate `#0F172A` blocks whose fill is
primary with a pink edge; hashtags take the secondary indigo. Structure, copy, the phone-fill element,
keyboard and reduced-motion behaviour are unchanged from the section above. The dark glass version is kept
in git history (`c9e6e7e`) if a dark mode is wanted later; the tokens are already on `:root`.

Also fixed while verifying: the page now keeps polling every 8 s when idle, so a job started from another
tab or the API appears without a reload.

## Revision 2, same day: "make it not look AI-generated"

The user rejected the violet/purple as the generic "AI purple" and asked, strictly, for a page that does not
read as generated. The move is from landing page to software: the page now looks like a tool a real team ships.

- **Chrome:** white ground, `#F7F7F7` form panel, `#E3E3E3` hairline borders, `#141414` text, `#5C5C5C`
  secondary. No gradients, glass, glow or shadows. Radius 6 px on controls, 8 px on thumbnails.
- **Colour only where it means something:** black primary button; amber "Making", grey "Queued", green
  "Ready", red "Failed" badges; the 22 px brand mark keeps Qoneqt's own purple-to-pink (their logo), nowhere else.
- **Type:** Instrument Sans, one family, 13-15 px, tabular numerals. Headings are labels ("New video",
  "In progress", "Ready to post"), not marketing lines.
- **Controls:** native `<select>` for Community and Language, a segmented control for Length, a plain list
  with "Add" buttons for suggested topics instead of chips.
- **Rows, not cards:** each video is a list row with a 9:16 thumbnail, title, status badge, one meta line,
  a determinate progress bar with "Images, step 2 of 6" while making, and the post text plus Copy / Download /
  Delete when ready. Photo credits are no longer shown (still recorded in the job JSON).
- **App bar:** wordmark, live tally, and an "Open Global Feed" link so posting is one click away in the demo.

Earlier looks stay in git history: dark glass (`c9e6e7e`), Vibrant & Block-based (`7a24006`).

## Revision 3, same day: structured like a video tool (reference screenshot)

The user brought a GPT-made mockup of the page and asked for its structure, minus the invented features
(credits, Upgrade, bell, avatar, nav tabs, Video style, Tone, Voice, Subtitles). API unchanged.

**Taken from the reference**

- Light grey page (`#F4F5F7`) with white panels and cards, hairline borders, 12 px card radius.
- Form steps are numbered (1 Topics, 2 Community, 3 Language, 4 Length) because they are a sequence.
- Community is a 3×2 grid of icon tiles (globe, cpu, dumbbell, flame, rupee, smile); Language is a native
  select with a globe prefix; Length is four bordered pills. Selection = blue `#2563EB` border on `#EEF3FF`.
- Black full-width "Generate video" button with a play glyph; under it "About a minute per video" and the
  Ctrl+Enter hint.
- Right column: "Your videos" heading, search box, tabs All / Ready / In progress / Failed with counts.
- One video = one card: 96 px portrait thumbnail with duration badge (the hook title lives at the top of the
  frame, so no landscape crop), status pill, topic as title, hook + caption excerpt (2 lines), meta row with
  icons (community, language, length, voice), hashtag chips, "Created 2 hours ago", Copy text, Download MP4
  and a ⋮ menu.

**Added**

- Thumbnail click opens the video in a native `<dialog>` at up to 86 vh instead of a tiny inline player.
- The ⋮ menu (a `<details>`) holds "Redo scene n" per scene and "Delete video".
- Search filters by topic; tabs filter by status; a single list keeps in-progress videos on top.
- In-progress cards reuse the layout: grey fill rising in the thumbnail, progress bar, "Images, step 2 of 6".

**Kept** Instrument Sans only, tabular numerals, amber / grey / green / red status pills, brand purple-pink
only in the 26 px mark, toast for copy/delete/start, reduced-motion switches transitions off. One shadow
exists, on the floating ⋮ menu.

## Revision 4, 3 Oct: the video being made is the show

Finale polish for a projector demo. Structure of Revision 3 kept; API gains read-only live fields.

- **Type:** Bricolage Grotesque (opsz 12–96, 500–700) for h1/h2, card titles, the stage word in a phone and the
  empty-state title; Instrument Sans stays for every control and label. Sizes up one step: h2 28, h1 22, card
  title 17, excerpt/meta 14/13, tabs 14, primary button 15 at 46 px tall.
- **The one bold element: the live card.** 144 px dark phone screen; the community's own caption colour (from
  `/presets` `accent`) rises inside it one sixth per stage until the first AI still lands, then the newest still
  fills the screen with a thin accent progress line at its foot and the stage word on a bottom scrim. Six
  story-style bars (Script, Images, Voice, Scenes, Captions, Render: done = ink, current = amber pulse) replace the
  single progress bar; under them a plain verb ("Generating images, 3 of 8") with a live elapsed clock, the hook
  once the script is written, and a filmstrip of every still so far (scene title on hover).
- **Quiet rows for everything waiting:** queued and failed videos are 72 px compact rows on a light screen
  ("Next up", "2nd in line"; "Stopped at Voice" on a red tint). Only the video being made is dark.
- **Ready cards:** 112 px thumbnail, "Made in 1:22" from `seconds_to_make`, silent looping preview on hover
  (pointer devices only, off under reduced motion). Empty state shows a dashed phone silhouette.
- **Pagination:** 10 per page, "Showing 11–20 of 30", first/last/neighbours with gaps; tab or search resets to
  page 1; a delete past the last page steps back.
- **API:** `pipeline.make_video` writes `out/<id>/plan.json` after planning; `/jobs` adds `started` and, for a
  running job, `hook`, `scenes` (titles), `shots` and `stills` (gen*.png present) read from that folder;
  `/presets` adds `accent`. One test covers the live fields.
- Motion inventory: fill/bar transitions, the pulse on the current step, the hover preview, the toast. Reduced
  motion turns the first three off.
