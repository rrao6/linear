---
date: 2026-02-15
category: oem
signals: [training-knowledge, strategy-doc]
confidence: Medium — training data through mid-2025
---

# OEM Platform Integration for FAST/Linear TV

## Cross-Platform Summary

| Platform | FAST Service | Channels | OS-Level Guide | 3P FAST in Guide | Default Power-On | Remote Button |
|---|---|---|---|---|---|---|
| **Fire TV** | Fire TV Channels | 500+ | Live Tab | Partial (API) | No (promoted) | Ch +/- some |
| **Roku** | Roku Channel | 350+ | Live TV tile | No (siloed) | No | No |
| **Samsung** | Samsung TV Plus | 300+ | Guide button | No (siloed) | **YES** | Guide button |
| **LG** | LG Channels (Xumo) | 300+ | Dashboard | No (siloed) | No | Ch +/- |
| **Vizio** | WatchFree+ | 300+ | SmartCast | No (siloed) | Partial | **Dedicated** |
| **Google TV** | Free Channels | 150+ | Live Tab | **Most open** | No | No |
| **Apple TV** | None | N/A | Sports/Watch | No | No | No |

## Critical Findings for Tubi

### 1. Third-Party FAST Apps Are Siloed Everywhere Except Fire TV and Google TV
- Samsung, LG, Vizio, Roku: Tubi channels stay inside Tubi app
- Fire TV: Partial integration via Live TV Integration API — Tubi channels CAN appear in Live tab
- Google TV: Most open model — best partner opportunity for OS-level discovery
- **This is why Amazon drives 31.5% of Tubi linear TVT** — it's the only platform where Tubi linear content escapes the app silo

### 2. Samsung's Power-On Default Is the Most Aggressive Discovery
- TV Plus auto-launches when TV powers on = massive passive reach
- No account required, 200M+ devices globally
- Tubi can't compete at this layer — pure app play

### 3. Google TV = Best Partnership Opportunity
- Most open integration model for third-party linear
- 150+ built-in free channels + aggregation framework
- "Freeplay" section for free content discovery
- AI-powered recommendations (Gemini) surface relevant live content
- **Tubi should pursue Google TV Live tab integration as priority entry point**

### 4. Walmart/Vizio = Wild Card
- Walmart acquired Vizio for $2.3B (early 2024)
- Shoppable TV + retail media integration coming
- WatchFree+ may be reshaped for commerce
- Dedicated remote button = zero-friction access

### 5. Sports Hubs Are Universal
- Roku Sports Hub, Amazon Sports row, Apple Sports tab, Google TV sports
- Every platform investing in sports as live content driver
- Tubi's Fox Sports pipeline = advantage if surfaced through platform hubs

## Platform-Specific Details

### Amazon Fire TV
- Live tab aggregates Fire TV Channels + third-party via API
- Amazon's own channels get priority (top positions, home screen, screensaver)
- Freevee brand discontinued → folded into Fire TV Channels
- "Continue Watching Live" widget resurfaces recently viewed channels
- **Tubi linear channels primarily accessed within Tubi app** — not deeply integrated into Live tab grid
- Some Fire TV remotes have channel +/- buttons for Live tab favorites

### Roku
- Roku Channel = 350+ linear FAST channels
- Live TV tile on home screen shows Roku Channel + OTA antenna only
- **Deliberate walled garden** — Roku takes 50% ad inventory share, keeps linear in-house
- "Roku City" screensavers transition into Roku Channel content
- Sports Hub aggregates across apps (discovery layer, not video)

### Samsung TV Plus
- 300+ channels verified (samsung.com Feb 2026)
- Default power-on input on many Samsung TV models
- Guide button on remote → traditional EPG grid
- No account needed — frictionless
- "Universal Guide" recommends across installed apps but not a unified linear guide
- 4K channels available (Bloomberg, others)

### LG Channels
- 300+ channels, powered by Xumo backend
- webOS launcher bar + "Live TV" section
- "Quick Channels" feature (2024+) — flip through LG Channels from anywhere via ch +/-
- Not auto-launch on power-on (one tap from home)

### Vizio WatchFree+
- 300+ channels on SmartCast
- **Dedicated WatchFree+ button on remote** — zero-friction
- Home screen banner promotion on power-on
- Walmart acquisition = shoppable TV integration incoming

### Google TV
- 150+ built-in free channels, "Freeplay" section
- Live tab aggregates from YouTube TV, Sling, Philo, and FAST services
- **Most open third-party integration** — content aggregation framework
- AI recommendations (Gemini) surface live content
- Runs on Chromecast, Sony, TCL, Hisense TVs

### Apple TV
- No FAST service — premium/subscription only
- Sports tab aggregates across services (MLS, MLB, etc.)
- ~2% of US streaming devices — limited relevance for FAST
- Multiview for simultaneous sports streams

## Implications for Tubi H1 FY26 Strategy

1. **Entry Point #11 (Platform Partner Deeplinks)** is critical — platform-level integration drives discovery
2. **Prioritize Google TV integration** — most open model, growing device base
3. **Protect Amazon Fire TV relationship** — 31.5% dependency, any algorithm change = risk
4. **Roku Sports Hub** — get Tubi sports content surfaced there (planned in H1)
5. **Accept Samsung/LG/Vizio are walled gardens** — focus on in-app discovery for these platforms
6. **Channel count narrative** — competitors market 300-500+ channels at OS level; Tubi's 180 active channels need strong curation story
