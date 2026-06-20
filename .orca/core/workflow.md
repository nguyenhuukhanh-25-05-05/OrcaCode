# Core Workflow - 5-Phase Execution

> **Module:** Foundation  
> **Read Time:** 3 minutes  
> **When:** Before complex UI work (forms, pages, dashboards)

---

## 🔄 THE 5 PHASES

Every UI component goes through exactly 5 phases:

```
Phase 1: Design Planning      (frontend-design)
Phase 2: Component Structure   (shadcn patterns)
Phase 3: Animation Implementation (emil-design-eng)
Phase 4: Performance Audit     (fixing-motion-performance)
Phase 5: Final Review          (all checklists)
```

**Simple components** (button, input): Phases 1-2-5 (skip 3-4)  
**Complex components** (form, dashboard): All 5 phases

---

## 📋 PHASE 1: DESIGN PLANNING

**Time:** 5 minutes  
**Reference:** `design/styles.md`, `reference/getdesign.md`

### Steps:

1. **Identify style** (from 8 rotation)
   ```
   Last used: Glassmorphism
   Next: Neumorphism ✓
   ```

2. **Find inspiration** (2-3 brands from getdesign.md)
   ```
   Project type: SaaS Dashboard
   References: Linear + Notion + Stripe
   ```

3. **Create design tokens**
   ```markdown
   ## Design Tokens
   
   **Colors:**
   - Primary: Deep Purple #6366f1 - CTA buttons, links
   - Accent: Cyan #06b6d4 - Highlights, success states
   - Neutrals: Slate scale - Backgrounds, text
   
   **Typography:**
   - Display: Inter Bold - Headings (48px → 32px mobile)
   - Body: Inter Regular - Content (16px)
   - Mono: JetBrains Mono - Code blocks
   
   **Signature Element:**
   Floating action buttons with ripple effect
   ```

4. **Self-critique**
   ```
   ❓ Is this cream #F4F1EA + terracotta? NO ✓
   ❓ Is this black + acid green? NO ✓
   ❓ Does it have signature element? YES ✓
   ```

### Output:
- Design tokens documented
- Signature element defined
- Passed self-critique

---

## 📋 PHASE 2: COMPONENT STRUCTURE

**Time:** 10 minutes  
**Reference:** `components/patterns.md`, `components/examples.md`

### Steps:

1. **Search existing components**
   ```
   Need: Login form
   Check: Input, Button, Card
   Found: All 3 exist ✓
   ```

2. **Apply composition patterns**
   ```jsx
   ❌ WRONG:
   <div className="space-y-4">
     <Label>Email</Label>
     <Input />
   </div>
   
   ✅ CORRECT:
   <FieldGroup>
     <Field>
       <FieldLabel htmlFor="email">Email</FieldLabel>
       <Input id="email" />
     </Field>
   </FieldGroup>
   ```

3. **Use semantic colors**
   ```jsx
   ❌ WRONG: className="bg-blue-500"
   ✅ CORRECT: className="bg-primary"
   
   ❌ WRONG: className="text-gray-600"
   ✅ CORRECT: className="text-muted-foreground"
   ```

4. **Apply spacing rules**
   ```jsx
   ❌ WRONG: className="space-y-4"
   ✅ CORRECT: className="flex flex-col gap-4"
   
   ❌ WRONG: className="w-10 h-10"
   ✅ CORRECT: className="size-10"
   ```

### Output:
- Correct component composition
- Semantic colors applied
- Proper spacing (gap-* not space-*)

---

## 📋 PHASE 3: ANIMATION IMPLEMENTATION

**Time:** 5 minutes  
**Reference:** `animation/rules.md`

### Steps:

1. **Decision framework**
   ```
   ❓ Should this animate?
      → Frequency: Occasional (modal open)
      → Decision: YES, 200-500ms ✓
   
   ❓ What easing?
      → Element entering? YES
      → Use: ease-out (cubic-bezier(0.23, 1, 0.32, 1))
   
   ❓ How fast?
      → Modal: 300ms ✓
   ```

2. **Apply animations**
   ```jsx
   <motion.div
     initial={{ opacity: 0, scale: 0.95 }}
     animate={{ opacity: 1, scale: 1 }}
     exit={{ opacity: 0, scale: 0.95 }}
     transition={{
       duration: 0.3,
       ease: [0.23, 1, 0.32, 1]
     }}
   >
   ```

3. **Add button feedback**
   ```jsx
   <button className="transition-transform active:scale-[0.97]">
   ```

4. **Handle reduced-motion**
   ```jsx
   const shouldReduceMotion = useReducedMotion()
   const duration = shouldReduceMotion ? 0 : 0.3
   ```

### Output:
- Duration ≤ 300ms for UI
- Custom easing applied
- Button has active state
- Reduced-motion handled

---

## 📋 PHASE 4: PERFORMANCE AUDIT

**Time:** 3 minutes  
**Reference:** `animation/performance.md`

### Steps:

1. **Check animated properties**
   ```
   ✅ Only transform + opacity? YES
   ❌ Animating width/height/padding? NO ✓
   ```

2. **Verify no layout thrashing**
   ```js
   // ❌ WRONG: Read + Write + Read + Write
   el.style.left = el.getBoundingClientRect().left + 10 + 'px'
   
   // ✅ CORRECT: Read all, then Write all (FLIP)
   const first = el.getBoundingClientRect()
   el.classList.add('moved')
   const last = el.getBoundingClientRect()
   el.style.transform = `translateX(${first.left - last.left}px)`
   requestAnimationFrame(() => {
     el.style.transition = 'transform 0.3s'
     el.style.transform = ''
   })
   ```

