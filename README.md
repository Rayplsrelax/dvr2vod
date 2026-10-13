# DVR2VOD

**Publish completed Dispatcharr DVR recordings as a VOD-style M3U playlist**, so
they play in TiviMate, OTT Navigator, VLC — anywhere an M3U works — instead of
being reachable only through Dispatcharr's web UI. This implements the
long-standing feature request
[Dispatcharr#799](https://github.com/Dispatcharr/Dispatcharr/issues/799)
without modifying Dispatcharr's core.

```
completed recordings ──▶ dvr2vod_data/recordings.m3u
each entry ──▶ {base_url}/api/channels/recordings/{id}/file/?token=…
```

The playlist links to Dispatcharr's own recording file endpoint (which supports
Range/seeking), so nothing is copied or moved: no extra disk usage, and deleting
a recording in Dispatcharr removes it from the playlist on the next rebuild.

## Features

- **Grouped per show** (default): recordings are split into show groups using
  `SxxExy` markers, date stamps (`2026-10-12`), or `Show - Episode` separators.
- **Flat mode**: every recording in one group ("DVR Recordings").
- **Auto rebuild**: regenerates the playlist whenever a recording finishes
  (`recording_end` event), plus manual Preview / Generate buttons.
- **Token-safe**: the access token is interpolated into entry URLs only and is
  never written to logs.
- **Update-safe state**: the playlist is written to a sibling data folder that
  survives plugin updates.

## Install

1. Download the latest `dvr2vod.zip` from
   [Releases](../../releases) (or the Dispatcharr plugin browser, once
   listed in the registry).
2. Install it in Dispatcharr: **Settings → Plugins → Install**.
3. Configure:
   - **Dispatcharr base URL** — an address your *client device* can reach
     (LAN IP/hostname, never `localhost`).
   - **Access token** — Dispatcharr's recording file endpoint requires
     authentication (JWT, API key, or `?token=`). Put the token value here.
4. Click **Generate playlist**, then point your player at
   `<data folder>/recordings.m3u` (or serve it over any static mount).

## How it works

| Piece | Detail |
|---|---|
| Source of truth | Dispatcharr `Recording` rows with `status="completed"` |
| Playback | `GET /api/channels/recordings/{id}/file/?token=…` (Range/seek supported) |
| Artwork | Channel logo is written as `tvg-logo` per entry |
| Ordering | Newest first; entries without timestamps sink to the end |
| Rebuild triggers | `recording_end` event (background thread) or the Generate button |

The heavy lifting (title → show/episode parsing, grouping, M3U rendering) is
pure Python with no Django imports, unit-tested in `tests/`. The Django-facing
glue in `dvr2vod/plugin.py` follows the same threading contract as clapparr:
the `recording_end` handler never blocks the recording task, and any thread
that touches the ORM calls `close_old_connections()` in its `finally`.

## Limitations

- Xtream-series metadata (per-series posters/episode images in TiviMate's
  series section) is not provided — the M3U presents shows as groups. True
  Xtream VOD/series API injection would require core changes (see #799).
- The `?token=` value is visible to anyone who can fetch the playlist file —
  keep the output path private to your LAN.

## Development

```bash
python -m unittest discover -s tests   # no Dispatcharr needed
python tools/build_release_zip.py      # -> dist/dvr2vod-<version>.zip
```

## License

MIT — see [LICENSE](LICENSE).
