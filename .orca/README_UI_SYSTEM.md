# 🎨 OrcaCode UI Design System

> **Mục tiêu:** Biến AI agent thành Design Engineer chuyên nghiệp, tạo giao diện đẹp mặc định

---

## 📚 CẤU TRÚC HỆ THỐNG

```
.orca/
├── instructions.md                    # MAIN - Design-first mandate
├── README_UI_SYSTEM.md               # THIS FILE - Overview
│
├── skills/
│   ├── ui_design.md                  # COMPREHENSIVE - Full design rules
│   ├── premium_ui_skills.md          # ESSENTIAL - 4 golden skills
│   ├── ui_quick_reference.md         # QUICK - Fast lookup
│   ├── getdesign_reference.md        # INSPIRATION - Real design systems
│   └── CustomDesign_original.md      # SOURCE - Original from Anthropic
```

---

## 🎯 USAGE GUIDE

### Cho AI Agent:

**Khi nhận yêu cầu UI, đọc theo thứ tự:**

1. **ui_quick_reference.md** (1 phút)
   - Quick checklist
   - Prohibited patterns
   - Component decision tree

2. **premium_ui_skills.md** (5 phút)
   - 4 phases workflow
   - Detailed rules
   - Integration checklist

3. **getdesign_reference.md** (2 phút)
   - Find 2-3 similar brands
   - Extract color/typography/patterns
   - Adapt (don't copy)

4. **ui_design.md** (On-demand)
   - Advanced techniques
   - JS libraries catalog
   - Performance optimization

### Cho Developer:

**Setup:**
```bash
# AI sẽ tự động đọc các file này khi code UI
# Không cần làm gì thêm
```

**Override behavior:**
```bash
# Nếu muốn AI tạo UI đơn giản (không polish):
"Tạo UI đơn giản, không cần animations"

# Nếu muốn AI tập trung performance:
"Tạo UI với performance tối ưu, ít animation"
```

---

## 🔥 CORE PRINCIPLES

### 1. Design-First Philosophy

**AI Agent KHÔNG BAO GIỜ tạo UI xấu.**

Mọi component đều phải:
- Có design tokens rõ ràng (color, typography, signature)
- Avoid AI default patterns (cream+terracotta, black+acid-green)
- Có ít nhất 1 signature element đáng nhớ

### 2. The 4 Golden Skills

#### Skill 1: Frontend-Design (The Soul)
- **From:** Anthropic (Claude team)
- **Purpose:** Distinctive, non-templated design
- **Key:** Brainstorm → Plan → Critique → Build

#### Skill 2: Emil-Design-Eng (The Polish)
- **From:** Emil Kowalski (Sonner, animations.dev)
- **Purpose:** Perfect micro-interactions
- **Key:** Animation decision framework, ≤300ms, custom easing

#### Skill 3: Shadcn (The Structure)
- **From:** shadcn/ui
- **Purpose:** Component-driven, maintainable code
- **Key:** gap-* not space-y-*, semantic colors, FieldGroup pattern

#### Skill 4: Fixing-Motion-Performance (The Quality)
- **From:** Web performance best practices
- **Purpose:** Smooth 60fps animations
- **Key:** Only transform+opacity, no layout thrashing, scroll timelines

### 3. Mandatory Workflow

```
EVERY UI component MUST go through:

Phase 1: Design Planning (frontend-design)
  ├─ Create design tokens
  ├─ Self-critique against AI defaults
  └─ Get signature element

Phase 2: Component Structure (shadcn)
  ├─ Search existing components
  ├─ Use correct composition patterns
  └─ Apply semantic colors

Phase 3: Animation Implementation (emil-design-eng)
  ├─ Apply decision framework
  ├─ Use custom easing
  └─ Handle reduced-motion

Phase 4: Performance Audit (fixing-motion-performance)
  ├─ Verify only transform+opacity
  ├─ Check for layout thrashing
  └─ Use scroll timelines

Phase 5: Final Review
  └─ Run through ALL checklists
```

---

## 📖 FILE PURPOSES

### instructions.md
**Role:** Main orchestrator  
**Contains:**
- Design-first mandate
- Style rotation system (8 styles)
- getdesign.md integration
- 5-step execution workflow
- Quality gate checklist

**Read when:** Starting any UI work

### premium_ui_skills.md
**Role:** The Bible  
**Contains:**
- Full documentation of 4 skills
- Integration workflow
- Master checklist
- Quality standards

**Read when:** Need detailed rules or patterns

### ui_quick_reference.md
**Role:** Cheat sheet  
**Contains:**
- Quick decision trees
- Prohibited patterns (❌ vs ✅)
- Component selection guide
- Self-critique questions

**Read when:** Need fast lookup during coding

### ui_design.md
**Role:** Encyclopedia  
**Contains:**
- Responsive design rules
- Color systems (light/dark)
- Typography scales
- JS libraries catalog
- Advanced CSS techniques
- Performance optimization
- Accessibility requirements

**Read when:** Need specific technique details

### getdesign_reference.md
**Role:** Inspiration library  
**Contains:**
- 73 design systems (Linear, Stripe, Vercel, Tesla, etc.)
- How to fetch & analyze DESIGN.md files
- Top 10 most referenced designs
- Design decision matrix

**Read when:** Need real-world design inspiration

---

## 🚀 QUICK START

### Scenario 1: Tạo Landing Page

```
1. Read: ui_quick_reference.md (workflow template)
2. Visit: https://getdesign.md/ 
3. Pick: Stripe (for SaaS) + Framer (for motion) + Vercel (for precision)
4. Extract: Colors, fonts, spacing from 3 designs
5. Create: Design tokens with unique signature element
6. Build: Following shadcn composition rules
7. Animate: Using emil's decision framework (≤300ms)
8. Audit: Performance (only transform+opacity)
9. Review: premium_ui_skills.md master checklist
```

### Scenario 2: Tạo Dashboard

```
1. Reference: Linear (ultra-minimal) + Notion (warm)
2. Design tokens: Dark #17171A + Purple #5E6AD2
3. Components: Sidebar + Card + Chart (shadcn)
4. Animations: Stagger 50ms, ease-out 200ms
5. Performance: Scroll timeline for reveals
```

### Scenario 3: Tạo Form

```
1. Structure: FieldGroup + Field (NOT div + Label)
2. Validation: data-invalid + aria-invalid
3. Inputs: InputGroup + InputGroupInput
4. Button: active scale(0.97)
5. Feedback: sonner toast
```

---

## 🎨 DESIGN STYLE ROTATION

AI automatically rotates through 8 styles:

1. **Glassmorphism Pro** - Backdrop blur, transparency
2. **Neumorphism** - Soft shadows, monochrome
3. **Brutalism** - High contrast, thick borders
4. **Gradient Mesh** - Layered gradients, blurred blobs
5. **Cyberpunk/Neon** - Dark + neon accents
6. **Minimalism+** - Whitespace, micro-interactions
7. **Organic/Nature** - Earthy colors, soft shapes
8. **Retro/Y2K** - Saturated colors, chunky elements

**Purpose:** Variety across projects, avoid repetition

---

## 🔗 EXTERNAL RESOURCES

### Primary References (Luôn Dùng):
- **getdesign.md** - 73 analyzed design systems
- **GitHub repo** - https://github.com/VoltAgent/awesome-design-md

### Component Catalogs:
- **Uiverse.io** - 200+ buttons, 150+ cards, ready-to-copy
- **CodePen** - Millions of live demos
- **Hover.dev** - 100+ hover effects
- **Animista** - CSS animation generator

### Libraries Priority:
- **shadcn/ui** - Base component system
- **Framer Motion** - React animations
- **GSAP** - Complex timelines
- **Lucide Icons** - Clean icon set
- **Tailwind CSS** - Utility-first styling

---

## 📊 QUALITY METRICS

### Every Component Must Pass:

**Design Quality:**
- [ ] Not generic AI default
- [ ] Has signature element
- [ ] Fonts paired deliberately
- [ ] Copy is action-oriented

**Code Quality:**
- [ ] Uses existing components (not custom markup)
- [ ] gap-* spacing (not space-y-*)
- [ ] Semantic colors (not raw values)
- [ ] Correct composition (FieldGroup, Card structure)

**Animation Quality:**
- [ ] Purpose is clear (not just "looks cool")
- [ ] Duration ≤ 300ms for UI
- [ ] Custom easing (not built-in)
- [ ] Never scale(0), never ease-in
- [ ] Reduced-motion handled

**Performance Quality:**
- [ ] Only transform+opacity animated
- [ ] No layout thrashing
- [ ] Scroll uses View Timeline
- [ ] Blur ≤ 8px
- [ ] CSS animations under load

**Score: 20/20 = COMPLETE | < 20/20 = INCOMPLETE**

---

## 🎓 LEARNING PATH

### Week 1: Fundamentals
- Read: ui_quick_reference.md fully
- Study: Prohibited patterns
- Practice: 5 button variations

### Week 2: Skills Deep Dive
- Read: premium_ui_skills.md
- Study: Animation decision framework
- Practice: Modal with perfect timing

### Week 3: Real-World Patterns
- Read: getdesign_reference.md
- Analyze: 3 brands from getdesign.md
- Practice: Landing page inspired by Stripe+Framer

### Week 4: Advanced Techniques
- Read: ui_design.md selectively
- Study: Performance optimization
- Practice: Dashboard with scroll effects

---

## 🐛 DEBUGGING GUIDE

### Problem: Animations feel slow
**Check:**
- Duration > 300ms? Reduce to 200ms
- Using ease-in? Change to ease-out
- Animating width/height? Use transform instead

### Problem: Layout shifts/jank
**Check:**
- Reading layout during animation? Batch reads before writes
- Animating inherited CSS vars? Update transform directly
- Heavy blur? Reduce to ≤8px

### Problem: Design looks generic
**Check:**
- Using cream #F4F1EA + terracotta? Pick project-specific colors
- No signature element? Add ONE memorable thing
- Default fonts? Choose deliberately

### Problem: Code is messy
**Check:**
- Using space-y-*? Change to gap-*
- Raw div + Label? Use FieldGroup + Field
- Raw color values? Use semantic tokens

---

## 📞 SUPPORT

### For AI Agent Issues:
Check:
1. ui_quick_reference.md - Fast patterns
2. premium_ui_skills.md - Detailed rules
3. instructions.md - Core mandate

### For Design Inspiration:
Visit:
1. https://getdesign.md/ - Design systems
2. https://uiverse.io/ - Component library
3. https://dribbble.com/ - Visual reference

### For Performance Issues:
Study:
- fixing-motion-performance in premium_ui_skills.md
- Performance section in ui_design.md

---

## 🎯 SUCCESS CRITERIA

**OrcaCode UI is successful when:**

✅ User says: "Wow, this looks professional"  
✅ Code passes all 4 skill checks  
✅ Animations feel smooth (60fps)  
✅ Design is memorable (has signature)  
✅ Components are maintainable (shadcn patterns)

**OrcaCode UI has FAILED when:**

❌ User says: "This looks like generic AI"  
❌ Animations jank or feel slow  
❌ Code uses space-y-* or raw colors  
❌ Performance issues (animating layout)  
❌ No distinctive personality

---

## 🚧 ROADMAP

### Current Version: 2.0
- ✅ 4 golden skills integrated
- ✅ getdesign.md reference system
- ✅ 8 style rotation
- ✅ Performance rules

### Future Enhancements:
- [ ] Video tutorials for each skill
- [ ] Interactive examples
- [ ] Auto-generate design tokens from screenshots
- [ ] Performance profiler integration
- [ ] A/B testing for animation timings

---

## 📄 LICENSE

Skills curated from:
- **Anthropic** - frontend-design philosophy
- **Emil Kowalski** - animation excellence (animations.dev)
- **shadcn** - component architecture (shadcn/ui)
- **Web Platform** - performance best practices

All external resources retain their original licenses.

---

**Built with ❤️ for beautiful, performant UI**

*Last updated: 2026 - OrcaCode v2.0*
