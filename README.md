# Guggenheim 2026 World Cup Sweepstake — Deployment

The site is a single static page (`index.html`) that reads scores from
`results.json` sitting next to it. Host both and you're live.

## Go live (5 minutes)

1. Create a new **public** GitHub repository, e.g. `wc26-sweepstake`.
2. Upload everything in this folder (keep the folder structure, including
   the hidden `.github` folder if you want automation).
3. Repo **Settings → Pages → Source: Deploy from a branch → main / (root) → Save**.
4. Wait ~1 minute. Your link is:
   `https://<your-username>.github.io/wc26-sweepstake/`
5. Share that link. It opens in everyone's real browser — bouncing ball and all.

## Updating scores

**Manual (zero setup):** edit `results.json` in the GitHub web UI each evening.
Per nation: `gw` = group-stage wins, `stage` = furthest round reached
(`group` → `r32` → `r16` → `qf` → `sf` → then `fourth` / `third` / `runnerup` / `champion`).
Update `lastUpdated` while you're there. Commit — the site refreshes for everyone.

**Automated (10 extra minutes):**
1. Get a free API key at https://www.football-data.org/client/register
   (free tier includes the World Cup).
2. Repo **Settings → Secrets and variables → Actions → New repository secret**:
   name `FOOTBALL_DATA_API_KEY`, value = your key.
3. Done. The workflow in `.github/workflows/update-results.yml` runs twice
   daily (04:30 and 07:00 UTC) and commits fresh scores. You can also trigger
   it any time from the **Actions** tab → "Update World Cup results" → Run workflow.

The updater refuses to write if the feed contains a team name it can't map,
so a feed quirk can never corrupt the leaderboard — it'll just fail loudly in
the Actions log and you can add the alias to `scripts/update_results.py`.

## Entering the draft

When teams are allocated, edit the `PAIRS` array near the bottom of
`index.html` (the format is shown in a comment) — or send the names and picks
back to Claude to do it for you.
