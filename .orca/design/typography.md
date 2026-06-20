# Typography — Font Hierarchy & Pairing System

> **Module:** Design System  
> **Read Time:** 3 minutes  
> **When:** Phase 1 — Design Planning

---

## 🎯 CORE RULE

**Fonts are the #1 carrier of a brand's personality.**  
Every project MUST use a deliberate font pairing — never default to "Inter everywhere."

---

## 1. FONT PAIRING CATALOG

### Pairing 1 — Classic Editorial
```
Heading:    Playfair Display (serif) — w600-700
Body:       Inter (sans-serif) — w400
Code:       JetBrains Mono
Use when:   Luxury, editorial, fashion, magazine, law
Vibe:       Sophisticated, timeless
```

### Pairing 2 — Modern Tech
```
Heading:    Inter (sans-serif) — w600-700
Body:       Inter (sans-serif) — w400
Code:       JetBrains Mono
Use when:   SaaS, dashboard, dev tools, corporate
Vibe:       Clean, professional, precise
```

### Pairing 3 — Creative Bold
```
Heading:    Space Grotesk (sans) — w500-700
Body:       Inter (sans-serif) — w400
Code:       Fira Code
Use when:   Creative agency, portfolio, startup landing
Vibe:       Bold, modern, distinctive
```

### Pairing 4 — Elegant Fashion
```
Heading:    Cormorant Garamond (serif) — w500-700
Body:       Inter or Söhne (sans) — w300-400
Code:       JetBrains Mono
Use when:   Fashion, beauty, luxury retail, cosmetics
Vibe:       Elegant, refined, haute couture
```

### Pairing 5 — Editorial Magazine
```
Heading:    Source Serif Pro (serif) — w600-700
Body:       Source Sans Pro (sans) — w400
Code:       IBM Plex Mono
Use when:   News, blog, publishing, content-heavy
Vibe:       Readable, classic, trustworthy
```

### Pairing 6 — Tech Dark
```
Heading:    Inter or Geist — w600-700
Body:       Inter or Geist — w400
Code:       Geist Mono
Use when:   Dark-mode apps, developer tools, terminal UIs
Vibe:       Precision, modern, high-contrast
```

### Pairing 7 — Playful Colorful
```
Heading:    Plus Jakarta Sans — w600-800
Body:       Inter — w400
Code:       JetBrains Mono
Use when:   Creative tools, education, children, playful brands
Vibe:       Friendly, approachable, fun
```

### Pairing 8 — Minimal Luxury
```
Heading:    Helvetica Neue or SF Pro Display — w300-600
Body:       Helvetica Neue or SF Pro Text — w400
Code:       SF Mono
Use when:   Premium products, Apple-like, minimalist
Vibe:       Ultra-clean, expensive, restrained
```

### Pairing 9 — Grotesk Modern
```
Heading:    Cabinet Grotesk or Manrope — w500-700
Body:       Inter — w400
Code:       JetBrains Mono
Use when:   Modern startups, fintech, B2B SaaS
Vibe:       Bold, geometric, contemporary
```

### Pairing 10 — Warm Serif
```
Heading:    Lora (serif) — w500-700
Body:       Inter or Nunito — w400
Code:       Source Code Pro
Use when:   Food, recipe, travel, lifestyle blog
Vibe:       Warm, cozy, inviting
```

---

## 2. TYPOGRAPHY SCALE

### Standard Scale (All projects)

| Level | Mobile | Tablet (md:) | Desktop (lg:) | Weight | Tracking |
|-------|--------|--------------|---------------|--------|----------|
| Hero (h1) | text-3xl (30px) | md:text-5xl (48px) | lg:text-6xl (60px) | 700 | -0.025em |
| Section (h2) | text-2xl (24px) | md:text-4xl (36px) | lg:text-4xl (36px) | 600 | -0.02em |
| Card Title (h3) | text-lg (18px) | md:text-xl (20px) | lg:text-2xl (24px) | 600 | normal |
| Subtitle | text-base (16px) | md:text-lg (18px) | lg:text-lg (18px) | 500 | normal |
| Body | text-base (16px) | text-base (16px) | text-base (16px) | 400 | normal |
| Small | text-sm (14px) | text-sm (14px) | text-sm (14px) | 400 | normal |
| Micro | text-xs (12px) | text-xs (12px) | text-xs (12px) | 500 | +0.05em |
| Code | text-sm (14px) | text-sm (14px) | text-sm (14px) | 400 | normal |

**Line Heights:**
- Headings: `leading-tight` (1.2-1.3)
- Body: `leading-relaxed` (1.625)
- Code: `leading-normal` (1.5)

---

## 3. FONT LOADING STRATEGY

```html
<!-- Recommended: Google Fonts + System Font fallback -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Playfair+Display:wght@500;600;700&family=JetBrains+Mono&display=swap" rel="stylesheet">
```

**Tailwind config:**
```js
// tailwind.config.js
module.exports = {
  theme: {
    fontFamily: {
      'display': ['Playfair Display', 'Georgia', 'serif'],
      'body': ['Inter', 'system-ui', 'sans-serif'],
      'mono': ['JetBrains Mono', 'Fira Code', 'monospace'],
    }
  }
}
```

---

## 4. TYPOGRAPHY RULES

| Rule | Description |
|------|-------------|
| **Pair deliberately** | Heading font ≠ Body font (except Modern Tech style) |
| **Max line length** | Never exceed 75 characters per line (use `max-w-prose` or `max-w-2xl`) |
| **No centering long text** | Never center-align paragraphs >3 lines |
| **Letter spacing** | Large headings use `tracking-tight`, uppercase uses `tracking-wide` |
| **Responsive scale** | Mobile headings are ~50% smaller than desktop |
| **Body contrast** | Body text is NEVER pure black/white — use `text-[secondary]` |
| **Font weight** | Headings: 600-700. Body: 400. Small: 400-500 |

---

## 5. ROTATION RULE

```
Task 1 → Pairing 1 (Playfair + Inter)
Task 2 → Pairing 4 (Cormorant + Inter)
Task 3 → Pairing 8 (Helvetica/SF Pro)
Task 4 → Pairing 3 (Space Grotesk + Inter)
Task 5 → Pairing 6 (Geist)
Task 6 → Pairing 9 (Cabinet Grotesk + Inter)
Task 7 → Pairing 2 (Inter + Inter)
Task 8 → Pairing 10 (Lora + Inter)
```

**Never use the same pairing twice in a row.**  
**Never default to Inter-only without a deliberate reason.**

---

**Next:** `design/spacing.md` — Layout & spacing system
