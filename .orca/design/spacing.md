# Spacing — Layout & Spacing System

> **Module:** Design System  
> **Read Time:** 2 minutes  
> **When:** Phase 1 — Design Planning

---

## 1. 8-POINT GRID SYSTEM

All spacing MUST follow multiples of 8 (or 4 for micro-spacing):

```
 2px  →  micro-tight
 4px  →  micro
 8px  →  xs
12px  →  sm
16px  →  base
20px  →  md
24px  →  lg
32px  →  xl
40px  →  2xl
48px  →  3xl
64px  →  4xl
80px  →  5xl
96px  →  6xl
128px →  7xl
```

---

## 2. RESPONSIVE SPACING

### Page Padding
```
Mobile (default):  px-4  (16px)
Tablet (md:):      md:px-8  (32px)
Desktop (lg:):     lg:px-16  (64px)
Large (xl:):       xl:px-24  (96px)
Max width:         max-w-7xl mx-auto (1280px centered)
```

### Section Spacing (Vertical Rhythm)
```
Between sections:      py-12 (48px) / md:py-16 (64px) / lg:py-24 (96px)
Between related blocks: space-y-8 (32px) / gap-8
Between heading + body: mb-4 (16px)
Between cards (grid):   gap-6 (24px)
Inside cards:           p-6 (24px)
```

---

## 3. COMPONENT SPACING

| Component | Padding | Gap | Border Radius |
|-----------|---------|-----|---------------|
| Button | px-6 py-3 (24px 12px) | gap-2 | rounded-xl (12px) |
| Input | px-4 py-3 (16px 12px) | — | rounded-xl (12px) |
| Card | p-6 (24px) | gap-4 | rounded-2xl (16px) |
| Modal | p-6 (24px) | gap-4 | rounded-2xl (16px) |
| Navigation | px-4, h-16 | gap-8 | — |
| Footer section | py-12 | gap-8 | — |
| Badge | px-3 py-1 | — | rounded-full |

---

## 4. GRID LAYOUTS

### Standard Card Grid
```
Mobile:   grid-cols-1
Tablet:   md:grid-cols-2
Desktop:  lg:grid-cols-3
Large:    xl:grid-cols-4
Gap:      gap-6
```

### Bento Grid (Mixed Sizes)
```
Desktop grid: grid-cols-3 + grid-cols-4
- Hero card: col-span-2 row-span-2
- Standard: col-span-1 row-span-1
- Wide: col-span-2 row-span-1
- Tall: col-span-1 row-span-2
```

### Two-Column Content (Hero/Feature)
```
Mobile:   flex flex-col
Desktop:  lg:grid lg:grid-cols-2 lg:gap-12 lg:items-center
Image:    order-first or order-last
```

---

## 5. LAYOUT PATTERNS

### Page Shell
```html
<div class="min-h-screen flex flex-col">
  <header class="sticky top-0 z-50">...</header>
  <main class="flex-1">
    <section class="py-12 lg:py-24">
      <div class="max-w-7xl mx-auto px-4 lg:px-16">
        <!-- content -->
      </div>
    </section>
  </main>
  <footer class="...">...</footer>
</div>
```

### Hero Section (Full-Viewport)
```html
<section class="relative min-h-[80vh] flex items-center">
  <div class="max-w-7xl mx-auto px-4 lg:px-16">
    <div class="max-w-3xl">
      <h1 class="text-3xl lg:text-6xl font-bold">...</h1>
      <p class="text-base lg:text-lg mt-6">...</p>
      <div class="flex gap-4 mt-8">...</div>
    </div>
  </div>
</section>
```

---

## 6. SPACING RULES

| Rule | Description |
|------|-------------|
| **Multiples of 8** | All spacing in increments of 8 (4 for micro) |
| **gap-* not space-y-** | Never use `space-y-*`; always use `flex flex-col gap-*` |
| **size-* for square** | `size-10` not `w-10 h-10` |
| **max-w-7xl** | Max content width 1280px, centered with mx-auto |
| **Mobile-first** | Base classes = mobile, md: = tablet, lg: = desktop |
| **Whitespace > clutter** | When in doubt, add more space. 40%+ whitespace is premium. |

---

**Next:** `design/styles.md` — 10+ design style rotation
