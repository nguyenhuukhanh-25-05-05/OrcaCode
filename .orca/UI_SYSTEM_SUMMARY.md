# 🎨 UI System - Tóm Tắt Nhanh

> **TL;DR:** OrcaCode giờ là Design Engineer AI, không bao giờ tạo UI xấu

---

## ✅ ĐÃ TÍCH HỢP

### 4 Kỹ Năng Vàng:

1. **frontend-design** (Anthropic/Claude)
   - Tạo design có cá tính riêng
   - Tránh AI generic patterns
   - Design tokens + signature element

2. **emil-design-eng** (Emil Kowalski/Sonner)
   - Micro-interactions hoàn hảo
   - Animation ≤300ms, custom easing
   - Button press feedback (scale 0.97)

3. **shadcn** (shadcn/ui)
   - Component-driven structure
   - gap-* not space-y-*
   - Semantic colors (bg-primary)

4. **fixing-motion-performance** (Web Performance)
   - Only transform+opacity
   - No layout thrashing
   - Scroll timelines

### Design System Catalog:

- **getdesign.md** - 73 analyzed design systems
- **Top references:** Linear, Stripe, Vercel, Notion, Tesla, Apple
- **Auto-fetch** real DESIGN.md files

### Style Rotation:

8 phong cách tự động xoay vòng:
- Glassmorphism, Neumorphism, Brutalism, Gradient Mesh
- Cyberpunk, Minimalism+, Organic, Retro/Y2K

---

## 📁 CẤU TRÚC FILES

```
.orca/
├── instructions.md              # MAIN - Read này trước
├── UI_SYSTEM_SUMMARY.md        # THIS FILE
├── README_UI_SYSTEM.md          # Full documentation
│
└── skills/
    ├── ui_quick_reference.md    # CHEAT SHEET (5KB)
    ├── premium_ui_skills.md     # 4 SKILLS (15KB)
    ├── getdesign_reference.md   # INSPIRATION (8KB)
    ├── ui_design.md             # ENCYCLOPEDIA (25KB)
    └── CustomDesign_original.md # SOURCE
```

---

## 🚀 AI AGENT WORKFLOW

### Khi nhận yêu cầu UI:

```
Step 1: Quick Check (30 giây)
  → Read: ui_quick_reference.md
  → Avoid: Prohibited patterns
  → Choose: Component from decision tree

Step 2: Design Inspiration (2 phút)
  → Visit: https://getdesign.md/
  → Pick: 2-3 brands with similar vibe
  → Extract: Colors, fonts, spacing

Step 3: Design Planning (3 phút)
  → Create: Design tokens (color, font, signature)
  → Critique: Is this generic AI? If yes → revise
  → Plan: Layout + component structure

Step 4: Build (10 phút)
  → Structure: shadcn composition rules
  → Animate: ≤300ms, custom easing, transform+opacity
  → Polish: Button press, hover states, reduced-motion

Step 5: Review (2 phút)
  → Check: Master checklist in premium_ui_skills.md
  → Score: 20/20 = pass | <20 = revise
```

**Total: ~17 phút cho component hoàn chỉnh**

---

## ⚡ QUICK RULES

### ✅ ALWAYS DO:

```css
/* Spacing */
flex gap-4                    /* NOT space-y-4 */

/* Size */
size-10                       /* NOT w-10 h-10 */

/* Colors */
bg-primary text-foreground    /* NOT bg-blue-500 */

/* Animations */
transition: transform 200ms cubic-bezier(0.23, 1, 0.32, 1);
transform: scale(0.95);       /* NOT scale(0) */
```

```jsx
/* Forms */
<FieldGroup>
  <Field>
    <FieldLabel>Email</FieldLabel>
    <Input />
  </Field>
</FieldGroup>

/* Icons */
<Button>
  <SearchIcon data-icon="inline-start" />
  Search
</Button>
```

### ❌ NEVER DO:

```css
/* WRONG */
transition: all 300ms ease-in;  /* Specify props, use ease-out */
animation-timing-function: ease-in; /* Feels sluggish */
transform: scale(0);            /* Use scale(0.95) + opacity */
.space-y-4 { }                  /* Use gap-4 */
.bg-blue-500 { }                /* Use bg-primary */
```

```jsx
/* WRONG */
<div className="space-y-4">     {/* Use FieldGroup */}
  <Label>Email</Label>
  <Input />
</div>

<Button>
  <Icon className="w-4 h-4" />  {/* Use data-icon */}
</Button>
```

---

## 🎯 MASTER CHECKLIST

Before marking work COMPLETE:

### Design (frontend-design):
- [ ] Has design tokens (color, font, signature)
- [ ] Avoids AI defaults (cream+terracotta, black+acid-green)
- [ ] Has ONE signature element

### Structure (shadcn):
- [ ] Uses existing components
- [ ] gap-* spacing (not space-y-*)
- [ ] Semantic colors (not raw values)
- [ ] Correct composition (FieldGroup, Card structure)

### Animation (emil-design-eng):
- [ ] Duration ≤ 300ms
- [ ] Custom easing cubic-bezier
- [ ] Never scale(0), never ease-in
- [ ] Button has active state
- [ ] Reduced-motion handled

### Performance (fixing-motion-performance):
- [ ] Only transform+opacity animated
- [ ] No layout thrashing
- [ ] Scroll uses View Timeline
- [ ] Blur ≤ 8px

**Score: 16/16 = PASS | < 16/16 = FAIL**

---

## 🔗 EXTERNAL LINKS

### Always Reference:
- https://getdesign.md/ - Design systems
- https://uiverse.io/ - Component catalog
- https://hover.dev/ - Hover effects
- https://easing.dev/ - Custom easing curves

### npm Packages:
```bash
# Components
npx shadcn@latest add button card dialog

# Animation
npm install framer-motion
npm install gsap

# Icons
npm install lucide-react
```

---

## 📊 SUCCESS METRICS

**OrcaCode UI is SUCCESSFUL when:**
✅ User: "Wow, professional!"
✅ Code: Passes all 4 skills
✅ Performance: 60fps smooth
✅ Design: Has signature element

**OrcaCode UI has FAILED when:**
❌ User: "Looks generic AI"
❌ Animations: Jank or slow
❌ Code: space-y-* or raw colors
❌ Design: No personality

---

## 💡 PRO TIPS

1. **Rotate styles** - Don't use same design twice
2. **Mix inspirations** - Combine 2-3 brands from getdesign.md
3. **Custom easing** - Never use built-in CSS easings
4. **One signature** - Every design needs ONE memorable thing
5. **Performance first** - Only transform+opacity

---

## 🆘 TROUBLESHOOTING

### "Animation feels slow"
→ Check duration > 300ms? Use ease-out not ease-in?

### "Layout shifts"
→ Animating width/height? Use transform instead

### "Design looks generic"
→ Using AI defaults? Add signature element

### "Code is messy"
→ Using space-y-*? Raw colors? Fix composition

---

## 📞 WHERE TO FIND HELP

| Problem | Read This |
|---------|-----------|
| Quick lookup | `ui_quick_reference.md` |
| Detailed rules | `premium_ui_skills.md` |
| Design inspiration | `getdesign_reference.md` |
| Advanced techniques | `ui_design.md` |
| Full documentation | `README_UI_SYSTEM.md` |

---

**Remember: AI agent của bạn giờ là Design Engineer, không phải code generator! 🎨✨**

*OrcaCode UI System v2.0 - 2026*
