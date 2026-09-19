# Arcade Football — 20s Vertical Gameplay Video

A 20-second, vertical 9:16 animated video styled as gameplay from a polished
arcade football mobile game. Produced as a test of the Higgsfield MCP integration.

## Output

| | |
|---|---|
| File | `arcade-football-20s-9x16.mp4` |
| Duration | 20.1s |
| Resolution | 1080 x 1920 (9:16 vertical) |
| Frame rate | 24 fps |
| Video codec | H.264 High profile, yuv420p, faststart |
| Audio | AAC stereo, 48 kHz, normalised to -14 LUFS |

## Generation

- **Model:** `seedance_2_5` (Bytedance, via Higgsfield MCP)
- **Mode:** text-to-video (`t2v`), no reference media
- **Settings:** 20s, 1080p, 9:16, native audio on, high bitrate
- **Cost:** 180 credits

`seedance_2_5` was chosen because it is the only model in the catalogue that
renders a genuine 20-second continuous take at 9:16 with native audio. Other
candidates cap out at 10-15 seconds, which would have forced a stitch and
broken the brief's requirement for one unbroken shot.

The master was delivered as HEVC (Main 10). This repo holds an H.264 transcode
for broad playback compatibility, with audio brought up from a quiet -25.8 dB
mean to the -14 LUFS social delivery standard.

## Beat structure

| Time | Beat |
|---|---|
| 0-4s | **The choice** — dribble toward twin glowing gates `+2` (cyan, left) and `+4` (gold, right); through `+4`; four teammates spawn; counter flips `1` to `5` |
| 4-9s | **Build the attack** — two red defenders beaten with two quick passes and a return ball |
| 9-14s | **The final defender** — red captain drawn to one side, diagonal pass to a teammate free in the box |
| 14-18s | **The shot** — strike to the top corner, slow-motion keeper dive, ball ripples the net |
| 18-20s | **The reward** — celebration, confetti, `GOAL!` and three gold stars |

## Art direction

Stylised cel-lit 3D with chunky toy-like players, vivid striped green turf and
crisp white markings, floodlit night stadium. Blue kits attack, red kits defend,
plain and unbranded. Camera holds a single continuous third-person track from
slightly above and behind the ball carrier, goal always ahead in frame.

## Verification

Checked against the brief rather than assumed from job status:

- Container probed — 20.1s, 1080x1920, 24 fps, stereo audio stream present
- Audio levels sampled per second — active across the whole clip, not silent
- Frames extracted at 15 beat points and inspected; contact sheets kept as
  `storyboard-0-12s.jpg` and `storyboard-13-20s.jpg`
- Confirmed visually: both gate labels legible, counter `1` to `5`, five blue
  players after the gate, a single ball throughout, keeper dive and miss, net
  ripple, confetti, `GOAL!` plus three gold stars

---

# Waitlist Landing Page

`index.html` — a mobile-first landing page for **Goal Rush**, live at
<https://squad-rush.milton-steve.workers.dev>. Built as the destination for a
paid creative test: run the video as an ad, measure what it costs to get a
click and a signup, and only build the game if those numbers hold up.

Working title is **Squad Rush** — a placeholder. It has not been checked for
trademark or App Store name conflicts.

## Before sending any paid traffic

The waitlist does not store anything yet. `CONFIG.WAITLIST_ENDPOINT` in
`index.html` is `null`, and while it is, the form tells visitors the waitlist
isn't open rather than claiming a signup it can't honour — so the page is
honest as it stands, but it will not collect a single address.

To switch it on, set the endpoint to any backend that accepts a POST of
`{email, source, position, ts}` as JSON:

```js
WAITLIST_ENDPOINT: "https://formspree.io/f/xxxxxxxx"
```

Formspree, Formspark and Basin all work on their free tiers and need no
server. A Supabase edge function or any serverless handler works equally well.

## Analytics

`track()` forwards events to Meta Pixel (`fbq`), GA4 (`gtag`) and `dataLayer`
if any are present, and no-ops otherwise. Drop a pixel snippet into `<head>`
and these start reporting with no other changes:

