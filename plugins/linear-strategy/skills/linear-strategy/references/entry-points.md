# Linear Entry Points Initiative

> From: Linear Entry Points doc | Author: Mariel Young | Status: Draft | Updated: Jan 12, 2026

## Goal

Audit, document, and improve existing logging to understand how users access Linear content. Enable success measurement for tests that unlock or expand visibility of linear content.

## Why This Matters

By understanding how users currently access linear, we can:
1. Assess opportunities to improve visibility (increase Linear TVT)
2. Identify which pathways are working well
3. Measure how product/feature changes impact pathways to Linear

## Key Questions to Answer

1. **How do users discover Linear content?**
   - For all users with linear TVT, what % came through each pathway?

2. **How do discovery paths differ by:**
   - Platform / Platform type
   - Country
   - Viewer age
   - Registered/unregistered
   - User tenure
   - Linear user segment (genre preference)

3. **How often is Linear the first view?**
   - What % of video sessions start with Linear content?

4. **How do discovery paths vary over time?**
   - Spikiness from CRM, tentpole events, platform changes

5. **Incremental lift by pathway?**
   - What is each pathway's incremental contribution?

6. **Pathway visibility?**
   - How many users see each discovery pathway?
   - Which pathways are evergreen vs conditional?

7. **Conversion rate by pathway?**
   - For users who see a linear tile in Featured, what % click?

8. **Missing pathways?**
   - What should be added? Potential opportunity?

## Identified Entry Points (April 2025)

1. Main nav "Live TV"
2. Linear containers (On Now, Sports/News/Entertainment on now)
3. Linear tile in Featured (when channel is pinned)
4. Deep link handling (device UIs to channel)
5. CRM
6. Web search deep links
7. Tubi web pages (live channels page, schedule page)
8. Search
9. My Stuff (favorite channels, platform-dependent)
10. Braze panel (Roku only, 2nd session education)
11. [Coming Soon] Linear Detail Pages (mobile first)

## Current Attribution (Sept 2024)

| Source | TVT Share |
|---|---|
| Homepage | 38.6% |
| Deeplink | 28.0% |
| Linear Browse/EPG | 15.9% |
| Other | 15.5% |
| Search | 2.0% |

## Known Gaps

- Missing attribution logging for deeplinks (ticket: TDATAINFRA-669)
- Need to identify % of sessions with missing attributions
- Need DE/DI resources to implement missing events

## Methodology

1. Identify top platforms to focus on
2. Identify top entry pathways
3. Map video sessions back to attributed pathway
4. Identify % with missing attributions
5. Work with DE/DI to fix missing events
6. Identify other attribution methods

## Data Resources

- Surface Metrics Dashboard
- Tubi Surface Metric Glossary
- Video session attribution (Slack thread reference)
- Deeplink attribution for linear content (Shortcut story 801831)
