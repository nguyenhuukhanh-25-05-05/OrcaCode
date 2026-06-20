# GetDesign.md Quick Reference Guide

## 🎯 Purpose
This is your PRIMARY design inspiration source. Before coding ANY UI, you MUST consult getdesign.md.

## 🔗 Main Website
https://getdesign.md/

## 📚 What It Contains
73+ analyzed design systems from real websites with full DESIGN.md files covering:
- Color palettes (semantic names + hex + roles)
- Typography hierarchy (fonts, sizes, weights)
- Component styles (buttons, cards, inputs with states)
- Layout principles (spacing, grid, whitespace)
- Animation patterns (transitions, hovers, entrances)

## 🚀 How to Use

### Step 1: Identify the Style Needed
Match your project to a category:

**AI & LLM Platforms:**
- Claude, Cursor, Mistral AI, Ollama, Replicate, xAI

**Developer Tools:**
- Linear, Vercel, Raycast, Warp, Superhuman, Expo

**SaaS & Productivity:**
- Notion, Figma, Framer, Airtable, Cal.com, Mintlify

**Fintech & Crypto:**
- Stripe, Revolut, Coinbase, Binance, Wise

**E-commerce & Retail:**
- Shopify, Nike, Airbnb, Starbucks, Apple

**Automotive & Luxury:**
- BMW, Tesla, Ferrari, Lamborghini, Bugatti

**Media & Tech:**
- Spotify, The Verge, WIRED, SpaceX, Pinterest

### Step 2: Fetch the Design System

**Option A: Visit the analysis page**
```
https://getdesign.md/[brand-name]/design-md
```

**Option B: Fetch raw DESIGN.md from GitHub**
```
https://raw.githubusercontent.com/VoltAgent/awesome-design-md/main/sites/[brand-name]/DESIGN.md
```

**Option C: Use web_fetch tool**
```
web_fetch("https://getdesign.md/[brand-name]/design-md", mode="rendered")
```

### Step 3: Extract Key Patterns

From each DESIGN.md, extract:

1. **Color System**
   - Primary color (brand identity)
   - Accent color (CTAs, highlights)
   - Neutral scale (grays for text/backgrounds)
   - Semantic colors (success, error, warning)

2. **Typography Scale**
   - Font families (headings vs body)
   - Size scale (from xs to 6xl)
   - Font weights (normal, medium, semibold, bold)
   - Letter-spacing (tight for display, normal for body)

3. **Component Patterns**
   - Button styles (primary, secondary, ghost)
   - Card designs (borders, shadows, hover states)
   - Input styles (borders, focus states, error states)
   - Navigation patterns (desktop vs mobile)

4. **Animation Principles**
   - Transition durations (200ms, 300ms, 500ms)
   - Easing functions (ease-out, ease-in-out)
   - Hover effects (scale, glow, color shift)
   - Entrance animations (fade-up, slide-in)

### Step 4: Adapt (Don't Copy)

- Use their color psychology but adjust hue/saturation
- Use their typography scale but change font families
- Use their spacing system but adapt to your content
- Use their animation patterns but vary timing/effects

## 🔥 Top 10 Most Referenced Designs

