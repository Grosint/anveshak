# YouTube Data API v3 — Setup Guide

## 1. Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Name it something like "Anveshak OSINT"

## 2. Enable YouTube Data API v3

1. Go to **APIs & Services > Library**
2. Search for "YouTube Data API v3"
3. Click **Enable**

## 3. Create API Key

1. Go to **APIs & Services > Credentials**
2. Click **Create Credentials > API Key**
3. Copy the key — this is your `YOUTUBE_API_KEY`
4. (Recommended) Click **Restrict Key** and limit to "YouTube Data API v3" only

## 4. Configure Anveshak

Add to your `.env` file:

```bash
YOUTUBE_API_KEY=AIza...your-key-here
YOUTUBE_ADAPTER_ENABLED=true

# Optional tuning
YOUTUBE_DAILY_QUOTA_CAP=9000       # free tier: 10K units/day, reserve 1K headroom
YOUTUBE_POLL_INTERVAL_S=900        # poll every 15 minutes
YOUTUBE_FETCH_COMMENTS=true        # set false to skip comment collection
YOUTUBE_MAX_COMMENTS_PER_VIDEO=100 # limit comments per video per poll
YOUTUBE_BACKFILL_COUNT=50          # initial videos to fetch when channel added
```

## 5. Quota Management

YouTube Data API v3 uses a unit-based daily quota (resets at midnight Pacific Time):

| API Call | Cost (units) |
|----------|-------------|
| `playlistItems.list` | 1 |
| `videos.list` | 1 |
| `commentThreads.list` | 1 |
| `channels.list` | 1 |
| `search.list` | 100 |

Anveshak uses `playlistItems.list` (1 unit) instead of `search.list` (100 units)
for channel monitoring, keeping quota usage minimal.

Captions are fetched via `youtube-transcript-api` (unofficial library, zero API quota cost).

**Budget math:** Monitoring 20 channels, 5 new videos each/day:
- Channel resolution: 20 × 1 = 20 units (cached after first call)
- Playlist fetch: 20 × 1 = 20 units
- Video metadata: 20 × 1 = 20 units (batched 50 per call)
- Comments: 100 videos × 1 = 100 units
- **Total: ~160 units/day** (1.6% of free tier quota)

`YouTubeQuotaGuard` enforces the daily cap atomically via Redis — same pattern
as `XSpendGuard` for X/Twitter.

## 6. Adding YouTube Sources

In the Anveshak UI, add a source with platform "youtube" and any of these URL formats:

- `@ChannelHandle`
- `https://www.youtube.com/@ChannelHandle`
- `https://www.youtube.com/channel/UCxxxxxxxxxx`
- `https://www.youtube.com/c/ChannelName`
- `https://www.youtube.com/user/Username`
- Bare channel ID: `UCX6OQ3DkcsbYNE6H8uQQuVA`

The adapter normalizes all formats to a channel ID automatically.

## 7. On-Demand Video Analysis

For deepfake detection on specific videos:
1. Find the YouTube content item in the Feed tab
2. Click **Analyse Video** button
3. The video is downloaded via `yt-dlp`, keyframes extracted, and run through
   the EfficientNet deepfake detector
4. Results appear in the Vision tab

Requires `yt-dlp` installed in the vision worker container.

## 8. Elevated Quota

For production deployments monitoring many channels, apply for elevated quota:

1. Go to **APIs & Services > YouTube Data API v3 > Quotas**
2. Click **Edit Quotas** or **Apply for higher quota**
3. Government/research use cases typically qualify for 50K-1M units/day

Update `YOUTUBE_DAILY_QUOTA_CAP` to match your approved quota.
