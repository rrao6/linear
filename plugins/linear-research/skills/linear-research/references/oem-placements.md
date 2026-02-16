# OEM Placement Intelligence

> How linear/FAST content appears on smart TV platforms

## Why OEM Placement Matters

Amazon's Live tab drives 29% of Tubi's linear TVT. This single platform integration is the #1 linear discovery mechanism outside of Tubi's own homepage. Understanding and optimizing OEM placements is critical to linear growth.

## Platform-Specific Surfaces

### Amazon Fire TV
- **Live tab**: Dedicated tab on Fire TV remote. Aggregates linear channels from all apps.
  - Tubi channels appear here → drives 29% of linear TVT
  - Algorithm determines channel ordering and prominence
- **Channel guide**: Full EPG-style grid accessible from Live tab
- **Home screen rows**: "Live TV" and "What's On" containers
- **Voice**: "Alexa, show me live TV" surfaces channels

### Roku
- **Live TV tab**: Aggregated guide for Roku Channel + partner channels
- **Sports Hub**: New dedicated sports discovery surface (Tubi partnership planned for H1)
- **Home screen**: Featured content rows
- **Search**: Voice and text search can surface live channels
- **Channel Store**: App listing with linear features highlighted

### Samsung TV
- **Samsung TV Plus**: Deeply integrated, channel 1001+
- **Guide**: Universal guide includes Samsung TV Plus channels
- **Home screen**: Ambient/art mode can show content
- **Bixby**: Voice integration for channel discovery

### LG (webOS)
- **LG Channels**: Pre-loaded, accessible from guide button on remote
- **Home dashboard**: Content recommendations include linear
- **ThinQ**: Voice control for channel switching

### Vizio (SmartCast)
- **WatchFree+**: Built-in, accessible from dedicated button on some remotes
- **Home screen**: Content rows with linear recommendations
- **Guide**: Integrated programming guide

## Requirements for OEM Placement

### Common Requirements Across Platforms
1. **Metadata**: Channel name, logo, genre, description
2. **Images**: Logo (multiple sizes), key art, thumbnails
3. **Stream URLs**: HLS/DASH endpoints, DRM tokens
4. **EPG Data**: Schedule feed (XMLTV or API), updated every 1-4 hours
5. **Deep links**: URL scheme for launching directly to channel

### Image Spec Patterns
| Asset | Typical Ratio | Min Resolution | Format |
|---|---|---|---|
| Channel logo (horizontal) | 16:9 | 640x360 | PNG (transparent) |
| Channel logo (square) | 1:1 | 400x400 | PNG (transparent) |
| Program key art | 2:3 or 16:9 | 1280x720 | JPEG |
| Channel tile | 16:9 | 1920x1080 | JPEG |
| Banner/Hero | 16:9 | 1920x1080 | JPEG |

### Known Tubi Gaps for OEM Placement
- Missing program poster images for Fox channels
- Live content not consistently flagged as "live" (was 60% of channels)
- Inconsistent season/episode formatting
- Missing sports metadata (teams, league, sport)
- No deeplink attribution logging for many platforms

## H1 FY26 Partner Integration Plans

| Partner | Initiative | Status |
|---|---|---|
| Roku | Sports Hub integration | Planned (H1) |
| Amazon | Maintain Live tab presence | Ongoing |
| Others | TBD based on partner integrations plan | Evaluating |

## Research Questions

- [ ] What are the exact OEM requirements for each platform's guide integration?
- [ ] How does each platform rank/order channels in their guide?
- [ ] What is Tubi's current position in each OEM's guide?
- [ ] Which OEM surfaces drive the most incremental linear TVT?
- [ ] What metadata quality threshold is needed for each surface?
