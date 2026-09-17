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
