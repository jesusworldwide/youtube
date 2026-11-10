# Jesus Worldwide · YouTube

Tools and content for growing the [@JesusIsWorldwide](https://www.youtube.com/@JesusIsWorldwide) YouTube channel, an Afro gospel music ministry from Ghana proclaiming the Good News of Jesus Christ.

## What's here

| Folder / file | What it is |
|---|---|
| [`youtube-mcp/`](youtube-mcp/) | **Jesus Worldwide Tools**: an MCP server that lets Claude read channel analytics and update video metadata, thumbnails, playlists and channel settings through the YouTube Data & Analytics APIs. |
| [`website/`](website/) | Static site for https://jesusisworldwide.vercel.app: homepage, [privacy policy](website/public/privacypolicy.html) and [terms](website/public/terms.html), which Google's OAuth consent screen requires. |
| [`METADATA-FIXES.md`](METADATA-FIXES.md) | Ready-to-apply titles, descriptions, tags and channel settings for the existing uploads. |

## Set up the YouTube tools

```bash
cd youtube-mcp
python3 -m venv .venv
.venv/bin/pip install --only-binary=cryptography -r requirements.txt
```

1. Create Google OAuth credentials by following [`youtube-mcp/SETUP.md`](youtube-mcp/SETUP.md), then save the file as `youtube-mcp/client_secret.json`.
2. Sign in once: `.venv/bin/python auth.py`
3. Copy `.mcp.example.json` to `.mcp.json` at the repo root and replace the paths with your absolute paths.
4. Open Claude Code in the repo folder and approve the **youtube** server.

> ⚠️ This repository is **public**. `client_secret.json`, `token.json` and `.mcp.json` are git-ignored. Never commit them.

## Website

Plain HTML/CSS with no build step. To preview it locally:

```bash
npx serve website
```

To deploy it (from the `website/` folder):

```bash
npx vercel --prod
```

`vercel.json` turns on clean URLs, so `/public/privacypolicy` serves `public/privacypolicy.html`.
