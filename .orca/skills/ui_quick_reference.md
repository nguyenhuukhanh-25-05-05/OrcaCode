# UI Quick Reference - Ghi Nhớ Nhanh

> **Sử dụng khi:** Bất kỳ tác vụ UI nào

---

## ⚡ TƯ DUY TRƯỚC KHI CODE

### 1. Frontend-Design (The Soul)
```
❓ Is this a generic AI default?
   → Cream #F4F1EA + terracotta? 
   → Black + acid green?
   → Broadsheet + hairlines?
   
   IF YES → REVISE to be project-specific
   
✅ Create signature element
✅ Pair fonts deliberately  
✅ Ground in subject matter
```

### 2. Emil-Design-Eng (The Polish)
```
❓ Should this animate?
   → 100x/day? NO ANIMATION
   → Keyboard action? NO ANIMATION
   → Modal/toast? YES (200-500ms)
   
✅ Custom easing: cubic-bezier(0.23, 1, 0.32, 1)
✅ Button active: scale(0.97)
✅ Never scale(0) → use scale(0.95) + opacity
✅ Popover: origin-aware | Modal: center
```

### 3. Shadcn (The Structure)
```
✅ Search existing components FIRST
✅ gap-* (NOT space-y-*)
✅ size-10 (NOT w-10 h-10)
✅ bg-primary (NOT bg-blue-500)
✅ FieldGroup + Field (forms)
✅ data-icon on Button icons
```

### 4. Fixing-Motion-Performance (The Quality)
```
✅ ONLY animate: transform + opacity
❌ NEVER animate: width, height, padding, layout
✅ Batch reads before writes (FLIP technique)
✅ Scroll: use View Timeline (not JS listener)
❌ Blur > 8px or on large surface
```

---

## 🎯 WORKFLOW TEMPLATE

```markdown
## Step 1: Design Tokens
- Primary: [color] #hex - [usage]
- Accent: [color] #hex - [usage]  
- Display font: [name] - [when]
- Body font: [name] - [when]
- Signature: [ONE memorable element]

## Step 2: Component Structure
- Use: [existing component names]
- Layout: flex gap-4 (NOT space-y-4)
- Colors: bg-background text-foreground

## Step 3: Animation Plan
- Duration: [100-500ms based on element type]
- Easing: cubic-bezier(0.23, 1, 0.32, 1)
- Properties: transform + opacity ONLY

## Step 4: Performance Check
- [ ] Only transform/opacity animated
- [ ] No layout reads during animation
- [ ] Scroll uses View Timeline
- [ ] Blur ≤ 8px
```

---

## 🚨 PROHIBITED PATTERNS

### Never Do These:

```css
/* ❌ WRONG */
.element {
  transition: all 300ms ease-in;
  animation-timing-function: ease-in;
}
.space-y-4 { } /* Use gap-* */
.w-10.h-10 { } /* Use size-10 */
.bg-blue-500 { } /* Use bg-primary */
.entering { transform: scale(0); } /* Use scale(0.95) + opacity */

/* ✅ CORRECT */
.element {
  transition: transform 200ms cubic-bezier(0.23, 1, 0.32, 1), 
              opacity 200ms cubic-bezier(0.23, 1, 0.32, 1);
}
.flex.gap-4 { }
.size-10 { }
.bg-primary { }
.entering { transform: scale(0.95); opacity: 0; }
```

```jsx
{/* ❌ WRONG */}
<div className="space-y-4">
  <Label>Email</Label>
  <Input />
</div>

{/* ✅ CORRECT */}
<FieldGroup>
  <Field>
    <FieldLabel htmlFor="email">Email</FieldLabel>
    <Input id="email" />
  </Field>
</FieldGroup>

{/* ❌ WRONG */}
<Button>
  <SearchIcon className="w-4 h-4" />
  Search
</Button>

{/* ✅ CORRECT */}
<Button>
  <SearchIcon data-icon="inline-start" />
  Search
</Button>
```

---

## 📊 COMPONENT DECISION TREE

```
Need a button?
  → <Button variant="primary|outline|ghost" />

Need form input?
  → Text: <FieldGroup><Field><FieldLabel/><Input/></Field></FieldGroup>
  → Select: <Select><SelectTrigger/><SelectContent><SelectGroup><SelectItem/></SelectGroup></SelectContent></Select>
  → Toggle 2-7: <ToggleGroup><ToggleGroupItem/></ToggleGroup>

Need modal/overlay?
  → Modal: <Dialog><DialogTrigger/><DialogContent><DialogTitle/></DialogContent></Dialog>
  → Side panel: <Sheet>
  → Bottom: <Drawer>
  → Confirm: <AlertDialog>

Need feedback?
  → Toast: import { toast } from 'sonner'; toast('Message')
  → Alert: <Alert><AlertTitle/><AlertDescription/></Alert>
  → Loading: <Skeleton /> or <Spinner />

Need empty state?
  → <Empty />

Need callout?
  → <Alert variant="info|warning|error" />
```

---

## ⏱️ ANIMATION DURATION CHEATSHEET

| Element | Duration | Easing |
|---------|----------|--------|
| Button press | 100-160ms | ease-out |
| Tooltip | 125-200ms | ease-out |
| Dropdown/Select | 150-250ms | ease-out |
| Modal/Sheet | 200-500ms | ease-out |
| Keyboard action | 0ms | none |

---

## 🎨 SELF-CRITIQUE QUESTIONS

Before presenting work:

1. **Design:** Does this look like generic AI output?
2. **Animation:** Did I use ease-in? (if yes → fix)
3. **Structure:** Did I use space-y-* instead of gap-*? (if yes → fix)
4. **Performance:** Did I animate width/height? (if yes → fix)
5. **Signature:** Can someone remember ONE unique thing about this design?

**If ANY answer is wrong → REVISE before showing user**

---

## 💡 QUICK WINS

### Instant Polish Additions:

```css
/* Button press feedback */
.button:active {
  transform: scale(0.97);
}

/* Smooth transitions */
* {
  transition: transform 200ms cubic-bezier(0.23, 1, 0.32, 1);
}

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  * { animation-duration: 0.01ms !important; }
}

/* Touch device hovers */
@media (hover: hover) and (pointer: fine) {
  .button:hover { transform: scale(1.05); }
}
```

---

## 🔗 FULL DOCUMENTATION

For complete details, see:
- `.orca/skills/premium_ui_skills.md` - Full 4 skills guide
- `.orca/instructions.md` - Main design mandate
- `.orca/skills/ui_design.md` - Extended UI patterns
- `.orca/skills/getdesign_reference.md` - Real-world design systems

---

**Remember: These are not suggestions. These are RULES.**

Every UI component must pass ALL 4 skill checks before completion.