| Event | Fires when |
|---|---|
| `VideoWatch3s` | Hero video passes 3 seconds |
| `VideoUnmute` | Visitor turns sound on |
| `WaitlistSubmit` | Valid email submitted |
| `WaitlistSuccess` | Backend accepted the signup |
| `WaitlistError` | Backend rejected or failed |

The funnel to watch is ad click -> `VideoWatch3s` -> `WaitlistSubmit`.

## Assets

| File | Purpose |
|---|---|
| `arcade-football-20s-9x16.mp4` | Full-quality master, 15MB — the ad creative |
| `hero-loop.mp4` | 720p web loop, 3.3MB — the page hero |
| `hero-poster.jpg` | Poster frame shown before the video plays |
| `storyboard-*.jpg` | Gameplay stills used in the page |

The hero is a separate, smaller encode on purpose: the 15MB master is fine as
an ad upload but far too heavy for a landing page on mobile data, where load
time feeds straight into bounce rate.

## Checked

Rendered in Chromium at 360 / 390 / 768 / 1280px: no horizontal overflow at
any width, no JavaScript errors, and the gameplay video sits within the first
screen on mobile — traffic arrives from a video ad, so the footage has to land
before the fold rather than below the copy.

## Where this is hosted, and why not on cambridgetech.ai

The landing page is deployed to its own Cloudflare project, `squad-rush`,
**not** to `cambridgetech.ai/arcade-football/`. That was deliberate.

`cambridgetech.ai` is served by the Cloudflare Pages project `cambridgetech`,
which is **direct-upload with no Git connection** (`source repo: None`) and was
last deployed on 8 July 2026. It does not build from this repo, which is why
everything merged here since then is absent from the live site — the repo's
`.github/workflows/deploy.yml` publishes to GitHub Pages, which nothing points
at.

More importantly, the live site has **diverged from this repo**, and the live
copy is ahead:

| | Live `cambridgetech.ai` | This repo |
|---|---|---|
| Contact form handler | Posts to `/api/contact`, a Pages Function that emails the team | Absent |
| Form field `name` attributes | Present | Absent |
| Honeypot spam trap | Present | Absent |
| `meal-plan/index.html` | One version | A different version |
| Team card (CTO) | Absent | Present |

So deploying this repo over that project would delete a working contact form
and its server-side function, reopen the form to spam, and publish a team
change that isn't live. That is why the landing page went to a separate
project instead.

**This divergence is unresolved.** The live site contains code — including a
Pages Function with a server-side email destination — that exists nowhere in
version control. It cannot be rebuilt from this repo if it is ever lost.

## 404 handling

The `squad-rush` project sets `not_found_handling: "404-page"`, so unknown
paths return a real 404 via `404.html`. `cambridgetech.ai` instead returns
200 with its homepage for any unknown path, which during a paid test would
silently absorb a broken ad link and make the funnel look merely poor rather
than broken.

---

# Concept rework: gates out, streak in

The original concept (gates that multiply your squad, then a scripted move to
goal) was dropped. Two problems with it:

1. **The squad was an abstraction between the player and the goal.** The
   mechanic is borrowed from crowd runners like Count Masters, where more units
   wins the fight. Football already has the clearest win condition in sport —
   score — so deferring it behind a collection layer is noise.
2. **The player barely played.** Across twenty seconds the only input was one
   gate choice. The passing, the defender and the finish were all the game
   playing itself.

## Goal Rush

Run at goal, weave past defenders, swipe to score, go again faster. The loop is
8–12 seconds:

| Step | Input |
|---|---|
| Auto-run at goal from the halfway line | none |
| Defenders converge | **drag** thumb left/right to weave |
| Cross into the box, time slows | none |
| Strike | **swipe** — arc sets placement and curve |
| Keeper dives; goal → streak +1 and pace increases | none |

Two inputs, one thumb, no buttons. Both idioms are proven: the weave is Subway
Surfers, the swipe-to-place finish is Score! Hero. Every run ends with the
player taking a shot, so nothing is a cutscene.

