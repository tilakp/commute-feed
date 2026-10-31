# Commute Mix podcast feed

This repo has one podcast feed (`feed.xml`) with episodes for my commute. Use the feed in a podcast app to download the episodes and listen offline.

A weekly job in the **Muse** app adds new episodes to `feed.xml`. You do not have to do anything to get them.

## Feed URL

```
https://tilakp.github.io/commute-feed/feed.xml
```

Use this URL in the podcast app. Do not use the github.com link of the file.

## Add the feed to Overcast (iPhone)

1. Open Overcast.
2. Tap **+** (top right).
3. Tap **Add URL**.
4. Paste the feed URL and tap **Done**.
5. Open the show and download the episodes.

## Add the feed to Apple Podcasts

**iPhone:**

1. Open Apple Podcasts and go to the **Library** tab.
2. Tap **...** (top right), then tap **Follow a Show by URL**.
3. Paste the feed URL and tap **Follow**.
4. Open the show and tap the download icon on each episode.

**Mac:** in the Podcasts app, select **File > Follow a Show by URL**.

The show is private. It is only in your library and not in the Apple Podcasts directory.

## How the feed is updated

1. Each week, the Muse job adds new episodes to `feed.xml` in this repo.
2. GitHub Pages publishes the new file in about 1 minute.
3. The podcast app gets the new episodes the next time it checks the feed. To get them at once, pull down on the show to refresh it.

The feed URL does not change. You add it to the app only one time. The app keeps your played status, because each episode keeps its ID from the original feed.

## The first import (`sync.py`)

`sync.py` made the first 40 episodes of the feed from a Spotify playlist.

**Warning:** do not run `sync.py` with `--repo`. It replaces all of `feed.xml` with the episodes from the playlist, and it removes the episodes that Muse added. Without `--repo`, it only writes a local file and does not change this repo.

How the script finds the episodes:

1. **It reads the playlist.** It gets the public Spotify embed page of the playlist. This page has the title, show name and length of each episode. The playlist must be public.
2. **It finds the RSS feed of each show.** It searches the iTunes Search API with the show name. It removes text such as `[Members Only]` or `| SiriusXM Podcasts+`, because these are paid copies of public shows.
3. **It matches each episode.** It compares the Spotify title with each title in the show's feed. It also counts the shared words, because some feeds put the words in a different order. An episode with almost the same length gets a higher score. If the best score is too low, the episode is `MISSING`. Spotify exclusives and paid-only episodes are not in public feeds, so they are always missing.
4. **It writes the feed.** Each episode keeps the audio link of the original podcast, so you get the full public episode. The show name is added after each title.

**Requirements:** Python 3 (no extra packages). If you get a `CERTIFICATE_VERIFY_FAILED` error, run `"/Applications/Python 3.12/Install Certificates.command"` (change the version number to your version).

## Troubleshooting

- **The app says it cannot add the URL.** Make sure that you used the `tilakp.github.io` URL. Open it in a browser. You must see XML. Run `curl -sI https://tilakp.github.io/commute-feed/feed.xml` and make sure that `content-type` is `application/xml`.
- **New episodes do not show.** Wait a few minutes, then refresh the show in the app. Apple Podcasts checks feeds less often than Overcast. If the episodes are still not there, look at the latest commits in this repo to see if the Muse job ran.

## Use only one app

You can follow the feed in Overcast and in Apple Podcasts at the same time. But your progress does not sync between the two apps. Use one app for your commute.
