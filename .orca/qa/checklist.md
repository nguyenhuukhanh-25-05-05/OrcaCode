# QA Checklist - 16 Quality Gates

> **Module:** Quality Assurance  
> **Read Time:** 2 minutes  
> **When:** Phase 5 - Final Review

---

## 🎯 PURPOSE

Every component MUST score **16/16** before marking work complete.

**If score < 16/16 → INCOMPLETE, go back and fix failures.**

---

## ✅ THE 16 CHECKS

### Category 1: Design Quality (4 checks)

#### ✓ 1. Has Design Tokens
```
Question: Did you document color, typography, signature element?

Pass Example:
## Design Tokens
- Primary: #6366f1 - CTA buttons
- Display: Inter Bold - Headings
- Signature: Floating ripple buttons

Fail Example:
[No design tokens documented]
```

#### ✓ 2. Avoids AI Defaults
```
Question: Is this cream #F4F1EA + terracotta? Black + acid-green? Broadsheet?

Pass Example:
Using deep purple #6366f1 + cyan #06b6d4 (project-specific)

Fail Example:
Using cream #F4F1EA + terracotta #c2410c (generic AI default)
```

#### ✓ 3. Has Signature Element
```
Question: What is the ONE memorable thing about this design?

Pass Example:
Glassmorphism cards with animated gradient glow on hover

Fail Example:
[Can't identify any unique element]
```

#### ✓ 4. Fonts Paired Deliberately
```
Question: Are fonts chosen for this project, not just Inter everywhere?

Pass Example:
Display: Playfair Display (serif, editorial feel)
Body: Inter (clean, readable)

Fail Example:
Display: Inter Bold
Body: Inter Regular
(same font family for both, not deliberate pairing)
```

---

### Category 2: Structure Quality (4 checks)

#### ✓ 5. Uses Existing Components
```
Question: Did you search for components before building custom markup?

Pass Example:
Used: <Button>, <Card>, <Input> from components library

Fail Example:
Built custom <div class="my-button"> instead of using <Button>
```

#### ✓ 6. gap-* Spacing (not space-y-*)
```
Question: All spacing uses gap-*, not space-y-* or space-x-*?

Pass Example:
<div class="flex flex-col gap-4">

Fail Example:
<div class="space-y-4">
```

#### ✓ 7. Semantic Colors
```
Question: Colors use semantic tokens, not raw Tailwind values?

Pass Example:
<div class="bg-primary text-foreground">

Fail Example:
<div class="bg-blue-500 text-gray-900">
```

#### ✓ 8. Correct Composition
```
Question: Components follow correct patterns (FieldGroup, Card structure)?

Pass Example:
<FieldGroup>
  <Field>
    <FieldLabel>Email</FieldLabel>
    <Input />
  </Field>
</FieldGroup>

Fail Example:
<div>
  <Label>Email</Label>
  <Input />
</div>
```

---

### Category 3: Animation Quality (4 checks)

#### ✓ 9. Duration ≤ 300ms
```
Question: All UI animations are ≤ 300ms?

Pass Example:
transition-all duration-200
(200ms ✓)

Fail Example:
transition-all duration-500
(500ms ✗ - too slow for UI)
```

#### ✓ 10. Custom Easing
```
Question: Using custom easing, not built-in CSS?

Pass Example:
transition: transform 200ms cubic-bezier(0.23, 1, 0.32, 1);

Fail Example:
transition: transform 200ms ease-in;
(built-in ease-in, and it's the WRONG one)
```

#### ✓ 11. Never scale(0) or ease-in
```
Question: No scale(0) entry animations? No ease-in timing?

Pass Example:
.entering { transform: scale(0.95); opacity: 0; }
.button { transition: transform 200ms ease-out; }

Fail Example:
.entering { transform: scale(0); }
.button { transition: all 300ms ease-in; }
```

#### ✓ 12. Reduced-Motion Handled
```
Question: Respects prefers-reduced-motion?

Pass Example:
@media (prefers-reduced-motion: reduce) {
  * { animation-duration: 0.01ms !important; }
}

Fail Example:
[No reduced-motion handling]
```

---

### Category 4: Performance Quality (4 checks)

#### ✓ 13. Only Transform + Opacity
```
Question: Only animates transform and opacity (not width/height/padding)?

Pass Example:
transition: transform 200ms, opacity 200ms;

Fail Example:
transition: width 300ms, height 300ms;
(animating layout properties ✗)
```

#### ✓ 14. No Layout Thrashing
```
Question: No interleaved reads/writes in same frame?

Pass Example:
// FLIP: Read all, then write all
const first = el.getBoundingClientRect();
el.classList.add('moved');
const last = el.getBoundingClientRect();
el.style.transform = `translateX(${first.left - last.left}px)`;

Fail Example:
// Thrashing: Read, write, read, write
el.style.left = el.getBoundingClientRect().left + 10 + 'px';
```