The streak carries the difficulty curve and the monetisation: each goal adds
pace and a defender, one mistake ends the run, and "continue your streak" on a
rewarded video is the highest-converting placement in score-attack games.

## Creative status

`hero-loop.mp4` is the master trimmed to start at 4.6s, which cuts the gate
sequence. What remains — run, defenders, box, strike, keeper dive, goal,
celebration — reads correctly for the new concept, and the on-screen counter
now reads as a streak.

`arcade-football-20s-9x16.mp4` (the master) **still opens on the gates** and no
longer matches the concept. It should not be used as ad creative as-is.

A purpose-built creative for the ad test still needs generating: it should show
a thumb dragging and swiping, and the slow-motion aim before the strike, so a
viewer can see it is playable. Cost is roughly 180 credits on `seedance_2_5`
at 20s/1080p.

---

# Art direction: Viking × premium-casual

The arcade look (bright plastic toys, vivid green pitch, modern floodlit
stadium) was replaced with a Viking theme carrying a premium-casual finish —
the Royal Match school of mobile art, where polish is the product.

## The rule that governs everything

**Norse flavour lives in the ornament, never in the letterforms.** Carved
timber, hammered bronze, knotwork, torchlight, longship prows. The type stays
a warm rounded face (Fredoka). Fantasy display fonts read as costume and make
a game look cheap; the premium-casual titles this borrows from all use
friendly rounded type and put their theme entirely into the frames, buttons
and props. That contrast is the whole trick.

Second rule: **warm, never grim.** Every surface carries a highlight, nothing
is muddy, gold is reserved for reward. It should look expensive.

## Palette

| Token | Hex | Use |
|---|---|---|
| `--night` | `#0b1728` | Fjord-night base |
| `--timber` / `--timber-2` | `#2c1a0f` / `#1a0f08` | Carved panel surfaces |
| `--bronze` | `#a9763c` | Hammered framing on every panel |
| `--gold` | `#f2b13c` | Torch gold — reward colour, used sparingly |
| `--ember` | `#e2662c` | Firelight accent |
| `--blood` | `#a8302b` | Rival clan |
| `--frost` | `#eaf2fa` | Body text, snow |

## Component language

- **Panels** — timber gradient, 2px bronze border, inset top highlight and
  bottom shade, generous radius. This is the translation of the gold-filigree
  frame those puzzle games wrap around everything.
- **Buttons** — gold gradient, heavy bevel, glossy top inset, warm outer glow.
- **Medallions** — circular hammered bronze with a gold rim, for step numbers
  and icons.
- **Knotwork divider** — a hairline bronze rule with a gold boss, pure CSS.

## Assets

Generated with `gpt_image_2_5` at 1 credit each — deliberately cheap, so the
direction could be proven before committing ~180 credits to video.

| File | Purpose |
|---|---|
| `viking-style/keyart.png` / `.jpg` | Hero key art; the captain |
| `viking-style/gameplay.png` / `.jpg` | In-game view: longship goal, braziers, frost |
| `viking-style/character.png` / `.jpg` | Character sheet for the mascot |
| `viking-style/ui-kit.png` / `.jpg` | UI system: panels, buttons, medallions, chest |

PNGs are the masters and are the only copy — regenerating costs credits and
will not reproduce them exactly. JPEGs are the web-optimised versions the page
actually loads.

## Creative status

The old `hero-loop.mp4` and `arcade-football-20s-9x16.mp4` are the **previous**
art direction and clash with this one. They are kept as history but are no
longer referenced by the page and are excluded from the deployment. Neither is
usable as ad creative now.

A video in this direction still needs generating before any paid test.

## Checked

Rendered in Chromium at 360 / 390 / 768 / 1280px: no horizontal overflow, no
JavaScript errors. The desktop hero needed two fixes — the tall portrait key
art was stretching the grid rows apart, leaving a dead gap between headline and
form, and then pushing the whole hero to ~900px; the rows are now pulled
together at the seam and the art is height-capped with a top-biased crop.
