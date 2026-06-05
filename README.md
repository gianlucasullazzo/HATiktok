# HATiktok — TikTok Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

A custom Home Assistant integration that exposes your TikTok account statistics as sensors — follower count, likes, video count, total video views, top-N videos by views, and last uploaded video.

---

## Features

- **Profile stats**: followers, likes, video count, total video views
- **Top N videos** (configurable 1–20): each video is a separate sensor with view count as state and thumbnail as entity picture
- **Last video**: sensor showing your most recently uploaded video
- **Configurable polling interval** (default 30 minutes)
- **OAuth 2.0 PKCE** authentication — no password required
- Italian and English UI

> **Note:** Profile views (visits to your profile page) are not available in the standard TikTok Display API. They require the Research API, which requires a separate approval process by TikTok.

---

## Sensors

| Entity | Description |
|---|---|
| `sensor.<name>_followers` | Follower count |
| `sensor.<name>_likes` | Total likes received |
| `sensor.<name>_video_count` | Total number of published videos |
| `sensor.<name>_total_video_views` | Sum of views across all fetched videos |
| `sensor.<name>_top_video_1` … `_top_video_N` | Top N videos by views — state = view count, thumbnail shown as entity picture |
| `sensor.<name>_last_video` | Most recently uploaded video — same structure as top videos |

Video sensors expose these extra attributes: `title`, `video_id`, `view_count`, `like_count`, `comment_count`, `share_count`, `thumbnail`, `create_time`.

---

## Prerequisites — TikTok Developer App

### 1. Create an app on TikTok Developers

1. Go to [developers.tiktok.com](https://developers.tiktok.com) and sign in with your TikTok account.
2. Click **Manage apps → Create an app**.
3. Choose the **Web** platform.
4. Fill in the required fields (App name, description, category).

### 2. Add Login Kit

In the app page, scroll to **Products** and add **Login Kit**.

> The "Display API" as a separate product was removed from the new TikTok Developers portal. All required scopes are now managed inside **Login Kit**.

### 3. Configure scopes

Under **Login Kit → Scopes**, enable all three:

| Scope | Purpose |
|---|---|
| `user.info.basic` | Display name, avatar |
| `user.info.stats` | Followers, likes, video count |
| `video.list` | Video list with per-video statistics |

> The integration degrades gracefully if `user.info.stats` or `video.list` are not yet approved — profile basics will still appear.

### 4. Set the Redirect URI

Under **Login Kit → Redirect URI**, add your Home Assistant URL:

```
https://<your-domain>/auth/tiktok/callback
```

Examples:
- Nabu Casa: `https://xxxxxxxxxxxxxxxx.ui.nabu.casa/auth/tiktok/callback`
- Custom domain: `https://home.yourdomain.com/auth/tiktok/callback`
- Local: `http://192.168.1.x:8123/auth/tiktok/callback`

TikTok allows multiple Redirect URIs per app — add as many as you need.

### 5. Get Client Key and Client Secret

From the **App info** tab:

- **Client Key** (also listed as App ID)
- **Client Secret** (click *Show*)

Keep these credentials safe and never commit them to version control.

### 6. Add your account as a tester

While your app is in **sandbox** mode it can only access accounts registered as testers:

1. Go to **App settings → Tester management → Add tester**
2. Add your TikTok account

---

## Installation

### Option A — HACS (recommended)

1. Open HACS → **Integrations → Custom repositories**
2. Add `https://github.com/gianlucasullazzo/hatiktok` with category **Integration**
3. Search for "TikTok" and install
4. Restart Home Assistant

### Option B — Manual

1. Copy the `custom_components/tiktok/` folder into your HA `config/custom_components/` directory
2. Restart Home Assistant

---

## Configuration

1. Go to **Settings → Devices & Services → Add Integration** and search for *TikTok*
2. Enter your **Client Key** and **Client Secret**
3. Set the number of top videos to track (1–20) and the polling interval in minutes
4. In the **Redirect URI** field enter the exact value registered in the TikTok portal (leave empty for auto-detection)
5. An authorization window will open — sign in and approve all scopes
6. Done. Sensors appear under a device named after your TikTok display name

You can change the top videos count and polling interval later via **Settings → Devices & Services → TikTok → Configure**.

---

## Token refresh

The integration automatically refreshes the OAuth2 access token. If the refresh token expires (typically after 30 days of no use), the integration will enter an authentication error state. To fix it, remove and re-add the integration from the HA UI.

---

## Project structure

```
custom_components/tiktok/
├── __init__.py          # Entry setup and teardown
├── api.py               # TikTok Display API v2 HTTP client
├── coordinator.py       # DataUpdateCoordinator (configurable polling)
├── config_flow.py       # OAuth2 PKCE config flow + options flow
├── sensor.py            # Profile and video sensors
├── const.py             # Constants and URLs
├── manifest.json
├── strings.json         # English UI strings
├── translations/
│   ├── en.json
│   └── it.json
└── brand/
    ├── icon.png
    ├── icon@2x.png
    ├── logo.png
    ├── logo@2x.png
    ├── dark_icon.png
    ├── dark_icon@2x.png
    ├── dark_logo.png
    └── dark_logo@2x.png
```

---

## License

MIT
