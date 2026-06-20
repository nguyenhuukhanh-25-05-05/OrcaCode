# Premium UI Skills - 4 Kỹ Năng Vàng

> Tổng hợp từ Anthropic (Claude), Emil Kowalski (Sonner), và shadcn/ui  
> **Mục đích:** Biến AI agent thành Design Engineer chuyên nghiệp

---

## 🚨 DIVERSITY MANDATE (ĐỌC TRƯỚC TIÊN)

**Vấn đề lớn nhất của AI khi tạo UI là: THIẾU ĐA DẠNG.**  
Mọi AI agent đều có thiên hướng rơi vào 3 pattern mặc định:
1. ❌ Cream (#F4F1EA) + Terracotta
2. ❌ Near-black (#0a0a0a) + Acid green
3. ❌ Blue-purple glassmorphism

**GIẢI PHÁP: BẮT BUỘC rotation qua 12 styles + 12 palettes + 10 typography pairings.**

### Quy trình enforced diversity:
```
Bước 1: Mở design/styles.md → chọn style KHÁC với 3 lần gần nhất
Bước 2: Mở design/colors.md → chọn palette KHỚP với style
Bước 3: Mở design/typography.md → chọn font pairing KHỚP với style
Bước 4: Nếu style "Apple" → KHÔNG dùng purple accent
         Nếu style "Gucci" → KHÔNG dùng glassmorphism
         Nếu style "Linear" → KHÔNG dùng gradient backgrounds
```

**Nếu không có lý do CHÍNH ĐÁNG để chọn style, palette, font → mặc định là SAI.**

---

## 🎨 SKILL 1: FRONTEND-DESIGN (The Soul)

### Philosophy: Make Distinctive Choices

**Reject templated defaults.** Every project deserves its own visual identity.

### Design Principles

1. **Ground it in the subject** - Let the product's world dictate design choices
2. **Hero is a thesis** - Open with the most characteristic element
3. **Typography carries personality** - Pair fonts deliberately
4. **Structure is information** - Use numbering/dividers only when meaningful
5. **Leverage motion deliberately** - One orchestrated moment > scattered effects
6. **Match complexity to vision** - Maximalist needs elaboration; minimal needs precision

### Workflow: Brainstorm → Plan → Critique → Build

**Step 1: Design Plan (Before Code)**
```markdown
## Design Tokens

**Color Palette:**
- Primary: [name] #hex - [usage]
- Accent: [name] #hex - [usage]
- Neutrals: [scale description]

**Typography:**
- Display: [font] - [weights] - [when to use]
- Body: [font] - [weights] - [when to use]
- Utility: [font] - [caption/data use]

**Layout Concept:**
[ASCII wireframe + prose description]

**Signature Element:**
[The ONE memorable thing this design will be known for]
```

**Step 2: Self-Critique**
Ask: "Would I produce this same design for ANY similar brief?"  
If YES → revise to be more specific to this project

**Step 3: Build**
Follow the plan exactly. Derive every color/type decision from it.

### Avoid AI Default Patterns

These are DEFAULTS, not CHOICES:
- ❌ Warm cream (#F4F1EA) + terracotta accent
- ❌ Near-black + acid green/vermilion
- ❌ Broadsheet layout + hairline rules + zero border-radius

Only use these if the brief EXPLICITLY asks for them.

### Writing in Design

**Words are design material, not decoration.**

Rules:
- Active voice by default: "Save changes" not "Submit"
- Name from user's perspective: "Notifications" not "Webhook Config"  
- Errors explain what + how to fix
- Empty states are invitations to act
- Keep register conversational: sentence case, plain verbs, no filler

---

## ⚡ SKILL 2: EMIL-DESIGN-ENG (The Polish)

### Core Philosophy

**Taste is trained, not innate.** Study great work, think deeply, practice relentlessly.  
**Unseen details compound.** Users never notice individual details — they feel the sum.  
**Beauty is leverage.** Good defaults and animations are real differentiators.

### Animation Decision Framework

#### Decision 1: Should this animate at all?

| Frequency | Decision |
|-----------|----------|
| 100+ times/day (keyboard shortcuts) | No animation. Ever. |
| Tens of times/day (hover, navigation) | Remove or drastically reduce |
| Occasional (modals, toasts) | Standard animation |
| Rare (onboarding, celebrations) | Can add delight |

**NEVER animate keyboard-initiated actions.**

#### Decision 2: What is the purpose?

Valid purposes:
- Spatial consistency (enter/exit from same direction)
- State indication (morphing feedback)
- Explanation (how a feature works)
- Feedback (button press confirmation)
- Preventing jarring changes

If purpose is "looks cool" + high frequency → don't animate.

#### Decision 3: What easing?

```
Is element entering/exiting?
  Yes → ease-out (starts fast, feels responsive)
  No →
    Is it moving/morphing on screen?
      Yes → ease-in-out
    Is it hover/color change?
      Yes → ease
    Is it constant motion?
      Yes → linear
    Default → ease-out
```

**Use custom curves:**
```css
--ease-out: cubic-bezier(0.23, 1, 0.32, 1);
--ease-in-out: cubic-bezier(0.77, 0, 0.175, 1);
--ease-drawer: cubic-bezier(0.32, 0.72, 0, 1); /* iOS-like */
```

**NEVER use ease-in for UI.** It feels sluggish.

#### Decision 4: How fast?

| Element | Duration |
|---------|----------|
| Button press | 100-160ms |
| Tooltips, small popovers | 125-200ms |
| Dropdowns, selects | 150-250ms |
| Modals, drawers | 200-500ms |

**Rule: UI animations ≤ 300ms**

### Component Building Rules

**Buttons must feel responsive:**
```css
.button {
  transition: transform 160ms ease-out;
}
.button:active {
  transform: scale(0.97);
}
```

**Never animate from scale(0):**
```css
/* BAD */
.entering { transform: scale(0); }

/* GOOD */
.entering { transform: scale(0.95); opacity: 0; }
```

**Popovers origin-aware (not modals):**
```css
/* Popover scales from trigger */
.popover {
  transform-origin: var(--radix-popover-content-transform-origin);
}

/* Modal stays centered */
.modal {
  transform-origin: center;
}
```

**Tooltips: skip delay on subsequent hovers**  
Once one tooltip is open, next tooltips appear instantly with no animation.

**Use blur to mask imperfect transitions:**
```css
.transitioning {
  filter: blur(2px);
  opacity: 0.7;
}
```

### Performance Rules

✅ Only animate `transform` and `opacity` (GPU accelerated)  
❌ Never animate `width`, `height`, `padding`, `margin` (triggers layout)  
❌ CSS variables are inheritable (expensive on large trees)  
✅ CSS animations > JS under load (off main thread)

**Framer Motion caveat:**
```jsx
/* NOT hardware accelerated */
<motion.div animate={{ x: 100 }} />

/* Hardware accelerated */
<motion.div animate={{ transform: "translateX(100px)" }} />
```

### Accessibility

**Reduced motion:**
```css
@media (prefers-reduced-motion: reduce) {
  .element {
    animation: fade 0.2s ease; /* Keep opacity/color */
    /* Remove transform-based motion */
  }
}
```

**Touch device hovers:**
```css
@media (hover: hover) and (pointer: fine) {
  .element:hover { transform: scale(1.05); }
}
```

### Review Format (MANDATORY)

Always use markdown table:

| Before | After | Why |
|--------|-------|-----|
| `transition: all 300ms` | `transition: transform 200ms ease-out` | Specify exact properties |
| `scale(0)` | `scale(0.95); opacity: 0` | Nothing appears from nothing |
| `ease-in` | `ease-out` or custom | ease-in feels sluggish |

---

## 🏗️ SKILL 3: SHADCN (The Structure)

### Core Principles

1. **Use existing components first** - Search before building custom
2. **Compose, don't reinvent** - Settings = Tabs + Card + form controls
3. **Use built-in variants** - `variant="outline"`, `size="sm"`
4. **Use semantic colors** - `bg-primary`, `text-muted-foreground` (never raw values)

### Critical Rules

#### Styling & Tailwind

❌ No `space-x-*` or `space-y-*` → Use `flex gap-*`  
✅ `size-*` when width = height → `size-10` not `w-10 h-10`  
✅ `truncate` shorthand → Not `overflow-hidden text-ellipsis whitespace-nowrap`  
❌ No manual `dark:` overrides → Use semantic tokens  
✅ Use `cn()` for conditional classes  

#### Forms & Inputs

✅ Forms use `FieldGroup` + `Field` (never raw `div` with `space-y-*`)  
✅ `InputGroup` uses `InputGroupInput`/`InputGroupTextarea`  
✅ Option sets (2-7 choices) use `ToggleGroup`  
✅ Validation: `data-invalid` on `Field`, `aria-invalid` on control  

```tsx
/* CORRECT Form Layout */
<FieldGroup>
  <Field>
    <FieldLabel htmlFor="email">Email</FieldLabel>
    <Input id="email" />
  </Field>
</FieldGroup>

/* CORRECT Validation */
<Field data-invalid>
  <FieldLabel>Email</FieldLabel>
  <Input aria-invalid />
  <FieldDescription>Invalid email.</FieldDescription>
</Field>
```

#### Component Structure

✅ Items always inside their Group (SelectItem → SelectGroup)  
✅ Dialog/Sheet/Drawer always need a Title (use `className="sr-only"` if hidden)  
✅ Use full Card composition (CardHeader/CardTitle/CardContent/CardFooter)  
✅ `Avatar` always needs `AvatarFallback`  
✅ `TabsTrigger` must be inside `TabsList`  

#### Icons

✅ Icons in `Button` use `data-icon`:
```tsx
<Button>
  <SearchIcon data-icon="inline-start" />
  Search
</Button>
```

❌ No sizing classes on icons inside components (components handle it)  
✅ Pass icons as objects: `icon={CheckIcon}` not string keys  

### Component Selection Quick Reference

| Need | Use |
|------|-----|
| Button/action | `Button` with variant |
| Form inputs | `Input`, `Select`, `Combobox`, `Switch`, `Checkbox`, `RadioGroup` |
| Toggle 2-5 options | `ToggleGroup` + `ToggleGroupItem` |
| Data display | `Table`, `Card`, `Badge`, `Avatar` |
| Navigation | `Sidebar`, `NavigationMenu`, `Breadcrumb`, `Tabs` |
| Overlays | `Dialog` (modal), `Sheet` (side), `Drawer` (bottom), `AlertDialog` |
| Feedback | `sonner` (toast), `Alert`, `Progress`, `Skeleton`, `Spinner` |
| Empty states | `Empty` |
| Callouts | `Alert` |

---

## 🔬 SKILL 4: FIXING-MOTION-PERFORMANCE (The Quality Check)

### Never Patterns (Critical)

❌ Do NOT interleave layout reads and writes in same frame  
❌ Do NOT animate layout continuously on large surfaces  
❌ Do NOT drive animation from `scrollTop`/`scrollY`/scroll events  
❌ No `requestAnimationFrame` loops without stop condition  
❌ Do NOT mix multiple animation systems that measure/mutate layout  

### Rendering Steps Glossary

- **Composite** (cheapest): transform, opacity
- **Paint** (medium): color, borders, gradients, masks, images, filters
- **Layout** (expensive): size, position, flow, grid, flex

### Performance Rules by Priority

#### 1. Choose the Mechanism (Critical)

✅ Default to `transform` and `opacity` for motion  
✅ Paint/layout animation OK only on small, isolated surfaces  
✅ One-shot effects acceptable more than continuous motion  

#### 2. Measurement (High)

✅ Measure once, then animate via transform/opacity  
✅ Batch all DOM reads before writes  
❌ Do NOT read layout repeatedly during animation  
✅ Prefer FLIP technique for layout-like effects  

**FLIP Example:**
```js
// Measure BEFORE change
const first = el.getBoundingClientRect();
// Apply change
el.classList.add('moved');
// Measure AFTER change
const last = el.getBoundingClientRect();
// Invert with transform
el.style.transform = `translateX(${first.left - last.left}px)`;
// Play animation
requestAnimationFrame(() => {
  el.style.transition = 'transform 0.3s';
  el.style.transform = '';
});
```

#### 3. Scroll (High)

✅ Prefer Scroll/View Timelines for scroll-linked motion  
✅ Use `IntersectionObserver` for visibility  
❌ Do NOT poll scroll position  
✅ Pause animations when off-screen  

**Scroll Timeline Example:**
```css
/* Instead of JS scroll listener */
.reveal {
  animation: fade-in linear;
  animation-timeline: view();
  animation-range: entry 0% entry 100%;
}
```

#### 4. Paint (Medium-High)

✅ Paint animation allowed only on small elements  
❌ Do NOT animate paint properties on large containers  
❌ Do NOT animate CSS variables for transform/opacity/position  
❌ Do NOT animate inherited CSS variables  

#### 5. Blur and Filters (Medium)

✅ Keep blur animation small (≤8px)  
✅ Use blur only for short, one-time effects  
❌ Never animate blur continuously  
❌ Never animate blur on large surfaces  
✅ Prefer opacity + translate before blur  

### Common Fixes

```css
/* Layout thrashing: animate transform instead of width */
/* BEFORE */ .panel { transition: width 0.3s; }
/* AFTER */  .panel { transition: transform 0.3s; }

/* Scroll-linked: use scroll-timeline instead of JS */
/* BEFORE */ window.addEventListener('scroll', () => el.style.opacity = scrollY / 500)
/* AFTER */  .reveal { animation: fade-in linear; animation-timeline: view(); }
```

### Review Guidance

1. Enforce critical rules first (never patterns)
2. Choose least expensive rendering work
3. For any non-default choice, state the constraint (surface size/duration/interaction)
4. Prefer actionable notes + concrete alternatives

---

## 🎯 INTEGRATION WORKFLOW

When building ANY UI component, follow this sequence:

### Phase 1: Design Planning (frontend-design)
1. Identify subject, audience, page job
2. Create design tokens (color, typography, layout, signature)
3. Self-critique against AI defaults
4. Get approval before coding

### Phase 2: Component Structure (shadcn)
1. Search for existing components first
2. Compose using correct patterns (FieldGroup, Card composition, etc.)
3. Use semantic colors and built-in variants
4. Follow spacing rules (gap-* not space-*)

### Phase 3: Animation Implementation (emil-design-eng)
1. Apply animation decision framework
2. Use correct easing + duration
3. Add button press feedback
4. Implement origin-aware popovers
5. Handle reduced-motion

### Phase 4: Performance Audit (fixing-motion-performance)
1. Verify only transform/opacity animated
2. Check for layout thrashing
3. Use scroll timelines for scroll effects
4. Avoid blur on large surfaces
5. Test with DevTools Performance tab

### Phase 5: Final Review
Run through ALL checklists:
- ✅ Design tokens followed?
- ✅ shadcn composition rules followed?
- ✅ Animation purpose clear?
- ✅ Performance patterns correct?
- ✅ Accessibility handled?

---

## 📋 MASTER CHECKLIST

Before marking work COMPLETE:

**Design (frontend-design):**
- [ ] Design plan created before code
- [ ] Avoids AI default patterns (cream+terracotta, black+acid-green, broadsheet)
- [ ] Has one signature element
- [ ] Typography pairs deliberately
- [ ] Copy is action-oriented and clear

**Structure (shadcn):**
- [ ] Uses existing components (not custom markup)
- [ ] Follows spacing rules (gap-* not space-*)
- [ ] Uses semantic colors (bg-primary not bg-blue-500)
- [ ] Form uses FieldGroup + Field
- [ ] Icons use data-icon attribute

**Polish (emil-design-eng):**
- [ ] Animation decision framework applied
- [ ] Duration ≤ 300ms for UI
- [ ] Uses custom easing (not built-in CSS)
- [ ] Never animates from scale(0)
- [ ] Buttons have active state (scale 0.97)
- [ ] Popovers origin-aware (modals centered)
- [ ] Reduced-motion handled

**Performance (fixing-motion-performance):**
- [ ] Only transform + opacity animated
- [ ] No layout thrashing (reads batched before writes)
- [ ] Scroll effects use View/Scroll Timeline
- [ ] No blur > 8px or on large surfaces
- [ ] CSS animations used under load (not JS)

**If ANY checkbox unchecked → work INCOMPLETE**

---

## 💎 Quality Standards

Ask yourself:
- **Would Emil approve the micro-interactions?**
- **Would shadcn approve the component composition?**
- **Would the performance pass Chrome DevTools audit?**
- **Does the design have a signature element that makes it memorable?**

If answer is NO to any → keep refining.

---

*Skills curated from: Anthropic Claude team, Emil Kowalski (animations.dev, Sonner), shadcn/ui*
