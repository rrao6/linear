# Competitive Intelligence Scan Summary — 2026-02-15

> Date: 2026-02-15
> Query: Full CI pipeline scan with --skip-memory (orchestrator run 20260215_173726)
> Status: COMPLETED (classification skipped — no OPENAI_API_KEY)

## Key Findings

- **141 articles collected** from 41 RSS feeds across 11 competitor categories
- **Tubi led press coverage** with 23 articles, followed by Peacock (20), Roku (12), Fubo (12)
- **Roku posted $80.5M Q4 profit** — validates FAST model profitability, 145.6B streaming hours
- **Tubi acquiring Cartoon Network content** starting March 1st — major content play for younger demographics
- **YouTube TV launching cheaper bundles** including standalone sports package — threat to price-sensitive cord-cutters
- **Samsung TV Plus reached 100M users** globally — OEM scale advantage growing
- **Xumo confirmed at 411 channels** (21% more than Tubi's ~340) across 26 niche categories
- **World Baseball Classic on Tubi** — Fox partnership delivering sports content to Tubi linear
- **Peacock dominating live sports** — NBA All-Star, Winter Olympics 2026 coverage (20 articles)
- **Fubo-Disney merger synergy** materializing with expanded reach for Fubo Sports Network

## Article Distribution by Competitor

| Competitor | Articles | Key Themes |
|---|---|---|
| Tubi | 23 | Content additions (Cartoon Network, classic movies), WBC, Valentine's |
| Peacock | 20 | NBA All-Star, Winter Olympics 2026, live sports |
| Roku Channel | 12 | Q4 earnings, new free channels, revenue growth |
| Fubo | 12 | Disney synergy, sports coverage, pricing comparisons |
| Samsung TV Plus | 6 | 100M users milestone, volleyball partnership |
| Hulu Live | 6 | Daytona 500, Dark Winds, live TV comparisons |
| YouTube TV | 6 | Cheaper bundles, sports plan, pricing breakdowns |
| Amazon Fire TV | 5 | FA Cup streaming, device channel listings |
| Industry | 49 | Fox Speed Channel return, Roku revenue, streaming ratings |
| Plex | 1 | Free streaming roundup |
| Vizio WatchFree | 1 | Walmart/Roku retail partnership post-acquisition |

## Channel Count Snapshot

| Service | Count | Method | Verified |
|---|---|---|---|
| Xumo | 411 | Slug count from page JSON | Yes |
| Tubi | ~340 | User-confirmed (dynamic rendering required) | Partial |
| Pluto TV | ~378 | Last confirmed via Playwright (dynamic JS) | Stale |
| Samsung TV Plus | 300+ | Marketing copy | No |
| Vizio WatchFree+ | 300+ | Marketing copy | No |

## Learnings Pushed to Hub

8 learnings pushed to `localhost:8888/api/strategy/learnings` (IDs 14-21):

1. **Roku Q4 2025 profit turnaround** — $80.5M profit, 145.6B streaming hours
2. **Tubi Cartoon Network acquisition** — March 1st launch, animation content play
3. **YouTube TV cheaper bundles** — standalone sports package, pricing threat
4. **Samsung TV Plus 100M users** — global scale milestone
5. **Channel count snapshot** — Xumo 411, Samsung 300+, Vizio 300+, Tubi ~340
6. **Fubo-Disney merger synergy** — expanded sports network reach
7. **World Baseball Classic on Tubi** — Fox/FS1/Tubi broadcast schedule
8. **Peacock live sports dominance** — 20 articles, NBA/Olympics coverage

## Pipeline Notes

- Classification phase skipped (OPENAI_API_KEY not set) — articles collected but not scored
- Analysis phase skipped (no classified intel to analyze)
- Memory phase skipped (--skip-memory flag)
- Synthesis phase skipped (no classified data)
- Channel scraping: Pluto and Tubi require dynamic rendering (Playwright) for accurate counts

## Methodology

- **Tool**: `python3 tools/scanner/orchestrator.py --skip-memory`
- **Sources**: 41 RSS feeds (Google News, press releases, trade publications)
- **Channel scraping**: Static HTML parsing of competitor channel pages
- **Date range**: Default lookback (72 hours)

## Follow-up

- Re-run with OPENAI_API_KEY for full classification and analysis
- Investigate YouTube TV sports bundle pricing impact on Tubi linear sports viewership
- Track Tubi Cartoon Network content launch metrics post-March 1st
- Monitor Roku Channel expansion — 9 new channels added, Pokémon among them
- Verify Pluto TV channel count with Playwright browser automation
