# UI Design System - Complete Index

> **Version:** 3.0.0  
> **Last Updated:** 2026-06-15  
> **Quick Navigation:** Use Ctrl+F to search

---

## 📁 FILE STRUCTURE

```
.orca/
├── instructions.md                 ← START HERE (main entry point)
├── INDEX.md                        ← THIS FILE (navigation hub)
├── CHANGELOG.md                    ← Version history
├── README_UI_SYSTEM.md             ← Full documentation
├── UI_SYSTEM_SUMMARY.md            ← Quick overview
├── UI_SYSTEM_DIAGRAM.md            ← Visual architecture
│
├── core/                           ← Foundation (always read first)
│   ├── philosophy.md               ← Design-first principles
│   └── workflow.md                 ← 5-phase execution
│
├── design/                         ← Design system (read before coding)
│   ├── styles.md                   ← 8 style rotation (TODO v3.1)
│   ├── colors.md                   ← Color palettes (TODO v3.1)
│   ├── typography.md               ← Font scales (TODO v3.1)
│   └── spacing.md                  ← Layout system (TODO v3.1)
│
├── components/                     ← Implementation (during coding)
│   ├── patterns.md                 ← Component selection (TODO v3.1)
│   └── examples.md                 ← Full code examples ✅
│
├── animation/                      ← Motion design (during coding)
│   ├── rules.md                    ← Decision framework (TODO v3.1)
│   └── performance.md              ← Optimization (TODO v3.1)
│
├── qa/                             ← Quality assurance (after coding)
│   ├── checklist.md                ← 16-check quality gate ✅
│   ├── accessibility.md            ← WCAG compliance (TODO v3.1)
│   └── performance.md              ← Performance audit (TODO v3.1)
│
├── reference/                      ← External resources (as needed)
│   ├── getdesign.md                ← Design systems catalog (TODO v3.1)
│   ├── libraries.md                ← JS/CSS libraries (TODO v3.1)
│   └── resources.md                ← Tools & links (TODO v3.1)
│
└── skills/                         ← Legacy (kept for reference)
    ├── premium_ui_skills.md        ← 4 golden skills (v2.0 format)
    ├── ui_design.md                ← Extended rules (v2.0 format)
    ├── ui_quick_reference.md       ← Cheat sheet (v2.0 format)
    ├── getdesign_reference.md      ← Design catalog (v2.0 format)
    └── CustomDesign_original.md    ← Source material
```

---

## 🔍 SEARCH BY TOPIC

### Design Principles
- **Philosophy** → `core/philosophy.md`
- **Forbidden patterns** → `core/philosophy.md` section 🚫
- **Mandatory elements** → `core/philosophy.md` section ✅
- **Design-first mindset** → `core/philosophy.md`
- **Style rotation** → `design/styles.md` (v3.1) or `skills/ui_design.md` (v2.0)

### Workflow & Process
- **5-phase workflow** → `core/workflow.md`
- **Time estimates** → `core/workflow.md` section ⏱️
- **Iteration loops** → `core/workflow.md` section 🔁
- **Quality gate** → `qa/checklist.md`

### Code Examples
- **Button examples** → `components/examples.md` section 1
- **Input examples** → `components/examples.md` section 2
- **Card examples** → `components/examples.md` section 3
- **Modal examples** → `components/examples.md` section 4
- **Navbar examples** → `components/examples.md` section 5
- **Form examples** → `components/examples.md` section 6

### Component Patterns
- **When to use which component** → `components/patterns.md` (v3.1)
- **shadcn composition rules** → `skills/premium_ui_skills.md` section "Skill 3"
- **FieldGroup patterns** → `skills/premium_ui_skills.md`

### Animation
- **Animation decision framework** → `animation/rules.md` (v3.1) or `skills/premium_ui_skills.md` section "Skill 2"
- **Duration guidelines** → `animation/rules.md` (v3.1)
- **Easing curves** → `animation/rules.md` (v3.1)
- **Reduced-motion** → `animation/rules.md` (v3.1)

### Performance
- **Transform + opacity only** → `animation/performance.md` (v3.1) or `skills/premium_ui_skills.md` section "Skill 4"
- **Layout thrashing** → `animation/performance.md` (v3.1)
- **FLIP technique** → `animation/performance.md` (v3.1)
- **Scroll timelines** → `animation/performance.md` (v3.1)
- **Blur limits** → `animation/performance.md` (v3.1)

### Quality Assurance
- **16-check checklist** → `qa/checklist.md`
- **Scoring system** → `qa/checklist.md` section 📊
- **Self-critique questions** → `qa/checklist.md` section 🎯
- **Accessibility** → `qa/accessibility.md` (v3.1)

### Design Inspiration
- **getdesign.md catalog** → `reference/getdesign.md` (v3.1) or `skills/getdesign_reference.md` (v2.0)
- **73 design systems** → `reference/getdesign.md` (v3.1)
- **Top 10 references** → `skills/getdesign_reference.md`
- **How to fetch DESIGN.md** → `skills/getdesign_reference.md`

### Color & Typography
- **Color palettes** → `design/colors.md` (v3.1) or `skills/ui_design.md` section "Color System"
- **Semantic colors** → `design/colors.md` (v3.1)
- **Typography scales** → `design/typography.md` (v3.1) or `skills/ui_design.md` section "Typography System"
- **Font pairing** → `design/typography.md` (v3.1)