#### ✓ 15. Scroll Timeline (not JS listener)
```
Question: Scroll effects use View Timeline, not JS listeners?

Pass Example:
.reveal {
  animation: fade-in linear;
  animation-timeline: view();
}

Fail Example:
window.addEventListener('scroll', () => {
  el.style.opacity = scrollY / 500;
});
```

#### ✓ 16. Blur ≤ 8px
```
Question: Blur effects are ≤ 8px and not on large surfaces?

Pass Example:
backdrop-blur-sm (4px) on card ✓

Fail Example:
backdrop-blur-2xl (40px) on full-page overlay ✗
```

---

## 📊 SCORING

### Calculate Your Score:

```
Design:      [ ] [ ] [ ] [ ]    /4
Structure:   [ ] [ ] [ ] [ ]    /4
Animation:   [ ] [ ] [ ] [ ]    /4
Performance: [ ] [ ] [ ] [ ]    /4
                          ────────
TOTAL:                          /16
```

### Result:

| Score | Status | Action |
|-------|--------|--------|
| 16/16 | ✅ PASS | Mark work complete |
| 14-15/16 | ⚠️ ALMOST | Fix 1-2 failures quickly |
| 12-13/16 | ❌ FAIL | Revise failed category |
| < 12/16 | ❌ MAJOR FAIL | Start over from Phase 1 |

---

## 🔍 DETAILED FAILURE DIAGNOSIS

### If you scored < 16/16:

```
Example: Score 14/16 (2 failures)

Failed:
- [ ] Avoids AI defaults (using cream #F4F1EA)
- [ ] Custom easing (using ease-in)

Root Cause Analysis:
1. Check 2 failed → Did not review design/styles.md before Phase 1
2. Check 10 failed → Did not read animation/rules.md before Phase 3

Fix:
1. Replace cream #F4F1EA with project-specific color (e.g., purple #6366f1)
2. Replace ease-in with cubic-bezier(0.23, 1, 0.32, 1)

Re-run checklist → If pass → Continue
```

---

## 💡 QUICK FIX GUIDE

### Common Failures & Fixes:

| Failed Check | Quick Fix |
|--------------|-----------|
| #2 Avoids AI defaults | Check `design/styles.md`, pick non-generic colors |
| #6 gap-* spacing | Find/replace `space-y-` → `flex flex-col gap-` |
| #7 Semantic colors | Replace `bg-blue-500` → `bg-primary` |
| #9 Duration ≤ 300ms | Change `duration-500` → `duration-200` |
| #10 Custom easing | Add custom easing curve from `animation/rules.md` |
| #11 Never scale(0) | Change `scale(0)` → `scale(0.95) + opacity: 0` |
| #13 Transform+opacity only | Replace width/height animations with transform |
| #15 Scroll timeline | Replace JS listener with CSS View Timeline |

---

## 🎯 SELF-CRITIQUE QUESTIONS

**After scoring 16/16, ask yourself:**

1. **Would Apple approve this?**  
   (Premium feel, attention to detail)

2. **Would Linear approve this?**  
   (Ultra-minimal, precise, functional)

3. **Would Stripe approve this?**  
   (Elegant, smooth, trustworthy)

4. **Would Framer approve this?**  
   (Motion-first, bold, design-forward)

**If answer is NO to any → Keep refining.**

---

## 📸 VISUAL REVIEW (If Available)

### Take screenshots and check:

- [ ] Visual balance (elements aligned, spaced consistently)
- [ ] Color harmony (colors work together, not clashing)
- [ ] Typography hierarchy (clear heading/body distinction)
- [ ] Interactive states (hover/focus/active visible)
- [ ] Loading states (spinners, skeletons present)
- [ ] Error states (red borders, error messages clear)
- [ ] Empty states (helpful, actionable)

---

## ⏱️ CHECKLIST TIMING

**Simple Component (Button):**
- Run checklist: 1 minute
- Fix failures: 2-3 minutes
- Re-check: 30 seconds

**Complex Component (Form, Dashboard):**
- Run checklist: 2 minutes
- Fix failures: 5-10 minutes
- Re-check: 1 minute

**Total overhead: ~5-15 minutes per component**

---

## 🚀 PASS CRITERIA SUMMARY

```
✅ WORK IS COMPLETE WHEN:
   • Score: 16/16
   • Self-critique: All YES
   • Visual review: Passed
   • Ready to present to user

❌ WORK IS INCOMPLETE WHEN:
   • Score: < 16/16
   • Self-critique: Any NO
   • Visual issues: Present
   • User would say "looks generic"
```

---

**Next Steps:**
- If PASS → Present work to user
- If FAIL → Fix failures, re-run checklist
- For accessibility details → `qa/accessibility.md`
- For performance deep-dive → `qa/performance.md`
