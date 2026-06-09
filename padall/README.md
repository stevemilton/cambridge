# PadAll Club — Website Redesign

A modern, SEO-first redesign of [padallclub.com](https://www.padallclub.com/) by Cambridge AI Technologies.

**Preview:** once merged, the demo is served at `https://cambridgetech.ai/padall/` (it lives in this subdirectory so the main Cambridge site is untouched).

## What changed

### Modern design
- Distinctive brand system: deep court green + lime accent, Sora/Inter type pairing
- Bold hero with court-line motif, stat strip, and clear primary CTA ("Book a Court")
- Card-based sections for coaching, events and membership; scroll-reveal animations (respecting `prefers-reduced-motion`)
- Fully responsive with a mobile slide-down nav; sticky translucent header
- No frameworks or build step — one HTML, one CSS, one tiny JS file. Loads fast on any connection.

### Discoverability (SEO)
- Semantic HTML5 landmarks, single `h1`, logical heading hierarchy
- Descriptive `<title>` and meta description targeting "padel Haverhill / padel courts Suffolk / padel club Cambridge"
- **JSON-LD structured data**: `SportsActivityLocation` (address, phone, amenities, offers) and `FAQPage` — eligible for rich results in Google
- Open Graph + Twitter Card tags for social sharing
- Canonical URL, `robots.txt` and `sitemap.xml` (move both to the domain root on deploy)
- Visible FAQ section mirrors the structured data, capturing long-tail searches ("can I play padel in winter", "how do I book a padel court in Haverhill")
- Accessible by default (skip link, focus styles, ARIA on the nav) — accessibility signals also feed search ranking

## Before launch (TODOs for the client)
1. Replace the Playtomic links (`https://playtomic.com/`) with PadAll Haverhill's exact Playtomic club deep-link.
2. Confirm the postcode in the JSON-LD address (The New Croft is listed as Chalkstone Way; Playtomic lists Ehringshausen Way CB9 0ER).
3. Add real photography (hero + venue) and an `og-image.jpg` (1200×630) for social cards.
4. Add opening hours to the `SportsActivityLocation` schema once confirmed.
5. Set up a Google Business Profile and link it to the site for local search.
