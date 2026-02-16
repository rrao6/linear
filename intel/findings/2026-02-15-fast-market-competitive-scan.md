---
date: 2026-02-15
category: market
signals: [web-research-samsung, web-research-pluto, web-research-xumo, strategy-doc-baselines]
---

# FAST/Linear TV Competitive Market Scan

> Date: 2026-02-15
> Type: Finding (market scan)
> Confidence: Medium — mix of verified web data + strategy doc baselines + training knowledge
> Sources marked with (W) = verified via web fetch, (S) = strategy doc, (K) = training knowledge through mid-2025

## Channel Count Comparison (Updated)

| Service | Channels (Strategy Doc) | Current Verified | Source | Change |
|---|---|---|---|---|
| Amazon Fire TV Channels | ~700 | ~700+ | (K) Largest FAST library | Stable |
| Roku Channel | 549 | 400+ live | (K) Varies by source | Possible methodology diff |
| Samsung TV Plus | 549 | **300+ live** | (W) samsung.com/us/tvplus | **DOWN** from earlier reports — may count differently |
| Pluto TV | 441 | 250+ (extensive) | (W) pluto.tv/live-tv | Categories suggest 250-350+ |
| Tubi | 275 (~180 available) | ~275 | (S) Strategy doc | Stable |
| Xumo | ~300+ | **200+** | (W) play.xumo.com/channels, 26 categories | Confirmed |
| Vizio WatchFree+ | ~250+ | ~250+ | (K) Integrated into Vizio TVs | Stable |
| LG Channels | ~300+ | ~300+ | (K) Integrated into LG TVs | Stable |

**Key Insight**: Channel counts are heavily methodology-dependent. Samsung reports "300+" on their official site vs 549 cited in competitive studies. This may reflect active US-only channels vs global/inactive lineup. Same likely applies to others.

## Platform Integration Status

### Amazon Fire TV — MOST CRITICAL FOR TUBI
- **Integration level**: OS-level. Live tab on Fire TV remote provides one-click access to linear channels
- **Third-party integration**: YES — Tubi channels appear in Amazon's Live tab via deeplinks
- **Impact on Tubi**: Drives **31.5% of Tubi's linear TVT** (our Databricks data, 30d)
- **Competitive moat**: Amazon aggregates all FAST content into a unified guide, but Amazon's own channels get priority placement
- **Key risk**: Any Live tab algorithm change directly impacts Tubi linear

### Samsung TV Plus — DEEP OEM INTEGRATION
- **Integration level**: OS-level. Pre-installed on 200M+ Samsung smart TVs worldwide
- **Content**: 300+ live channels + 1000s of on-demand titles (W)
- **4K support**: Yes — Bloomberg and others available in 4K (W)
- **Compatible devices**: Smart TVs (2016+), Galaxy phones/tablets, web browsers (W)
- **No account required**: Frictionless — just turn on the TV (W)
- **Third-party integration**: NO — Samsung TV Plus is Samsung's own walled garden. Tubi is a separate app on Samsung
- **Key threat**: Zero-friction viewing means Samsung TV Plus captures passive linear viewers that might otherwise open Tubi

### Roku Channel
- **Integration level**: OS-level. Roku owns the platform + the FAST service
- **Sports Hub**: Launched as dedicated sports discovery surface — aggregates free sports from multiple sources
- **Third-party integration**: Limited — Roku Channel gets preferred placement on Roku home screen
- **Impact on Tubi**: Roku is #2 linear TVT platform (16.0%) but #1 for VOD. Gap shows Roku deprioritizes third-party linear
- **Key signal**: Sports Hub = Roku investing in live/linear sports discovery, directly competing with Tubi's sports strategy

### Xumo (Comcast/Charter)
- **Channels**: 200+ across 26 categories (W)
- **Integration**: Pre-loaded on Comcast Flex, Xfinity Stream, Charter Spectrum devices
- **Strategy**: Cable operator replacement play — targets cord-cutters within existing cable ecosystems
- **Notable**: Strong local news coverage across major US markets (W)
- **Third-party threat**: Low — Xumo primarily competes on cable distribution, not app stores

