# Styles — 12 Design Styles & Rotation System

> **Module:** Design System  
> **Read Time:** 5 minutes  
> **When:** Phase 1 — Pick ONE style per project

---

## 🎯 CORE RULE

**Pick exactly ONE style per project. Never mix styles.**  
Rotate through styles — never use the same style twice in a row.

---

## STYLE CATALOG

### Style 1 — Apple Minimalism
```
Colors:      White, light gray, Apple blue (#0071E3)
Typography:  SF Pro / Helvetica Neue — weight 300-600
Corners:     rounded-2xl (16px) cards, rounded-full pills
Shadows:     None or very subtle (0 1px 3px rgba(0,0,0,0.08))
Borders:     1px solid #D2D2D7
Whitespace:  50%+ of page area
Signature:   Floating hero image with shadow, staggered text reveal
Animation:   200ms ease-out, opacity + translateY only
Best for:    Premium product, hardware, minimalist brand
```

### Style 2 — Stripe Purple (Elegant SaaS)
```
Colors:      White, ice blue #F6F9FC, purple #635BFF, teal #00D4AA
Typography:  Inter — weight 300-700
Corners:     rounded-lg (8px) buttons, rounded-xl (12px) cards
Shadows:     Light (0 4px 12px rgba(99,91,255,0.15))
Borders:     1px solid #E6EBF1
Signature:   Gradient hero, floating purple glow, smooth card hover
Animation:   200ms ease-out, subtle lift on hover
Best for:    SaaS, fintech, B2B, payment pages
```

### Style 3 — Linear Dark (Ultra-Minimal)
```
Colors:      #17171A, #0D0D0F, purple #5E6AD2
Typography:  Inter — weight 400-700
Corners:     rounded-lg (8px)
Shadows:     Only on hover (0 8px 24px rgba(94,106,210,0.25))
Borders:     Subtle 1px #2A2A2E
Signature:   Clean dark surfaces, purple accent only on CTAs, precise spacing
Animation:   <200ms, only opacity and color changes
Best for:    Dev tools, project management, dark-mode apps
```

### Style 4 — Gucci Luxury (Fashion Heritage)
```
Colors:      Ivory #F5F0EB, green #006039, gold #B4975A
Typography:  Playfair Display (headings) + Inter (body)
Corners:     sharp (rounded-none) for premium feel
Shadows:     None
Borders:     Double borders or thick borders (2px)
Signature:   Monogram patterns, gold accents, serif headings, asymmetrical layout
Animation:   300ms ease-out, slow and deliberate
Best for:    Fashion, luxury, premium lifestyle
```

### Style 5 — Dior Couture (Refined Elegance)
```
Colors:      White, champagne #F8F5F0, gold #A67C52, midnight blue #1A1A2E
Typography:  Cormorant Garamond (headings) + Inter (body)
Corners:     Slightly rounded (rounded-md = 6px)
Shadows:     Ultra-light, warm-toned
Borders:     1px #E5DDD3
Signature:   Gold accent lines, thin dividers, generous whitespace, centered hero
Animation:   400ms ease-out, fade transitions
Best for:    Cosmetics, high-end retail, luxury brand landing
```

### Style 6 — Vercel Brutalist
```
Colors:      Black #000, white #FFF, gray #666
Typography:  Geist / Inter — weight 400-700
Corners:     None (rounded-none)
Shadows:     None
Borders:     Thick borders (2px solid)
Signature:   Raw typography, monochrome, no decorative elements, content-first
Animation:   None or instant (0ms)
Best for:    Dev portfolios, documentation, tech showcases
```

### Style 7 — Spotify Dark (Expressive Media)
```
Colors:      #121212, white, green #1DB954, orange #E13300
Typography:  Inter — weight 400-900 (heavy weights encouraged)
Corners:     rounded-full for pills, rounded-xl for cards
Shadows:     Colored glows (0 0 20px rgba(29,185,84,0.3))
Borders:     None or very subtle
Signature:   Duotone images, gradient overlays, bold typography, card carousels
Animation:   300ms ease, scale on hover, smooth slide
Best for:    Media, music, entertainment, creative portfolio
```