### 1. Linear (https://getdesign.md/linear.app/design-md)
**Style:** Ultra-minimal, precise, purple accent  
**Best for:** Project management, SaaS dashboards  
**Key patterns:** Dark UI (#17171A), purple accent (#5E6AD2), Inter font, minimal borders

### 2. Stripe (https://getdesign.md/stripe/design-md)
**Style:** Purple gradients, weight-300 elegance  
**Best for:** Payment pages, financial tools  
**Key patterns:** Purple gradients, ultra-light font weights, smooth animations

### 3. Vercel (https://getdesign.md/vercel/design-md)
**Style:** Black & white precision, Geist font  
**Best for:** Developer tools, deployment platforms  
**Key patterns:** Monochrome, geometric shapes, Geist Mono font

### 4. Notion (https://getdesign.md/notion/design-md)
**Style:** Warm minimalism, serif headings  
**Best for:** Productivity apps, note-taking  
**Key patterns:** Warm beige tones, Söhne font, soft surfaces

### 5. Cursor (https://getdesign.md/cursor/design-md)
**Style:** Sleek dark interface, gradient accents  
**Best for:** Code editors, developer tools  
**Key patterns:** Dark gray (#1a1a1a), blue-purple gradients, VS Code inspired

### 6. Framer (https://getdesign.md/framer/design-md)
**Style:** Bold black and blue, motion-first  
**Best for:** Website builders, design tools  
**Key patterns:** High contrast, bold typography, smooth transitions

### 7. Figma (https://getdesign.md/figma/design-md)
**Style:** Vibrant multi-color, playful yet professional  
**Best for:** Design tools, creative platforms  
**Key patterns:** Rainbow colors, friendly UI, rounded corners

### 8. Tesla (https://getdesign.md/tesla/design-md)
**Style:** Radical subtraction, full-viewport photography  
**Best for:** Automotive, minimalist showcase  
**Key patterns:** Near-zero UI, cinematic images, white space

### 9. Apple (https://getdesign.md/apple/design-md)
**Style:** Premium white space, SF Pro, cinematic  
**Best for:** Consumer electronics, premium products  
**Key patterns:** SF Pro Display, massive whitespace, subtle shadows

### 10. Shopify (https://getdesign.md/shopify/design-md)
**Style:** Dark-first cinematic, neon green accent  
**Best for:** E-commerce platforms  
**Key patterns:** Dark backgrounds, lime green (#95BF47), ultra-light type

## 🎨 Quick Design Decision Matrix

| Project Type | Recommended Reference | Color Direction | Typography Style |
|--------------|----------------------|-----------------|------------------|
| AI Assistant | Claude, Cursor | Warm terracotta / Purple | Clean sans-serif |
| Code Editor | Cursor, Warp, Vercel | Dark gray + accent | Monospace focused |
| SaaS Dashboard | Linear, Notion | Purple / Neutral | Minimal, precise |
| Landing Page | Framer, Stripe, Vercel | Bold gradients | Display + body contrast |
| E-commerce | Shopify, Nike, Apple | High contrast | Bold display type |
| Fintech | Stripe, Revolut, Wise | Professional blues/purples | Trustworthy, clean |
| Portfolio | Framer, Figma, Clay | Creative, vibrant | Art-directed |
| Documentation | Mintlify, Supabase | Readable, calm | Optimized for reading |

## 📋 Workflow Template

When you receive a UI task:

```
TASK: [User request]

STEP 1: REFERENCE LOOKUP
- Visit https://getdesign.md/
- Identify closest match: [Brand name]
- URL: https://getdesign.md/[brand]/design-md

STEP 2: DESIGN EXTRACTION
- Primary color: [color + hex]
- Accent color: [color + hex]
- Font family: [font name]
- Key pattern: [description]

STEP 3: ADAPTATION PLAN
- My color: [your adapted color]
- My typography: [your fonts]
- My unique twist: [what makes it different]

STEP 4: IMPLEMENTATION
[Write the code]

STEP 5: POLISH
- Added hover states? ✓
- Added loading states? ✓
- Responsive? ✓
- Accessible? ✓
```

## 🚫 Common Mistakes to Avoid

❌ **Copying exactly** - Always adapt, never clone  
❌ **Ignoring the reference** - Don't skip the research phase  
❌ **Using only one reference** - Compare 2-3 designs  
❌ **Forgetting responsive** - All references include mobile patterns  
❌ **Skipping animations** - Most references have subtle micro-interactions  

## 💡 Pro Tips

1. **Rotate references** - Don't use the same design twice in a row
2. **Mix inspirations** - Combine colors from one, typography from another
3. **Study the "why"** - Understand design decisions, not just copy values
4. **Save favorites** - Keep a mental list of designs that match your style
5. **Check updates** - New designs added regularly to getdesign.md

## 🔗 Quick Links

- Main catalog: https://getdesign.md/
- GitHub repo: https://github.com/VoltAgent/awesome-design-md
- Request a design: https://getdesign.md/request
- Google Stitch spec: https://stitch.withgoogle.com/docs/design-md/overview/

---

**Remember: getdesign.md is not just a color picker. It's a comprehensive design system analyzer. Use it as your design mentor, not just a reference tool.**