### Pluto TV (Paramount)
- **Content**: Extensive multi-genre lineup (W) with strong entertainment focus
- **Categories observed**: Movies (multiple sub-genres), Black Collective, Comedy, Classic TV, Sci-Fi, Drama, True Crime, Reality (W)
- **Integration**: App-based (like Tubi) — no OEM advantage
- **Competitive position**: Pioneer brand recognition, Paramount content library (CBS, MTV, Nickelodeon)
- **Tubi advantage**: Pluto lacks Tubi's Fox sports content and VOD cross-pollination

## Market Dynamics (Training Knowledge through mid-2025)

### FAST Market Size
- **2024 estimate**: $6-8B US ad revenue (multiple analyst estimates)
- **2027 forecast**: $12-15B US ad revenue
- **Growth driver**: CTV ad spending shift from traditional linear to FAST
- **Key trend**: Platform-integrated FAST services (Samsung, Roku, Amazon) growing faster than pure-app FAST (Pluto, Tubi)

### Nielsen Gauge Context
- As of mid-2025, streaming accounted for ~40%+ of total US TV viewing
- Tubi consistently appeared in Nielsen Gauge as a measurable player
- FAST/linear within streaming services is ~5-8% of streaming viewing, but growing
- Key metric: "Other Streaming" category in Nielsen Gauge includes most FAST services

### Sports on FAST — Emerging Battleground
- **Roku Sports Hub**: Dedicated sports discovery surface, aggregates free sports content
- **Amazon**: Thursday Night Football drives Fire TV engagement; free sports channels in Live tab
- **Tubi/Fox**: NFL Channel (3.94M unique viewers per our 30d data), Super Bowl simulcast, Fox Sports content
- **Pluto TV**: CBS Sports-branded channels from Paramount
- **Key trend**: Sports is the #1 driver of platform-level live TV engagement — whoever wins sports discovery wins linear

### Key Competitive Gaps for Tubi
1. **No platform integration**: Every top competitor except Pluto has some form of OEM/OS integration
2. **Channel count**: At 275 channels (~180 active), Tubi has fewest among top 6 competitors
3. **Amazon dependency**: 31.5% of linear TVT from one platform's deeplinks = fragile
4. **Sports depth**: NFL Channel is strong but brief-engagement (4.0 min avg session) — need deeper sports content

### Tubi Competitive Advantages
1. **Fox partnership**: Only FAST service with direct Fox Sports, NFL, World Cup, Liga MX
2. **VOD+Linear hybrid**: Linear+VOD users watch 2.4x more (35.2 hrs vs 14.5 hrs) — unique engagement model
3. **True Crime dominance**: ION, Dateline, ION Mystery, Forensic Files cluster = 30%+ of entertainment TVT
4. **Scale**: Top 5 FAST service by audience, strong brand recognition in AVOD

## So What — Implications for Tubi Linear Strategy

1. **OEM integration is the moat**: Samsung, Roku, Amazon all leverage OS-level integration. Tubi should pursue deeper platform partnerships (entry point #11 in strategy: Platform Partner Deeplinks)

2. **Sports is the next frontier**: Roku Sports Hub signals industry-wide investment in sports discovery. Tubi's Fox Sports content is an underutilized advantage — need better sports discovery surface

3. **Channel count matters less than curation**: Samsung reports 300+ but gets massive engagement from zero-friction access. Quality > quantity, but Tubi's 180 active channels may look thin vs marketed 400-700 counts

4. **Deeplink dependency is strategic risk**: Need to diversify entry points away from Amazon Live tab (31.5% dependency)

5. **True Crime is Tubi's content moat**: No other FAST service has the ION/Dateline/Forensic Files cluster performing this well. Protect and expand this advantage

## Research Gaps (Need Live Research)

- [ ] Exact current channel counts (verified from each platform's site)
- [ ] Roku Sports Hub specific content and partner list
- [ ] Amazon Live tab algorithm changes in 2025-2026
- [ ] Samsung TV Plus expansion into new Samsung models/international
- [ ] Nielsen Gauge latest data (Q4 2025 / Q1 2026)
- [ ] Ad fill rates and CPMs by competitor
- [ ] Pluto TV strategy post-Paramount merger/restructuring