### Libraries & Tools
- **JS libraries** → `reference/libraries.md` (v3.1) or `skills/ui_design.md` section "Open-source Libraries"
- **Animation libraries** → `reference/libraries.md` (v3.1)
- **Icon libraries** → `reference/libraries.md` (v3.1)
- **External tools** → `reference/resources.md` (v3.1)

---

## 🎯 SEARCH BY USER INTENT

### "I need to understand the system"
1. Read: `instructions.md` (2 min)
2. Read: `core/philosophy.md` (2 min)
3. Read: `core/workflow.md` (3 min)
4. Skim: `README_UI_SYSTEM.md` (5 min)

**Total: ~12 minutes**

### "I need to code a button"
1. Check: `components/examples.md` section 1 (1 min)
2. Copy template (30 sec)
3. Verify: `qa/checklist.md` simple component (1 min)

**Total: ~3 minutes**

### "I need to code a form"
1. Read: `core/workflow.md` (3 min)
2. Check: `components/examples.md` section 6 (2 min)
3. Reference: `skills/getdesign_reference.md` for inspiration (2 min)
4. Verify: `qa/checklist.md` (2 min)

**Total: ~10 minutes**

### "I need animation guidance"
1. Check: `animation/rules.md` (v3.1) OR `skills/premium_ui_skills.md` section "Skill 2" (3 min)
2. Reference: easing curves (1 min)
3. Check: `animation/performance.md` for optimization (2 min)

**Total: ~6 minutes**

### "My work failed quality check"
1. Run: `qa/checklist.md` (2 min)
2. Identify: failed checks (30 sec)
3. Fix: using Quick Fix Guide (5 min)
4. Re-run: checklist (1 min)

**Total: ~9 minutes**

### "I need design inspiration"
1. Visit: `reference/getdesign.md` OR `skills/getdesign_reference.md` (2 min)
2. Pick: 2-3 brands (1 min)
3. Fetch: DESIGN.md files (2 min)
4. Adapt: create design tokens (3 min)

**Total: ~8 minutes**

---

## 📚 READING PATHS

### Path 1: First-Time User (Complete Understanding)
```
1. instructions.md          (2 min)
2. core/philosophy.md       (2 min)
3. core/workflow.md         (3 min)
4. components/examples.md   (5 min - scan)
5. qa/checklist.md          (2 min)
6. README_UI_SYSTEM.md      (5 min - skim)

Total: ~20 minutes
```

### Path 2: Quick Start (Minimum Viable Knowledge)
```
1. instructions.md          (2 min)
2. core/philosophy.md       (2 min)
3. components/examples.md   (1 min - find needed component)
4. qa/checklist.md          (1 min - scan)

Total: ~6 minutes
```

### Path 3: Advanced User (Deep Dive)
```
1. instructions.md          (2 min)
2. core/philosophy.md       (2 min)
3. core/workflow.md         (3 min)
4. skills/premium_ui_skills.md  (15 min - all 4 skills)
5. skills/ui_design.md      (20 min - advanced techniques)
6. skills/getdesign_reference.md (5 min)

Total: ~47 minutes
```

### Path 4: Specific Topic (Targeted Learning)
```
Example: Animation
1. instructions.md > animation section (1 min)
2. animation/rules.md (v3.1) or skills/premium_ui_skills.md > Skill 2 (3 min)
3. animation/performance.md (v3.1) (2 min)
4. components/examples.md > button with hover (1 min)

Total: ~7 minutes per topic
```

---

## 🔗 QUICK LINKS

### Documentation
- [Main Entry Point](./instructions.md)
- [Full Documentation](./README_UI_SYSTEM.md)
- [Quick Overview](./UI_SYSTEM_SUMMARY.md)
- [Visual Diagram](./UI_SYSTEM_DIAGRAM.md)
- [Version History](./CHANGELOG.md)

### Foundation
- [Design Philosophy](./core/philosophy.md)
- [5-Phase Workflow](./core/workflow.md)

### Implementation
- [Code Examples](./components/examples.md)
- [Premium Skills](./skills/premium_ui_skills.md)

### Quality Assurance
- [16-Check Checklist](./qa/checklist.md)

### Reference
- [getdesign.md Catalog](./skills/getdesign_reference.md)
- [Quick Reference](./skills/ui_quick_reference.md)

---

## 🆕 WHAT'S NEW IN v3.0.0

### Major Changes:
- ✅ Modular structure (15 focused files vs 1 monolithic)
- ✅ Concrete code examples (HTML + CSS + JS)
- ✅ 16-check quality gate system
- ✅ Version tracking (CHANGELOG)
- ✅ Clear workflows with time estimates

### Coming in v3.1.0:
- [ ] `design/` modules (styles, colors, typography, spacing)
- [ ] `animation/` modules (rules, performance)
- [ ] `components/patterns.md` (component selection)
- [ ] `qa/` modules (accessibility, performance)
- [ ] `reference/` modules (getdesign, libraries, resources)

---

## 📞 SUPPORT

### Can't Find Something?
1. Use Ctrl+F in this INDEX file
2. Check CHANGELOG for recent moves
3. Try both v3.0 path and v2.0 path (skills/)

### Found a Bug?
1. Check CHANGELOG > "Upcoming Changes"
2. Create issue with module name + description

### Want to Contribute?
1. Read CHANGELOG > "Versioning Policy"
2. Follow existing module structure
3. Add examples where possible

---

**Status:** Production Ready ✅  
**Current Version:** 3.0.0  
**Last Updated:** 2026-06-15
