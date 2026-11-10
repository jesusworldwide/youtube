# Connect Claude to the Jesus Worldwide YouTube channel

The connection code is already built and installed in this folder. What's left is
creating your own free Google API credentials (about 20 minutes) and signing in once.

**Use the Google account that owns @JesusIsWorldwide** (or is an Owner/Manager of its Brand Account).

---

## 1. Create a Google Cloud project
1. Go to https://console.cloud.google.com and sign in.
2. Accept Google Cloud's terms if this is your first time (no payment card is needed).
3. Click the project picker at the top, choose **New Project**, name it `Jesus Worldwide YouTube`, then click **Create**.
4. Make sure the new project is selected in the top bar.

## 2. Turn on the two YouTube APIs
Go to **APIs & Services**, then **Library**, then search for and **Enable** each of these:
- **YouTube Data API v3** (edit videos, playlists and the channel)
- **YouTube Analytics API** (views, watch time, retention, countries)

## 3. Set up the sign-in screen (OAuth consent)
Go to **APIs & Services**, then **OAuth consent screen** (also called **Google Auth Platform**), then **Get started**:
- App name: `Jesus Worldwide Tools`
- User support email: your email
- Audience: **External**
- Contact email: your email
- Agree to the policy and click **Create**

Then open **Audience** and click **Publish app**, then **Confirm**.
> Why: in "Testing" mode Google signs you out every 7 days. Publishing keeps you signed in.
> You don't need Google's verification because only you will use it.

## 4. Create the client credentials
Go to **Clients** (or **Credentials**), then **Create client** (or **Create credentials**, then **OAuth client ID**):
- Application type: **Desktop app**
- Name: `Claude YouTube`
- Click **Create**, then **Download JSON**

Save the downloaded file **into this folder** and rename it exactly:
```
client_secret.json
```
so it sits at `JESUS IS WORLDWIDE/youtube-mcp/client_secret.json`.

## 5. Sign in once
Run in Terminal:
```bash
cd "/Users/KWABI/Documents/LYM DEV/JESUS IS WORLDWIDE/youtube-mcp" && .venv/bin/python auth.py
```
A browser window opens:
1. Pick the account or channel for **Jesus Worldwide**.
2. If you see "Google hasn't verified this app", click **Advanced**, then **Go to Jesus Worldwide Tools**. It's your own app, so this is expected.
3. Tick the permissions and click **Continue**.

The terminal should say: `✅ Connected to: Jesus Worldwide`.

## 6. Turn it on in Claude
Start a new Claude Code session in the `JESUS IS WORLDWIDE` folder and approve the **youtube** server when asked.
Then you can ask Claude things like:
- "Show me last 28 days of analytics by video"
- "Apply the fixes in METADATA-FIXES.md"
- "Which countries watch us most?"

---

## What Claude can do with it
| Read | Change (Claude asks before each one) |
|---|---|
| Channel stats, description, keywords | Video title, description, tags, category |
| All videos and Shorts with stats | AI / altered-content disclosure |
| Playlists | Upload custom thumbnails |
| Analytics: views, watch time, retention, subscribers, traffic sources, countries, devices | Channel description, keywords, trailer |
| | Create playlists and add videos |

Not possible through Google's API (do these in Studio): links on the channel header, profile picture and banner, deleting videos.

## Safety
- `client_secret.json` and `token.json` are your keys. **Never share or upload them.**
- To disconnect at any time, go to https://myaccount.google.com/permissions, then remove **Jesus Worldwide Tools**, and delete `token.json`.
- Google allows about 10,000 API "units" per day. Each video edit costs about 50, so you can edit roughly 200 videos a day.