3. **Check scroll handling**
   ```css
   /* ❌ WRONG: JS scroll listener */
   window.addEventListener('scroll', () => ...)
   
   /* ✅ CORRECT: Scroll timeline */
   .reveal {
     animation: fade-in linear;
     animation-timeline: view();
   }
   ```

4. **Verify blur usage**
   ```
   ✅ Blur ≤ 8px? YES (backdrop-blur-md = 12px ⚠️ → reduce to blur-sm)
   ✅ Not on large surface? YES ✓
   ```

### Output:
- Only transform+opacity animated
- No layout thrashing
- Scroll uses View Timeline
- Blur ≤ 8px

---

## 📋 PHASE 5: FINAL REVIEW

**Time:** 2 minutes  
**Reference:** `qa/checklist.md`

### Steps:

1. **Run master checklist** (16 checks)
   ```
   Design (4/4):
   ✓ Has design tokens
   ✓ Avoids AI defaults
   ✓ Has signature element
   ✓ Fonts paired deliberately
   
   Structure (4/4):
   ✓ Uses existing components
   ✓ gap-* spacing
   ✓ Semantic colors
   ✓ Correct composition
   
   Animation (4/4):
   ✓ Duration ≤ 300ms
   ✓ Custom easing
   ✓ Never scale(0) or ease-in
   ✓ Reduced-motion
   
   Performance (4/4):
   ✓ Only transform+opacity
   ✓ No layout thrashing
   ✓ Scroll timeline
   ✓ Blur ≤ 8px
   
   TOTAL: 16/16 = PASS ✅
   ```

2. **Self-critique questions**
   ```
   ❓ Would Apple approve? YES
   ❓ Would Linear approve? YES
   ❓ Would Stripe approve? YES
   ❓ Would Framer approve? YES
   ```

3. **Screenshot review** (if tool available)
   ```
   - Take screenshot
   - Check visual balance
   - Verify spacing consistency
   - Confirm color harmony
   ```

### Output:
- Scored 16/16 on checklist
- Passed self-critique
- Ready to present

---

## ⏱️ TIME ESTIMATES

### Simple Component (Button):
```
Phase 1: Design Planning        → 2 min
Phase 2: Component Structure    → 3 min
Phase 3: (Skip for simple)      → 0 min
Phase 4: (Skip for simple)      → 0 min
Phase 5: Final Review           → 1 min
─────────────────────────────────────────
TOTAL:                            6 min
```

### Medium Component (Form):
```
Phase 1: Design Planning        → 5 min
Phase 2: Component Structure    → 10 min
Phase 3: Animation              → 5 min
Phase 4: Performance            → 3 min
Phase 5: Final Review           → 2 min
─────────────────────────────────────────
TOTAL:                           25 min
```

### Complex Component (Dashboard):
```
Phase 1: Design Planning        → 10 min
Phase 2: Component Structure    → 20 min
Phase 3: Animation              → 10 min
Phase 4: Performance            → 5 min
Phase 5: Final Review           → 5 min
─────────────────────────────────────────
TOTAL:                           50 min
```

---

## 🔁 ITERATION LOOPS

### If Phase 5 Fails (Score < 16/16):

```
Score: 14/16 (2 failures)

Failed:
- [ ] Avoids AI defaults (using cream #F4F1EA)
- [ ] Custom easing (using ease-in)

Action:
1. Fix failed items
2. Re-run Phase 5
3. If pass → Continue
4. If fail again → Revise Phase 1 or 3
```

**Never present work with score < 16/16.**

---

## 📊 WORKFLOW DIAGRAM

```
START
  ↓
Phase 1: Design Planning
  ├─ Pick style from rotation
  ├─ Find 2-3 brand references
  ├─ Create design tokens
  └─ Self-critique → PASS? → Yes ↓
  ↓
Phase 2: Component Structure
  ├─ Search existing components
  ├─ Apply composition patterns
  ├─ Use semantic colors
  └─ Apply spacing rules → Done ↓
  ↓
Phase 3: Animation Implementation
  ├─ Apply decision framework
  ├─ Use custom easing ≤300ms
  ├─ Add button feedback
  └─ Handle reduced-motion → Done ↓
  ↓
Phase 4: Performance Audit
  ├─ Check animated properties
  ├─ Verify no layout thrashing
  ├─ Check scroll handling
  └─ Verify blur usage → Done ↓
  ↓
Phase 5: Final Review
  ├─ Run master checklist (16 checks)
  ├─ Self-critique questions
  └─ Score: 16/16? 
       ├─ YES → OUTPUT (Complete)
       └─ NO → LOOP BACK (Fix failures)
```

---

## 🎯 SUCCESS CRITERIA

**Work is COMPLETE when:**
✅ All 5 phases executed  
✅ Score 16/16 on checklist  
✅ Passed all self-critique questions  
✅ Ready to present to user

**Work is INCOMPLETE when:**
❌ Skipped any phase  
❌ Score < 16/16  
❌ Failed self-critique  
❌ User would say "looks generic"

---

## 💡 PRO TIPS

1. **Don't skip phases** - Even if you think you know the answer
2. **Document tokens** - Write them down in Phase 1, reference in Phase 2-3
3. **Use examples** - Check `components/examples.md` for templates
4. **Test incrementally** - Don't wait until Phase 5 to find issues
5. **Screenshot often** - Visual check reveals what code review misses

---

**Next Modules:**
- `design/styles.md` - 8 design style rotation
- `components/patterns.md` - Component selection guide
- `animation/rules.md` - Animation decision framework