### Style 8 — Shopify Bold (Cinematic Marketing)
```
Colors:      Deep teal #00282B, white, lime #95BF47
Typography:  Inter Bold (headings) + Inter Regular (body)
Corners:     rounded-2xl (16px)
Shadows:     Large, colored (0 20px 60px rgba(0,40,43,0.4))
Borders:     2px solid contrasting color
Signature:   Full-bleed dark hero, overlaid text, bold CTAs, scroll-triggered reveals
Animation:   500ms ease-out, dramatic entrances
Best for:    E-commerce, startup landing, marketing pages
```

### Style 9 — Figma Playful (Creative Colorful)
```
Colors:      White, purple #A259FF, cyan #1ABCFE, orange #FF7262
Typography:  Plus Jakarta Sans (headings) + Inter (body)
Corners:     rounded-3xl (24px) — extra round
Shadows:     Multiple colored shadows
Borders:     2px colorful borders
Signature:   Multi-color gradients, playful illustrations, overlapping elements
Animation:   300ms bounce, spring effects
Best for:    Creative tools, design studios, education
```

### Style 10 — Tesla Cinematic
```
Colors:      White #FFF, dark gray #171A20, red #E82127
Typography:  Inter / Helvetica — weight 400-700
Corners:     rounded-xl (12px)
Shadows:     Large, soft (0 20px 60px rgba(0,0,0,0.15))
Borders:     1px #E5E5E5
Signature:   Full-bleed hero image, minimal UI overlay, cinematic typography
Animation:   400ms ease, parallax scroll
Best for:    Automotive, product showcase, cinematic landing
```

### Style 11 — Airbnb Warm (Community)
```
Colors:      White, warm gray #F7F7F7, pink-red #FF385C
Typography:  Inter (all) — weight 400-700
Corners:     rounded-xl (12px)
Shadows:     Soft (0 6px 16px rgba(0,0,0,0.08))
Borders:     1px #DDDDDD
Signature:   Rounded search bar, card grid with images, sticky footer
Animation:   200ms ease, subtle lift
Best for:    Travel, marketplace, community, hospitality
```

### Style 12 — Terminal Dev (Cyber Modern)
```
Colors:      #1A1A2E, coral #FF6B6B, teal #4ECDC4
Typography:  Inter / JetBrains Mono (code-heavy)
Corners:     rounded-md (6px)
Shadows:     Neon glows (0 0 15px rgba(255,107,107,0.3))
Borders:     1px #2A2A4A
Signature:   Code syntax highlighting, terminal-style UI, ASCII decorations
Animation:   200ms, blink cursors, typing animation
Best for:    Dev tools, CLI apps, coding portfolios
```

---

## STYLE ROTATION SYSTEM

### Mandatory Rotation

```
Task #  → Required Style
─────────────────────────
  1    → Apple Minimalism (or random pick)
  2    → MUST be different from #1
  3    → MUST be different from #1, #2
  4    → MUST be different from all prior
  5+   → Never repeat a style unless all 12 exhausted
```

### How To Pick

1. Check the last 3 styles used (stored in memory/project state)
2. Exclude those 3 from selection
3. Randomly pick from remaining 9 styles
4. If no history exists, randomly pick any of the 12

### Example Rotation
```
Project 1:  Stripe Purple (Style 2)
Project 2:  Gucci Luxury (Style 4)
Project 3:  Linear Dark (Style 3)
Project 4:  Tesla Cinematic (Style 10)
Project 5:  Spotify Dark (Style 7)
Project 6:  Dior Couture (Style 5)
Project 7:  Figma Playful (Style 9)
Project 8:  Apple Minimalism (Style 1)
Project 9:  Shopify Bold (Style 8)
Project 10: Vercel Brutalist (Style 6)
Project 11: Airbnb Warm (Style 11)
Project 12: Terminal Dev (Style 12)
```

---

## FORBIDDEN

- ❌ Cream (#F4F1EA) + Terracotta
- ❌ Near-black + Acid green
- ❌ Blue-to-purple gradient on everything
- ❌ Glassmorphism for every card
- ❌ Same style used twice in a row

---

**Next:** `components/patterns.md` — Component selection guide
