# Animation Rules — Decision Framework

> **Module:** Animation  
> **Read Time:** 3 minutes  
> **When:** Phase 3 — Animation Implementation

---

## 1. SHOULD THIS ANIMATE?

| Frequency | Decision |
|-----------|----------|
| 100+/day (keyboard shortcuts) | NO animation. Ever. |
| 10s/day (hover, nav transitions) | Remove or drastically reduce |
| Occasional (modals, toasts) | Standard animation (200-500ms) |
| Rare (onboarding, celebrations) | Can add delight |

**NEVER animate keyboard-initiated actions.**

---

## 2. WHAT EASING?

```
Is element entering/exiting the screen?
  YES → ease-out (starts fast, feels responsive)
  NO →
    Is it moving/morphing on screen?
      YES → ease-in-out
    Is it hover/color change?
      YES → ease (standard)
    Is it constant motion (spinner)?
      YES → linear
    Default → ease-out
```

### Custom Easing Curves

```css
--ease-out: cubic-bezier(0.23, 1, 0.32, 1);
--ease-in-out: cubic-bezier(0.77, 0, 0.175, 1);
--ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
--ease-drawer: cubic-bezier(0.32, 0.72, 0, 1);
```

**NEVER use `ease-in` for UI.** It feels sluggish.

---

## 3. HOW FAST?

| Element | Duration |
|---------|----------|
| Button press | 100-160ms |
| Tooltips, small popovers | 125-200ms |
| Dropdowns, selects | 150-250ms |
| Hover effects | 200-300ms |
| Modals, drawers | 200-500ms |
| Page transitions | 300-500ms |
| Scroll reveals | 400-700ms |

**Rule: UI animations ≤ 300ms. Scroll animations ≤ 700ms.**

---

## 4. ENTRANCE ANIMATIONS

### Fade Up (Default)
```css
.entrance {
  opacity: 0;
  transform: translateY(20px);
  transition: opacity 500ms ease-out, transform 500ms ease-out;
}
.entrance.visible {
  opacity: 1;
  transform: translateY(0);
}
```

### Staggered Children
```css
.parent > .child:nth-child(1) { transition-delay: 0ms; }
.parent > .child:nth-child(2) { transition-delay: 100ms; }
.parent > .child:nth-child(3) { transition-delay: 200ms; }
.parent > .child:nth-child(4) { transition-delay: 300ms; }
```

---

## 5. MICRO-INTERACTIONS

```css
/* Button press feedback */
.button:active {
  transform: scale(0.97);
}

/* Card hover lift */
.card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 24px rgba(0,0,0,0.1);
}

/* Link underline */
.link {
  position: relative;
}
.link::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  width: 0;
  height: 1px;
  background: currentColor;
  transition: width 200ms ease-out;
}
.link:hover::after {
  width: 100%;
}
```

---

## 6. REDUCED MOTION

```css
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

**Next:** `animation/performance.md` — Performance optimization
