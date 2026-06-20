# Animation Performance — Optimization Rules

> **Module:** Animation  
> **Read Time:** 2 minutes  
> **When:** Phase 4 — Performance Audit

---

## 1. RENDERING COST HIERARCHY

```
Cheapest → Most Expensive:
Composite  (transform, opacity)  → ✅ ALWAYS prefer
Paint      (color, borders, shadows, filters) → ⚠️ Small areas only
Layout     (width, height, padding, margin, position) → ❌ NEVER animate
```

---

## 2. CRITICAL RULES

| Rule | Description |
|------|-------------|
| **Only transform + opacity** | Never animate width, height, padding, margin, top, left |
| **CSS over JS** | CSS animations run off main thread; JS blocks |
| **GPU acceleration** | `transform` and `opacity` are GPU-accelerated |
| **No layout thrashing** | Batch DOM reads before writes (FLIP technique) |
| **No blur > 8px** | Blur is expensive; max 8px, small surfaces only |
| **Pause off-screen** | Stop animations when element is not visible |

---

## 3. FLIP TECHNIQUE (Layout Animation Without Layout Thrashing)

```javascript
// 1. Measure (read)
const first = el.getBoundingClientRect();

// 2. Apply change (write)
el.classList.add('moved');

// 3. Measure again (read)
const last = el.getBoundingClientRect();

// 4. Invert with transform (write)
const deltaX = first.left - last.left;
const deltaY = first.top - last.top;
el.style.transform = `translate(${deltaX}px, ${deltaY}px)`;

// 5. Play animation
requestAnimationFrame(() => {
  el.style.transition = 'transform 300ms ease-out';
  el.style.transform = '';
});
```

---

## 4. SCROLL PERFORMANCE

```css
/* ✅ GOOD: CSS View Timeline (no JS listener) */
.reveal {
  animation: fade-in linear;
  animation-timeline: view();
  animation-range: entry 0% entry 100%;
}

/* ❌ BAD: JS scroll listener */
window.addEventListener('scroll', () => { ... });
```

---

## 5. BLUR USAGE

```css
/* ✅ Safe: small blur on small element */
.card { backdrop-filter: blur(4px); }

/* ❌ Unsafe: large blur on large surface */
.hero { backdrop-filter: blur(40px); }

/* ✅ Alternative: use opacity instead of blur */
.overlay { background: rgba(0,0,0,0.5); }
```

---

## 6. AUDIT CHECKLIST

- [ ] Only `transform` and `opacity` are animated
- [ ] No interleaved DOM reads/writes
- [ ] No scroll event listeners (use View Timeline)
- [ ] Blur ≤ 8px and on small surfaces only
- [ ] No CSS variable animation for transform/opacity
- [ ] Animations paused when off-screen
- [ ] Reduced-motion media query present

---

**Next:** `components/patterns.md` — Component selection guide
