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

`index.html` — a mobile-first landing page for the concept, live at
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
