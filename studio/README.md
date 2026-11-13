# Jesus Worldwide Studio

The production line for [@JesusIsWorldwide](https://www.youtube.com/@JesusIsWorldwide): scripts in `content/` become finished, scheduled YouTube videos.

```
content/daily-bread/<month>.md ──daily_bread.py──▶ production/daily-bread/<date>/spec.json
                                                     │
                                         make_short.py (voice, slides, captions, music)
                                                     ▼
                                       production/daily-bread/<date>/video.mp4
                                                     │
                                         yt_publish.py (upload, schedule, playlist)
                                                     ▼
                                    YouTube: private until publish_at, then public
```

`queue_run.py` does the render and upload steps for everything pending, within YouTube's daily quota.

## Setup (already done on this Mac)
```bash
cd studio
python3 -m venv .venv
.venv/bin/pip install --only-binary=:all: edge-tts imageio-ffmpeg -r ../youtube-mcp/requirements.txt
```
Uses the YouTube sign-in from `youtube-mcp/token.json`, Google Chrome for rendering slides, and a bundled ffmpeg (no Homebrew needed).

## Everyday use
```bash
cd studio
.venv/bin/python daily_bread.py ../content/daily-bread/2027-01-january.md   # make specs for a new month
.venv/bin/python queue_run.py --max-uploads 5                              # render + upload what's pending
```
Log: `production/queue.log`.

## Daily automatic run (optional, install yourself)
Run from the repo root (it fills in this computer's folder path):
```bash
sed "s|REPO_PATH|$PWD|g" studio/com.jesusworldwide.studio.plist > ~/Library/LaunchAgents/com.jesusworldwide.studio.plist
launchctl load ~/Library/LaunchAgents/com.jesusworldwide.studio.plist
```
(Installed on the ministry Mac on 13 Nov 2026.)
Runs `queue_run.py` every day at 9:15 am, and catches up after the Mac wakes. To remove it:
`launchctl unload ~/Library/LaunchAgents/com.jesusworldwide.studio.plist && rm ~/Library/LaunchAgents/com.jesusworldwide.studio.plist`

## Choices baked in
| Setting | Value | Why |
|---|---|---|
| Voice | `en-US-AndrewNeural`, rate −6 % | Chosen by the ministry after auditioning six voices |
| Format | 1080×1920, 30 fps, H.264, AAC 48 kHz stereo, −14 LUFS | YouTube Shorts standard |
| Looks | 5 rotating colour themes + rotating music-bed chords | So uploads don't look templated |
| Captions | Word-timed, hidden while the verse card is on screen | Readable on phones, no repeated text |
| Scripture | KJV only | Public domain |
| Publish time | 06:00 GMT, uploaded private with `publishAt` | Morning across Africa and the UK |
| Quota | Max 5 uploads/day (1,600 units each of 10,000) | Leaves room for metadata edits |

## Known limits
- **Altered content (AI) disclosure** can't be saved through the API. Tick it in Studio for each upload (Content → select → Edit → Altered content → Yes).
- The Microsoft neural voice is reached through the `edge-tts` library, which uses Microsoft Edge's read-aloud service. For a monetized channel, switching to an official **Azure Speech** key (free tier: 500,000 characters/month, the same voices) is the licensed route. Ask Claude to swap it once you have a key.
- Renders take about 3 minutes per Short on this 2015 MacBook.
