# Colors — Premium Color Palettes

> **Module:** Design System  
> **Read Time:** 3 minutes  
> **When:** Phase 1 — Design Planning

---

## 🎯 CORE RULE

**You MUST pick ONE palette from Section 1 below for every UI task.**  
Never use the same palette twice in a row. Rotate through them.

**NEVER use AI defaults:**
- ❌ Cream (#F4F1EA) + Terracotta
- ❌ Near-black (#0a0a0a) + Acid green (#00ff00)
- ❌ Blue-purple gradient on everything

---

## 1. PALETTE CATALOG

### Palette A — Apple Premium (Minimalist Luxury)
```
Background:     #FFFFFF (white), #F5F5F7 (light gray)
Text Primary:   #1D1D1F (near-black)
Text Secondary: #6E6E73 (medium gray)
Accent:         #0071E3 (Apple blue)
Border:         #D2D2D7 (light gray)
Success:        #30D158
Error:          #FF453A
Warning:        #FFD60A
```
**Best for:** Premium product pages, hardware showcases, minimalist landing pages  
**Mood:** Clean, expensive, restrained

### Palette B — Stripe (Elegant Purple)
```
Background:     #FFFFFF, #F6F9FC (ice blue)
Text Primary:   #1A1A2E (deep navy)
Text Secondary: #6B7C93 (steel blue)
Accent:         #635BFF (Stripe purple)
Secondary:      #00D4AA (teal)
Border:         #E6EBF1 (light blue-gray)
Danger:         #EF4444
```
**Best for:** SaaS dashboards, payment pages, B2B tools  
**Mood:** Trustworthy, professional, modern

### Palette C — Linear (Ultra-Minimal Dark)
```
Background:     #17171A (dark surface), #0D0D0F (darker)
Text Primary:   #FFFFFF
Text Secondary: #8A8F99 (gray)
Accent:         #5E6AD2 (Linear purple)
Border:         #2A2A2E (subtle)
Success:        #00E599
Danger:         #FF5C5C
```
**Best for:** Dev tools, project management, dark-mode dashboards  
**Mood:** Precise, focused, premium dark

### Palette D — Gucci (Luxury Fashion)
```
Background:     #F5F0EB (warm ivory), #FFFFFF
Text Primary:   #1A1A1A
Text Secondary: #6B6258 (warm brown-gray)
Accent:         #006039 (Gucci green)
Secondary:      #B4975A (gold)
Tertiary:       #8B0000 (deep red)
Border:         #E0D8CE (warm beige)
```
**Best for:** Fashion, luxury brands, premium lifestyle  
**Mood:** Opulent, heritage, sophisticated

### Palette E — Dior (Haute Couture)
```
Background:     #FFFFFF, #F8F5F0 (champagne white)
Text Primary:   #1C1C1E (off-black)
Text Secondary: #8E8E93 (warm gray)
Accent:         #A67C52 (Dior gold)
Secondary:      #1A1A2E (midnight blue)
Border:         #E5DDD3 (champagne border)
Danger:         #C41E3A (Dior red)
```
**Best for:** High-end fashion, cosmetics, luxury retail  
**Mood:** Elegant, refined, timeless

### Palette F — Vercel (Monochrome Precision)
```
Background:     #000000, #111111
Text Primary:   #EDEDEF
Text Secondary: #666666
Accent:         #FFFFFF (white-on-dark)
Border:         #222222
Success:        #5EFF5E
Code:           Geist Mono
```
**Best for:** Developer tools, deployment platforms, tech showcases  
**Mood:** Brutalist, minimal, high-contrast

### Palette G — Spotify (Expressive Dark)
```
Background:     #121212, #181818
Text Primary:   #FFFFFF
Text Secondary: #B3B3B3
Accent:         #1DB954 (Spotify green)
Secondary:      #E13300 (orange)
Highlight:      #1E3264 (deep blue)
Border:         #282828
```
**Best for:** Media, entertainment, music, creative portfolios  
**Mood:** Energetic, dark, vibrant

### Palette H — Shopify (Cinematic Dark)
```
Background:     #00282B, #003A3D (deep teal)
Text Primary:   #FFFFFF
Text Secondary: #B8D4D6 (light teal)
Accent:         #95BF47 (Shopify lime)
Secondary:      #F9F871 (yellow)
Border:         #1A4D50
```
**Best for:** E-commerce, startup landing pages, bold marketing  
**Mood:** Bold, fresh, confident

### Palette I — Figma (Playful Creative)
```
Background:     #FFFFFF, #F0F0F0
Text Primary:   #2C2C2C
Text Secondary: #7B7B7B
Accent:         #A259FF (Figma purple)
Secondary:      #1ABCFE (cyan)
Tertiary:       #FF7262 (Figma orange)
Border:         #E1E1E1
Success:        #00C853
```
**Best for:** Creative tools, design portfolios, collaborative platforms  
**Mood:** Playful, creative, colorful

### Palette J — Warp (Terminal Modern)
```
Background:     #1A1A2E, #16213E
Text Primary:   #E0E0E0
Text Secondary: #8A8F99
Accent:         #FF6B6B (coral)
Secondary:      #4ECDC4 (teal)
Border:         #2A2A4A
Code:           #FFD93D (yellow for syntax)
```
**Best for:** Developer tools, terminal apps, code editors  
**Mood:** Modern, tech-forward, vibrant dark

### Palette K — Tesla (Radical Subtraction)
```
Background:     #FFFFFF, #F5F5F5
Text Primary:   #171A20 (dark gray)
Text Secondary: #8E8E93
Accent:         #E82127 (Tesla red)
Border:         #E5E5E5
Image-dominant: true (hero = full-bleed photo)
```
**Best for:** Automotive, product showcases, minimalist hero pages  
**Mood:** Cinematic, bold, subtractive

### Palette L — Airbnb (Warm Hospitality)
```
Background:     #FFFFFF, #F7F7F7
Text Primary:   #222222
Text Secondary: #717171
Accent:         #FF385C (Airbnb pink/red)
Border:         #DDDDDD
Success:        #008A05
Danger:         #C13515
```
**Best for:** Travel, hospitality, marketplace, community platforms  
**Mood:** Warm, inviting, trustworthy

---

## 2. SEMANTIC COLOR TOKENS

Map your chosen palette to these semantic tokens:

```css
--bg-primary:      /* Main page background */
--bg-secondary:    /* Cards, sections */
--bg-elevated:     /* Modals, dropdowns */
--text-primary:    /* Headings, body */
--text-secondary:  /* Descriptions */
--text-muted:      /* Captions, metadata */
--accent:          /* CTAs, links, highlights */
--accent-hover:    /* Darker/lighter variant */
--accent-muted:    /* Subtle accent bg (rgba) */
--border:          /* Card borders, dividers */
--border-subtle:   /* Very light borders */
--success:         /* Success states */
--error:           /* Error states */
--warning:         /* Warning states */
```

**Example mapping (Palette B — Stripe):**
```css
:root {
  --bg-primary: #FFFFFF;
  --bg-secondary: #F6F9FC;
  --bg-elevated: #FFFFFF;
  --text-primary: #1A1A2E;
  --text-secondary: #6B7C93;
  --text-muted: #8899A6;
  --accent: #635BFF;
  --accent-hover: #4F46E5;
  --accent-muted: rgba(99, 91, 255, 0.08);
  --border: #E6EBF1;
  --border-subtle: #F0F4F8;
  --success: #00D4AA;
  --error: #EF4444;
  --warning: #F59E0B;
}
```

---

## 3. COLOR USAGE RULES

| Rule | Description |
|------|-------------|
| **90/10 rule** | 90% neutral tones, ≤10% accent color |
| **One accent** | Use exactly ONE accent color per page |
| **No raw colors** | Never use `bg-blue-500`. Always map to semantic tokens |
| **Dark mode** | All palettes MUST have a dark variant |
| **Gradient limit** | Gradients only on hero or feature highlights, never on body |
| **Contrast** | Text on bg must pass WCAG AA (4.5:1 ratio) |

---

## 4. ROTATION RULE

```
Task 1 → Palette A (Apple)
Task 2 → Palette E (Dior)
Task 3 → Palette C (Linear)
Task 4 → Palette H (Shopify)
Task 5 → Palette G (Spotify)
Task 6 → Palette B (Stripe)
Task 7 → Palette K (Tesla)
Task 8 → Palette D (Gucci)
...then repeat with different pairings
```

**Never use the same palette twice in a row.**
**Never use an AI default palette (cream/terracotta, black/acid-green).**

---

**Next:** `design/typography.md` — Font pairings & hierarchy
