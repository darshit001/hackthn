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
