# UI Design Master Ruleset — OrcaCode Agent Instructions

> ⚠️ **QUAN TRỌNG:** Hệ thống design modules mới đã được tạo tại `.orca/design/` và `.orca/animation/`.
> **BẮT BUỘC đọc `.orca/instructions.md` TRƯỚC KHI code UI.**

## 1. RESPONSIVE DESIGN — MANDATORY FOR ALL UI WORK

Every single page, component, and layout created by the agent MUST support all three device categories below. This is not optional. The agent must test and verify layout correctness at all breakpoints before declaring work complete.

### 1.1 Required Breakpoints

| Device Category | Min Width | Max Width | Tailwind Prefix | Typical Screen |
|-----------------|-----------|-----------|-----------------|----------------|
| **MOBILE** | 320px | 767px | default (no prefix) | iPhone SE, Galaxy S23 |
| **TABLET** | 768px | 1023px | `md:` | iPad, iPad Mini, Galaxy Tab |
| **LAPTOP / DESKTOP** | 1024px | 1919px | `lg:` | MacBook 13-15", Windows laptop, 1080p monitors |
| **LARGE DESKTOP** | 1920px+ | — | `xl:` `2xl:` | 4K monitors, ultra-wide displays |

### 1.2 Mobile-First Layout Rules

The agent MUST write CSS/Tailwind starting from mobile and scaling up. This means:
- Base classes (no prefix) define the MOBILE layout
- `md:` overrides apply for TABLET
- `lg:` overrides apply for LAPTOP/DESKTOP
- `xl:` and `2xl:` overrides apply for LARGE DISPLAYS

### 1.3 Specific Layout Requirements Per Device

**MOBILE (320px - 767px):**
- Single column layout for all content sections
- Text size: body minimum 16px (text-base), headings scale down proportionally
- Touch targets: all clickable elements minimum 44x44px (Tailwind: min-h-[44px] min-w-[44px])
- Buttons should be full-width or near full-width (w-full or w-[90%])
- Navigation must collapse into hamburger menu or bottom tab bar
- Padding: px-4 (16px) on sides, py-6 (24px) between sections
- Images max-width: 100% of container
- No horizontal scrollbars allowed — if content overflows, wrap or scroll vertically
- Card grid: 1 column (grid-cols-1)
- Font sizes: headings max text-2xl (24px), body text-base (16px)

**TABLET (768px - 1023px) — `md:` prefix:**
- Navigation can expand to horizontal bar if space permits (md:flex md:flex-row)
- Card grid: 2 columns (md:grid-cols-2)
- Side padding: md:px-8 (32px)
- Buttons can return to natural width (md:w-auto)
- Section padding: md:py-12 (48px)
- Hero heading: md:text-4xl or md:text-5xl

**LAPTOP/DESKTOP (1024px+) — `lg:` prefix:**
- Full horizontal navigation bar (lg:flex lg:flex-row)
- Card grid: 3-4 columns (lg:grid-cols-3 or lg:grid-cols-4)
- Side padding: lg:px-16 or lg:px-24
- Maximum content width: max-w-7xl (1280px) centered with mx-auto
- Hero heading: lg:text-6xl or lg:text-7xl
- Two-column layouts allowed for text+image sections (lg:grid-cols-2)
- Sticky sidebars or fixed headers if appropriate

### 1.4 Responsive Testing Checklist (Agent Must Self-Verify)

Before marking work as complete, the agent must verify:
- [ ] No horizontal scrollbar on any viewport width
- [ ] Text does not overflow or get cut off
- [ ] All buttons and links are tappable on mobile (44x44px minimum)
- [ ] Navigation menu works on mobile (hamburger or tabs)
- [ ] Images scale correctly and don't exceed viewport
- [ ] Forms are usable on mobile (inputs full-width, labels above)
- [ ] Tables either scroll horizontally or stack vertically on mobile
- [ ] Modals and dialogs fit within mobile screen (max-w-[90vw] max-h-[80vh])
- [ ] Spacing between elements adjusts proportionally across breakpoints
- [ ] Font sizes are readable at all sizes (no text smaller than 14px)

---

## 2. COLOR SYSTEM

### 2.1 Light Theme Colors (Default — when no theme is specified)

| Element | Tailwind Class | Hex Value | Usage |
|---------|---------------|-----------|-------|
| Page background | bg-white or bg-gray-50 | #ffffff or #f9fafb | Main page background |
| Card/Section background | bg-white | #ffffff | Cards, panels, containers |
| Primary text | text-gray-900 | #111827 | Headings, important text |
| Secondary text | text-gray-600 | #4b5563 | Body text, descriptions |
| Muted text | text-gray-400 | #9ca3af | Captions, timestamps, metadata |
| Accent color | text-blue-600 bg-blue-600 | #2563eb | Buttons, links, highlights (use 1 accent max) |
| Border light | border-gray-200 | #e5e7eb | Card borders, separators |
| Border subtle | border-gray-100 | #f3f4f6 | Very light borders |
| Success | text-green-600 bg-green-50 | #16a34a / #f0fdf4 | Success messages, confirmations |
| Error | text-red-600 bg-red-50 | #dc2626 / #fef2f2 | Error messages, destructive actions |
| Warning | text-amber-600 bg-amber-50 | #d97706 / #fffbeb | Warning messages |

### 2.2 Dark Theme Colors (When explicitly requested)

| Element | Tailwind Class | Hex Value |
|---------|---------------|-----------|
| Page background | bg-gray-950 or bg-slate-950 | #030712 or #020617 |
| Card/Section background | bg-gray-900 | #111827 |
| Primary text | text-white or text-gray-100 | #ffffff or #f3f4f6 |
| Secondary text | text-gray-400 | #9ca3af |
| Muted text | text-gray-500 | #6b7280 |
| Accent color | text-blue-400 bg-blue-500 | #60a5fa / #3b82f6 |
| Border | border-gray-800 | #1f2937 |
| Card hover | hover:bg-gray-800 | #1f2937 |

### 2.3 Color Rules
- Use EXACTLY ONE accent color throughout the entire page
- The accent color should appear on less than 10% of total visible area
- 90% of the interface uses neutral tones (gray, white, slate)
- Never use more than 5 distinct colors on a single page
- Gradients: only on hero sections or feature highlights, never on body text or body background

---

## 3. TYPOGRAPHY SYSTEM

### 3.1 Font Family Hierarchy

| Usage | Font Family | Tailwind Class | Weight |
|-------|------------|---------------|--------|
| Hero/main heading | Font sans (Inter, system-ui) | font-sans | font-bold (700) or font-semibold (600) |
| Section headings | Font sans (Inter, system-ui) | font-sans | font-semibold (600) |
| Body text | Font sans (Inter, system-ui) | font-sans | font-normal (400) |
| Code/pre | Font mono (JetBrains Mono, monospace) | font-mono | font-normal (400) |

### 3.2 Font Size Scale

| Level | Mobile (default) | Tablet (md:) | Desktop (lg:) | Usage |
|-------|-----------------|--------------|---------------|-------|
| Hero Title | text-3xl (30px) | md:text-5xl (48px) | lg:text-6xl (60px) | Page main heading |
| Section Title | text-2xl (24px) | md:text-3xl (30px) | lg:text-4xl (36px) | Section headings |
| Card Title | text-lg (18px) | md:text-xl (20px) | lg:text-xl (20px) | Card/panel headings |
| Body Large | text-base (16px) | md:text-lg (18px) | lg:text-lg (18px) | Intro paragraphs |
| Body Normal | text-base (16px) | text-base (16px) | text-base (16px) | Standard body text |
| Body Small | text-sm (14px) | text-sm (14px) | text-sm (14px) | Captions, footnotes |
| Micro | text-xs (12px) | text-xs (12px) | text-xs (12px) | Labels, badges, tags |

### 3.3 Typography Rules
- Line height for body text: leading-relaxed (1.625) — always
- Line height for headings: leading-tight (1.25)
- Letter spacing for large headings: tracking-tight (-0.025em)
- Maximum line length for readability: 65-75 characters per line (max-w-prose or max-w-2xl)
- Never center-align paragraphs longer than 3 lines
- Always use text-gray-600 (not pure black) for body text on light backgrounds
- Always use text-gray-400 (not pure white) for body text on dark backgrounds

---

## 4. SPACING & LAYOUT SYSTEM

### 4.1 Vertical Rhythm (Section Spacing)
- Between major sections: py-16 (64px) on desktop, py-12 (48px) on mobile
- Between related content blocks: space-y-8 (32px) or gap-8
- Between text and its heading: mb-4 (16px) or mb-6 (24px)
- Between card grid items: gap-6 (24px)
- Inside cards: p-6 (24px) default, p-8 (32px) for featured cards

### 4.2 Horizontal Spacing
- Page side padding mobile: px-4 (16px)
- Page side padding tablet: md:px-8 (32px)
- Page side padding desktop: lg:px-16 (64px)
- Maximum content width: max-w-7xl (1280px) with mx-auto
- Between buttons in a row: gap-3 (12px) or gap-4 (16px)

### 4.3 Card Grid Layout
- Mobile: grid-cols-1 (single column)
- Tablet: md:grid-cols-2 (two columns)
- Desktop: lg:grid-cols-3 (three columns) or lg:grid-cols-4 (four columns for small cards)

### 4.4 Layout Patterns
- Hero sections: full viewport min-h-screen or min-h-[80vh] with vertically centered content (flex items-center)
- Feature sections: alternating left-right on desktop (image left/text right, then reverse), stacked on mobile
- Footer: multi-column on desktop (grid-cols-4 or grid-cols-5), single column on mobile
- Forms: max-w-md or max-w-lg centered, inputs stacked vertically with labels above

---

## 5. COMPONENT STYLES

### 5.1 Buttons

**Primary Button (main action):**
```
bg-blue-600 hover:bg-blue-700 text-white font-medium px-6 py-3 rounded-xl
transition-all duration-200 active:scale-[0.97]
min-h-[44px] (mobile touch target)
```

**Secondary Button (alternative action):**
```
border border-gray-300 hover:border-gray-400 text-gray-700 hover:text-gray-900
font-medium px-6 py-3 rounded-xl transition-all duration-200
min-h-[44px]
```

**Ghost/Tertiary Button (low emphasis):**
```
text-gray-600 hover:text-gray-900 hover:bg-gray-100 px-4 py-2 rounded-lg transition-all
```

**Danger Button (destructive action):**
```
bg-red-600 hover:bg-red-700 text-white font-medium px-6 py-3 rounded-xl
transition-all duration-200
```

**Mobile Full-Width Button:**
```
w-full md:w-auto (fills screen on mobile, natural width on tablet+)
```

### 5.2 Cards

```
bg-white rounded-2xl border border-gray-100 shadow-sm
hover:shadow-md hover:border-gray-200 transition-all duration-300 p-6
```

### 5.3 Input Fields

```
w-full px-4 py-3 bg-white border border-gray-300 rounded-xl
text-gray-900 placeholder:text-gray-400
focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500
transition-all duration-200
min-h-[44px] (mobile touch target)
```

With label above:
```
<label class="block text-sm font-medium text-gray-700 mb-1">Label Text</label>
<input class="[as above]" />
```

### 5.4 Navigation

**Desktop Top Navigation (lg:flex lg:flex-row):**
- Background: bg-white border-b border-gray-100
- Logo left, links center or right
- Links: text-gray-600 hover:text-gray-900 px-4 py-2
- Active link: text-blue-600 font-medium
- Max height: h-16 (64px)
- Sticky: sticky top-0 z-50

**Mobile Navigation (default — hamburger menu):**
- Hamburger button: top-right corner, 44x44px touch target
- Mobile menu: fixed full-screen overlay with white background
- Menu items: full-width, text-lg, py-4, with separators (border-b border-gray-100)
- Close button: same position as hamburger

### 5.5 Footer

```
bg-gray-900 text-gray-400
Desktop: grid grid-cols-4 gap-8 py-16 px-8
Mobile: flex flex-col space-y-8 py-12 px-4
Bottom bar: border-t border-gray-800 py-6 text-sm text-gray-500
```

---

## 6. ANIMATION & TRANSITIONS

### 6.1 Standard Transition Values
- Duration: 200ms for micro-interactions (buttons, links)
- Duration: 300ms for card hovers, color changes
- Duration: 500ms for page transitions, modal open/close
- Easing: ease-out for appearing elements, ease-in-out for transforms

### 6.2 Hover Effects
- Cards: hover:-translate-y-1 hover:shadow-md (subtle lift)
- Buttons: hover:brightness-110 or darker shade based on type
- Links: hover:underline or hover:text-[color]
- Images: hover:scale-[1.02] (subtle zoom)

### 6.3 Entrance Animations (On Scroll Into View)
- Elements should fade up: translate-y-4 opacity-0 → translate-y-0 opacity-100
- Stagger: first element 0ms delay, second 100ms, third 200ms, etc.
- Duration: 500-700ms per element
- Apply only once (not on every scroll)

### 6.4 Loading States
- Skeleton loaders: gray-200 animate-pulse rounded for content areas
- Spinner: simple CSS spinner 24x24px, colored with accent color
- Button loading: spinner replaces text, button disabled

---

## 7. ACCESSIBILITY REQUIREMENTS

- All images must have alt text (descriptive, not "image" or "photo")
- Form inputs must have associated labels (use for + id or aria-label)
- Color contrast ratio: minimum 4.5:1 for normal text, 3:1 for large text
- Focus states: visible outline ring-2 ring-blue-500 on all interactive elements
- Buttons and links must be keyboard accessible (Tab to focus, Enter/Space to activate)
- Page must have exactly one h1 element
- Headings must follow logical hierarchy (h1 → h2 → h3, never skip levels)
- Use semantic HTML elements: nav, main, section, article, aside, footer, header

---

## 8. EXECUTION CHECKLIST (Agent Must Follow In Order)

1. [ ] READ project files to understand existing code and structure
2. [ ] CHECK all image assets are present or use placeholder URLs
3. [ ] PLAN layout structure for mobile first, then tablet, then desktop
4. [ ] WRITE HTML with semantic elements (header, nav, main, section, footer)
5. [ ] WRITE CSS using Tailwind utility classes only (no custom CSS unless absolutely necessary)
6. [ ] VERIFY mobile layout: single column, 16px text minimum, 44px touch targets
7. [ ] VERIFY tablet layout: md: breakpoints applied, 2-column grids where needed
8. [ ] VERIFY desktop layout: lg: breakpoints applied, max-w-7xl centered
9. [ ] CHECK for horizontal overflow at all breakpoints
10. [ ] CHECK all interactive elements have hover and focus states
11. [ ] RUN the page in a browser (or instruct user to do so) to verify visual correctness
12. [ ] REPORT completion with a summary of what was created at each breakpoint

---

## 9. QUICK REFERENCE — Tailwind Classes For Common Tasks

**Center content horizontally:** mx-auto max-w-7xl
**Center content vertically:** flex items-center justify-center min-h-screen
**Responsive grid:** grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6
**Responsive padding:** px-4 md:px-8 lg:px-16 py-12 md:py-16 lg:py-24
**Responsive text:** text-3xl md:text-5xl lg:text-6xl font-bold tracking-tight
**Card component:** bg-white rounded-2xl shadow-sm border border-gray-100 p-6
**Button primary:** bg-blue-600 text-white px-6 py-3 rounded-xl font-medium hover:bg-blue-700
**Input field:** w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500
**Sticky header:** sticky top-0 z-50 bg-white/80 backdrop-blur border-b border-gray-100
**Footer:** bg-gray-900 text-gray-400 py-12 grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-8

---

## 10. CURATED DESIGN REFERENCE WEBSITES

These websites are **content libraries** — they each provide hundreds or thousands of actual code examples, component designs, and ready-to-use CSS/HTML snippets. For every UI task, the agent MUST browse the actual content of at least **2 websites** from the list below. The goal is to **find specific code examples from their catalogs** and adapt them to the current project.

**How to use these sites correctly:**
1. Open the website URL in the browser (or search its gallery/catalog)
2. Browse/search for the exact component type you need (e.g., "button", "card", "login form", "navbar")
3. Look through the dozens/hundreds of examples they provide — each one has actual HTML/CSS source code
4. Select ONE specific example whose design style best matches the project requirements
5. Copy the CSS/HTML techniques from that specific example (not the website's own UI)
6. Adapt the code to use the project's color system and Tailwind classes from Sections 2-5

**Example workflow:**
- Task asks for a "glassmorphism login card" → browse Glassmorphism.com's generator → find a card design with the right blur/border/transparency values → copy the `backdrop-filter` and `background` CSS → apply to the project's login card component
- Task asks for "animated gradient button" → browse gradient.style → find a purple-to-blue gradient → browse Uiverse.io → search "gradient button" → find M4rco592's animated button → combine the gradient colors with the button animation pattern

### 10.1 Design Component Catalogs (Content You Browse For Code)

| Website | URL | What Content They Provide |
|---------|-----|--------------------------|
| **Uiverse.io** | https://uiverse.io/ | Community-built CSS/HTML component gallery with **hundreds of ready-to-copy elements**: buttons (200+ styles), cards (150+), loaders (100+), toggles, checkboxes, inputs, modals, navigation. Each component has: live preview, full HTML/CSS source code, and a unique creator ID. Search by element type, browse by creator. **When using: pick one specific component that matches your needs, copy its code pattern, adapt colors to project theme.** |
| **CodePen** | https://codepen.io/ | **Millions of live code demos** created by developers worldwide. Search for: "tailwind card hover", "css only modal", "3D button three.js", "animated login form". Each result is a working code example with HTML, CSS, and JS panes visible. **When using: search for your specific component type, open 3-5 results, study the top-voted ones, adapt the best technique.** |
| **Hover.dev** | https://hover.dev/ | **Curated hover effect gallery** with 100+ effects. Each effect has: live preview, Tailwind CSS classes, and vanilla CSS code. Categories: link underlines, button animations, image overlays, card lift effects, text reveals. **When using: browse the gallery, pick the hover effect that matches your design tone, copy the exact Tailwind classes.** |
| **Animista** | https://animista.net/ | **CSS animation code generator** with dozens of preset animations. Categories: fade, slide, rotate, scale, blur, bounce, flip. Each animation has adjustable parameters and outputs complete `@keyframes` + CSS class code. **When using: select the animation type you need, adjust speed/easing, copy the generated CSS keyframes into your stylesheet.** |
| **getwaves.io** | https://getwaves.io/ | **SVG wave pattern generator.** Adjust wave shape, curvature, number of layers, and colors. Outputs downloadable SVG or inline SVG code. **When using: customize the wave to match your section divider needs, copy the SVG code directly into your HTML.** |
| **Blobmaker** | https://www.blobmaker.app/ | **Random organic SVG blob shape generator.** Each click generates a new unique blob. Customize color, complexity, and contrast. Download as SVG or copy path data. **When using: generate 5-10 blobs, pick the shape that fits your layout, place as hero background or card decoration.** |
| **cssgradient.io** | https://cssgradient.io/ | **Visual CSS gradient builder.** Drag color stops on a gradient bar, adjust angle and type (linear/radial), preview in real-time. Outputs exact `linear-gradient()` or `radial-gradient()` CSS code. **When using: design your gradient visually, copy the CSS code into your Tailwind config or inline style.** |
| **Neumorphism.io** | https://neumorphism.io/ | **Soft UI / neumorphic design code generator.** Adjust background color, element color, shadow distance, blur, and border radius. Outputs complete `box-shadow` and `border-radius` CSS. **When using: only if the project requests soft/flat 3D aesthetic — generate shadow values, copy CSS.** |
| **Glassmorphism.com** | https://glassmorphism.com/ | **Frosted glass effect CSS generator.** Set blur amount, transparency level, border width and color. Outputs `backdrop-filter: blur()` and `background: rgba()` CSS. **When using: adjust blur until the frosted glass effect looks right, copy CSS values, apply to card/modal/navbar.** |
| **gradient.style** | https://gradient.style/ | **Premium CSS gradient collection** organized by color family (blue, purple, warm, green, monochrome). Each gradient shows: preview, Tailwind classes, and raw CSS. **When using: browse the color family that matches your accent color, pick a gradient, copy both Tailwind and CSS versions.** |
| **cubic-bezier.com** | https://cubic-bezier.com/ | **Visual CSS easing curve builder.** Drag two handles to shape an easing curve, preview the animation motion with a ball demo, copy the exact `cubic-bezier()` value. **When using: design a custom easing for entrance animations or transitions, copy the bezier value.** |
| **Coolors.co** | https://coolors.co/ | **Color palette generator** — press spacebar to generate random 5-color palettes. Lock colors you like, adjust individual colors, export as CSS variables, Tailwind config, hex, RGB. **When using: generate until you find a palette that fits the project mood, lock the main color, export as Tailwind theme config.** |
| **Adobe Color** | https://color.adobe.com/ | **Color wheel with harmony rules** (complementary, analogous, triadic, monochromatic, compound, shades). Extract palette from an uploaded image. Export as hex, RGB, CSS. **When using: use the color wheel to find mathematically harmonious colors for your accent + neutral scheme.** |
| **ColorsInspo** | https://colorsinspo.com/ | **Curated color palette library** organized by mood (dark, pastel, vibrant, corporate, nature). Each palette displays hex codes and contrast ratio check. **When using: browse by the project's intended mood, copy the hex codes, use as starting point for color theme.** |

### 10.2 UI/UX Best Practice Resources (Read-Only Reference)

- **Smashing Magazine** — Articles on accessibility, responsive patterns, form UX, color theory, typography
- **CSS-Tricks** — Complete CSS reference guides for Flexbox, Grid, animations, custom properties
- **Awwwards** — Gallery of award-winning websites for layout composition and interaction design ideas
- **Dribbble** — Professional UI design shots for color pairings, spacing, and visual hierarchy reference
- **Mobbin** — Real production app screenshots organized by user flow (signup, onboarding, dashboard, settings)

---

## 11. CURATED OPEN-SOURCE JAVASCRIPT LIBRARIES

All libraries listed below are 100% open source (MIT, Apache 2.0, ISC, or BSD license). For each UI task, the agent MUST choose at least **2 libraries** from this catalog and integrate them into the project. The libraries here are **reference catalogs** — each category has multiple options; pick the one whose API and component set best matches the project requirements.

**How to use the libraries correctly:**
1. Identify the project's functional needs (animation? 3D? icons? forms? tables? rich text?)
2. Look through the relevant category below — each library has a "Best For" description
3. Pick the library whose strengths match your project's requirements
4. Install it via npm (command provided in the "Install Command" column)
5. Use the library's actual documentation and examples to implement features
6. If installation fails (network, version conflict, environment), skip it and try the next one in the same category

**Example workflow:**
- Project needs smooth scroll animations + icons → pick **AOS** (Animation) + **Lucide React** (Icons) → install both → use AOS `data-aos` attributes for scroll effects → use Lucide `<Icon>` components for all icons

### 11.1 Core UI Framework Libraries

| Library | Install Command | License | Best For |
|---------|----------------|---------|----------|
| **shadcn/ui** | `npx shadcn-ui@latest init` | MIT | Tailwind-first component library with full source code access. Copy-paste components into your project. |
| **Headless UI** | `npm install @headlessui/react` | MIT | Unstyled, accessible UI primitives (dropdown, dialog, tabs, listbox). Works perfectly with Tailwind. |
| **Chakra UI** | `npm install @chakra-ui/react @emotion/react @emotion/styled framer-motion` | MIT | Accessible, composable React components with built-in dark mode and responsive props. |
| **Ant Design** | `npm install antd` | MIT | Enterprise-grade UI framework with 60+ components. Excellent for admin dashboards and data-heavy interfaces. |
| **daisyUI** | `npm install daisyui` | MIT | Tailwind CSS component library. Add semantic class names like `btn-primary`, `card`, `alert`. No JS components — pure CSS. |
| **Mantine** | `npm install @mantine/core @mantine/hooks` | MIT | Full-featured React component library with hooks for modals, notifications, forms. Excellent documentation. |
| **PrimeVue** | `npm install primevue primeicons` | MIT | Vue component library with 90+ components. Each has multiple themes (Material, Bootstrap, Tailwind). |
| **Vuetify** | `npm install vuetify@3` | MIT | Material Design 3 framework for Vue. Complete with grid system, typography, and 80+ components. |

### 11.2 Animation & Interaction Libraries

| Library | Install Command | License | Best For |
|---------|----------------|---------|----------|
| **Framer Motion** | `npm install framer-motion` | MIT | Declarative React animations. Layout animations, gestures (drag, hover, tap), scroll-linked animations. |
| **GSAP** | `npm install gsap` | Standard (free) | Professional-grade animation. Timeline sequencing, scroll-triggered animations, SVG morphing. Industry standard for complex motion. |
| **Three.js** | `npm install three` | MIT | 3D rendering in the browser. Particle systems, 3D product viewers, interactive backgrounds, WebGL effects. |
| **Babylon.js** | `npm install babylonjs` | Apache 2.0 | Full 3D engine with physics, VR support. Easier API than Three.js for beginners. |
| **Lottie Web** | `npm install lottie-web` | Apache 2.0 | Render After Effects animations natively. Lightweight JSON format. Use with LottieFiles for free animations. |
| **AOS** | `npm install aos` | MIT | Animate On Scroll library. Add `data-aos="fade-up"` attributes to elements. Zero JavaScript configuration needed. |
| **React Spring** | `npm install @react-spring/web` | Apache 2.0 | Physics-based animation for React. Natural spring animations, trajectories, interpolation. |
| **Anime.js** | `npm install animejs` | MIT | Lightweight JavaScript animation engine. CSS properties, SVG, DOM attributes, JavaScript objects. |
| **TweenJS** | `npm install tweenjs` | MIT | Simple tweening library. Animate any numeric property between two values. Part of CreateJS suite. |
| **Popmotion** | `npm install popmotion` | MIT | Low-level animation library. Functional API for springs, tweens, and input tracking. Underlies Framer Motion. |

### 11.3 Styling & CSS Libraries

| Library | Install Command | License | Best For |
|---------|----------------|---------|----------|
| **Tailwind CSS** | `npm install -D tailwindcss postcss autoprefixer` | MIT | Utility-first CSS framework. Used as the default styling system for all UI tasks unless specified otherwise. |
| **Styled Components** | `npm install styled-components` | MIT | CSS-in-JS with tagged template literals. Scoped styles, dynamic props, theme support. |
| **Emotion** | `npm install @emotion/react @emotion/styled` | MIT | High-performance CSS-in-JS. Used internally by Chakra UI and MUI. |
| **UnoCSS** | `npm install -D unocss` | MIT | Instant on-demand atomic CSS engine. Faster alternative to Tailwind with same utility class API. |
| **Panda CSS** | `npm install @pandacss/dev` | MIT | Type-safe CSS-in-JS with zero runtime. Generates static CSS at build time. |

### 11.4 Icon Libraries

| Library | Install Command | License | Best For |
|---------|----------------|---------|----------|
| **Lucide React** | `npm install lucide-react` | ISC | Clean, consistent icon set (1000+ icons). Tree-shakeable, customizable stroke width. Default icon choice. |
| **React Icons** | `npm install react-icons` | MIT | Unified package for 20+ icon sets (Font Awesome, Material, Feather, Heroicons). Import icons from any set. |
| **Heroicons** | `npm install heroicons` | MIT | Tailwind CSS team's icon set. 288 icons in outline and solid styles. |
| **Phosphor React** | `npm install phosphor-react` | MIT | 1000+ icons with 6 style variants per icon (thin, light, regular, bold, fill, duotone). |
| **Feather Icons** | `npm install feather-icons` | MIT | Minimalist icon set (287 icons). Stroke-based, 24x24 grid, customizable. |
| **Tabler Icons** | `npm install tabler-icons` | MIT | 3000+ pixel-perfect icons. Consistent 2px stroke, 24x24 size. |

### 11.5 Data & Visualization Libraries

| Library | Install Command | License | Best For |
|---------|----------------|---------|----------|
| **TanStack Table** | `npm install @tanstack/react-table` | MIT | Headless table library. Sorting, filtering, pagination, column resizing. Framework-agnostic. |
| **Grid.js** | `npm install gridjs` | MIT | Lightweight data table with built-in search, sort, pagination. Works with any framework. |
| **Chart.js** | `npm install chart.js` | MIT | Simple canvas-based charts. Line, bar, radar, doughnut, polar. Good for dashboards and analytics. |
| **ECharts** | `npm install echarts` | Apache 2.0 | Feature-rich charting library. 3D charts, maps, heatmaps, tree diagrams. Smooth animations. |
| **D3.js** | `npm install d3` | ISC | Low-level data visualization. Full control over SVG, Canvas, or HTML rendering. Used for custom interactive visualizations. |

### 11.6 Utility Libraries (Always Useful)

| Library | Install Command | License | Purpose |
|---------|----------------|---------|---------|
| **Zustand** | `npm install zustand` | MIT | Lightweight state management for React. Simple API, no boilerplate. |
| **React Hook Form** | `npm install react-hook-form` | MIT | Performant form validation. Minimal re-renders, native HTML validation integration. |
| **Zod** | `npm install zod` | MIT | TypeScript-first schema validation. Define schemas, infer types, validate at runtime. |
| **Axios** | `npm install axios` | MIT | Promise-based HTTP client. Request/response interceptors, automatic JSON parsing, timeout handling. |
| **date-fns** | `npm install date-fns` | MIT | Modular date utility library. Format, parse, compare, manipulate dates. Tree-shakeable. |
| **clsx** | `npm install clsx` | MIT | Tiny utility for conditionally joining class names. Used with Tailwind for dynamic classes. |
| **nanoid** | `npm install nanoid` | MIT | Tiny, secure, URL-friendly unique ID generator. Alternative to UUID. |

### 11.7 Rich Text Editor Libraries

| Library | Install Command | License | Best For |
|---------|----------------|---------|----------|
| **Tiptap** | `npm install tiptap` | MIT | Headless, extensible rich text editor. Based on ProseMirror. Extensions for mentions, tables, code blocks. |
| **Slate** | `npm install slate` | MIT | Customizable rich text editor framework. Full control over the editing experience. |
| **Lexical** | `npm install lexical` | MIT | Meta's extensible text editor. Lightweight, framework-agnostic. |
| **Quill** | `npm install quill` | BSD | Ready-to-use rich text editor with clean API. Toolbar, themes, and formats included. |
| **Editor.js** | `npm install editorjs` | Apache 2.0 | Block-style editor. Outputs clean JSON. Plugins for images, code, tables, embeds. |

---

## 12. TASK EXECUTION RULES (Updated)

### 12.1 Mandatory References Per Task
For every UI task (creating a page, component, or layout), the agent MUST:

1. Randomly select and consult at least **2 design reference websites** from Section 10
2. Randomly select and install/integrate at least **2 open-source libraries** from Section 11
3. Document which websites and libraries were used in the completion report

### 12.2 Library Integration Policy
- Libraries marked as reference-only (design websites) are consulted for inspiration and code patterns — they are NOT installed
- Libraries from Section 11 that provide UI components (shadcn/ui, daisyUI, Headless UI) should be **installed and used** in the project when relevant
- Animation libraries (Framer Motion, AOS, Anime.js) should be installed for any page with interactive elements
- Icon libraries (Lucide React) should be installed for every UI project
- If a library fails to install due to network, version conflicts, or environment issues, skip it and try another from the same category — **do not block task completion**
- Failed library installations must be noted in the completion report but are NOT errors

### 12.3 Style Reference Procedure
When consulting design websites:
1. Browse/search for the specific component type needed (e.g., "card", "navbar", "modal")
2. Study the CSS techniques used (animations, transitions, layout)
3. Adapt the design pattern to the project's color system and typography
4. Use the exact Tailwind classes and CSS from Section 2-5 of this ruleset
5. Credit the source website in code comments: `/* Inspired by: https://uiverse.io/... */`

---

## 13. 🎨 DESIGN STYLE SYSTEM — RANDOM SELECTION BY CONTEXT

> **NOTE:** This section is DEPRECATED in favor of the new modular system:
> - **`.orca/design/styles.md`** — 12 curated styles with concrete examples
> - **`.orca/design/colors.md`** — 12 premium color palettes (Apple, Stripe, Dior, Gucci, etc.)
> - **`.orca/design/typography.md`** — 10 font pairings
> - **`.orca/design/spacing.md`** — 8-point grid system
> 
> Use the new files for ALL new UI work. This section kept for backward compatibility.

### 13.1 Style Selection Rules

The agent MUST select ONE design style per project/page/component using the following rules:

**Step 1: Analyze Context**
Read the user's request, project description, and any theme hints. Identify the context category:

| Context Clue | Matched Styles |
|-------------|----------------|
| "corporate", "professional", "SaaS", "dashboard", "admin", "enterprise", "clean", "simple" | Minimalism, Corporate |
| "dark", "tech", "hacker", "cyberpunk", "gaming", "dev", "terminal", "code" | Dark Mode & High Contrast |
| "cozy", "organic", "natural", "food", "recipe", "blog", "handmade", "artisan", "boutique" | Warm Aesthetic |
| "futuristic", "transparent", "overlay", "glass", "depth", "blur", "modern" | Glassmorphism |
| "bold", "creative", "agency", "portfolio", "fun", "playful", "colorful", "loud" | Bold & Maximalism |
| "soft", "subtle", "minimal shadow", "3D button", "tactile", "iPhone-like" | Neumorphism |
| "3D", "immersive", "interactive", "game", "product showcase", "rotate" | 3D & Immersive |
| "editorial", "magazine", "news", "literary", "serif", "elegant" | Typography-Forward |
| "analytics", "dashboard", "data", "metrics", "charts", "statistics" | Data Visualization |
| "animation", "motion", "scroll", "parallax", "transition" | Animation & Motion |
| "mobile app", "native feel", "iOS", "Android", "app-like" | Mobile App Style |
| "elegant", "luxury", "premium", "sophisticated", "refined" | Elegant Minimal |
| "vintage", "retro", "nostalgia", "classic", "old-school" | Retro / Vintage |

**Step 2: Random Selection Within Context**
- If context matches **ONE style** → use that style
- If context matches **MULTIPLE styles** → randomly pick ONE
- If context is **AMBIGUOUS or UNDEFINED** → randomly pick from ALL styles
- The randomization should ensure VARIETY across tasks — do NOT always pick the same style

**Step 3: Apply Style Consistently**
Once selected, apply the chosen style's rules to ALL elements in the project. Do NOT mix styles within a single page/component unless explicitly told to.

---

### 13.2 🤍 STYLE 1: MINIMALISM & CLEAN DESIGN

**When to use:** Corporate websites, SaaS landing pages, dashboards, documentation sites, professional portfolios.

**Colors:**
- Background: `#FFFFFF` or `#FAFAFA`
- Text Primary: `#000000` or `#1a1a1a`
- Text Secondary: `#666666`
- Accent: ONE color only (navy blue `#003d82`, or deep teal)
- Borders: `#DDDDDD`, `#E5E5E5`
- NO gradients, NO secondary accent colors

**Typography:**
- Display: Inter, Helvetica Neue, System Font — 48-64px, weight 600-700, line-height 1.2, letter-spacing -0.02em
- Body: Inter, -apple-system — 16px, weight 400, line-height 1.6, letter-spacing 0
- UI/Button: 14px, weight 500, letter-spacing 0.01em

**Spacing:** Multiples of 8 (8, 16, 24, 32, 48). Container padding 24px mobile / 48px desktop. Section gaps 64-96px. Max-width 1200-1440px. 40-50% whitespace.

**Buttons:**
- Primary: `padding: 12px 24px; border-radius: 4px; background: #003d82; color: white; border: none; font-size: 14px; font-weight: 500; transition: opacity 0.2s;` Hover: `opacity 0.85`
- Secondary: `background: transparent; border: 1px solid #DDDDDD; color: #1a1a1a;`

**Cards:** `background: white; border: 1px solid #EEEEEE; border-radius: 8px; padding: 24px; box-shadow: none;` Hover: `border-color: #CCCCCC`

**Inputs:** `padding: 12px 16px; border: 1px solid #DDDDDD; border-radius: 4px; font-size: 16px;` Focus: `border-color: #003d82; box-shadow: none;` Label: 14px, weight 500, color `#1a1a1a`

**Icons:** Outline/stroke-based, 16-32px, 2px stroke, same color as text.

**Navigation:** Height 64px, padding 0 24px, `border-bottom: 1px solid #EEEEEE`, bg white. Links: 14px, weight 500, color `#666666`, hover color `#003d82`.

**Animations:** Duration 0.2-0.3s, ease. ONLY opacity, color, border-color changes. NO transforms.

**Shadows:** None or very light (`0 1px 2px rgba(0,0,0,0.05)`).

**Border Radius:** Buttons 4px, Cards 8px, Large elements 12px.

**Tailwind equivalents:**
```
bg-white text-gray-900 text-gray-600 border-gray-200
rounded (4px) rounded-lg (8px) rounded-xl (12px)
font-sans font-semibold font-medium font-normal
py-3 px-6 text-sm tracking-wide
transition-opacity duration-200
```

---

### 13.3 🌙 STYLE 2: DARK MODE & HIGH CONTRAST

**When to use:** Tech projects, developer tools, gaming sites, cyberpunk themes, terminal emulators, code editors.

**Colors:**
- Background: `#0a0a0a`, `#111111`, `#1a1a1a`
- Surface/Cards: `#1e1e1e`, `#252525`
- Text Primary: `#ffffff`
- Text Secondary: `#b0b0b0`, `#999999`
- Accent (neon): Acid Green `#00ff00`, Neon Pink `#ff006e`, Cyan `#00ffff`, Vermilion `#ff4500`
- Borders: `#333333`, `#404040`

**Typography:**
- Display: Inter, Roboto, Courier (monospace for tech) — 36-56px, weight 600-700, color `#ffffff`, letter-spacing -0.01em
- Body: Inter — 15-16px, weight 400, color `#d0d0d0`, line-height 1.6

**Buttons:**
- Primary: `padding: 12px 24px; border-radius: 8px; background: linear-gradient(135deg, #00ff00, #00cc00); color: #0a0a0a; font-weight: 600; box-shadow: 0 8px 24px rgba(0,255,0,0.25); transition: all 0.3s;` Hover: `box-shadow: 0 12px 32px rgba(0,255,0,0.4); transform: translateY(-2px);`
- Secondary: `background: transparent; border: 2px solid #00ff00; color: #00ff00;` Hover: `background: rgba(0,255,0,0.1); box-shadow: 0 0 16px rgba(0,255,0,0.3);`

**Cards:** `background: #1e1e1e; border: 1px solid #333333; border-radius: 12px; padding: 24px; box-shadow: 0 8px 32px rgba(0,0,0,0.3);` Hover: `border-color: #00ff00; box-shadow: 0 12px 40px rgba(0,255,0,0.15);`

**Inputs:** `background: #252525; border: 1px solid #404040; border-radius: 8px; padding: 12px 16px; color: #ffffff;` Focus: `border-color: #00ff00; background: #1e1e1e; box-shadow: 0 0 12px rgba(0,255,0,0.2);` Placeholder: `#666666`

**Navigation:** Height 64px, bg transparent, `border-bottom: 1px solid #333333`, `backdrop-filter: blur(10px)`. Links: color `#b0b0b0`, hover `#00ff00`.

**Animations:** Duration 0.3-0.5s, ease-in-out. Color changes, glow shadows, subtle scale (0.98-1.02), translateY(-2px on hover).

**Icons:** Color `#00ff00` or `#ffffff`, 20-32px, 2px stroke, glow on hover.

**Scrollbar:** `scrollbar-color: #00ff00 #1a1a1a; scrollbar-width: thin;`

**Dividers:** `background: linear-gradient(90deg, transparent, #333333, transparent); height: 1px;`

**Tailwind equivalents:**
```
bg-gray-950 bg-gray-900 bg-gray-800
text-white text-gray-400 text-gray-500
border-gray-800 border-gray-700
text-green-400 bg-green-500
shadow-lg shadow-green-500/25
hover:shadow-green-500/40 hover:-translate-y-0.5
transition-all duration-300 ease-in-out
backdrop-blur-md
```

---

### 13.4 🔥 STYLE 3: WARM AESTHETIC (Cream & Terracotta)

**When to use:** Food blogs, recipe sites, artisan/boutique shops, handmade product stores, wellness brands, cozy portfolios.

**Colors:**
- Background: `#F4F1EA`, `#F9F7F4` (cream)
- Secondary BG: `#FAF8F5`
- Text Primary: `#2a2520` (deep brown)
- Text Secondary: `#8b8578`
- Accent Colors: Terracotta `#d4714f`, Burnt Orange `#c25a3a`, Gold `#d4af37`, Sage Green `#9ca89a`
- Borders: `#e8e3da`, `#dcd5ca`

**Typography:**
- Display (Serif): Playfair Display, Lora, Cormorant — 52-72px, weight 600-700, color `#2a2520`, letter-spacing 0
- Body (Sans): Inter, Sohne — 15-16px, weight 400, color `#4a4540`, line-height 1.7, letter-spacing 0.02em
- Accent Text: Serif italic or small-caps, 14-16px, color `#d4714f`

**Buttons:**
- Primary: `padding: 14px 32px; border-radius: 24px; background: #d4714f; color: #ffffff; font-size: 15px; font-weight: 500; box-shadow: 0 8px 16px rgba(212,113,79,0.15); transition: all 0.3s;` Hover: `background: #c25a3a; box-shadow: 0 12px 24px rgba(212,113,79,0.25); transform: translateY(-2px);`
- Secondary: `background: transparent; border: 2px solid #d4714f; color: #d4714f;`
- Ghost: `background: transparent; border: none; color: #d4714f; text-decoration: underline; text-decoration-color: rgba(212,113,79,0.3);`

**Cards:** `background: #ffffff; border: 1px solid #e8e3da; border-radius: 12px; padding: 32px 28px; box-shadow: 0 2px 8px rgba(42,37,32,0.06);` Hover: `border-color: #d4714f; box-shadow: 0 8px 16px rgba(212,113,79,0.1);`

**Inputs:** `background: #faf8f5; border: 1px solid #e8e3da; border-radius: 8px; padding: 12px 16px; color: #2a2520;` Focus: `background: #ffffff; border-color: #d4714f; box-shadow: 0 0 0 3px rgba(212,113,79,0.1);` Label: 13px, weight 500, uppercase, letter-spacing 0.05em

**Navigation:** Height 70px, bg `rgba(244,241,234,0.9)`, `backdrop-filter: blur(4px)`, `border-bottom: 1px solid #e8e3da`. Logo: Serif, 20px, weight 600. Links: 13px, weight 500, uppercase, letter-spacing 0.05em, color `#4a4540`, hover `#d4714f`.

**Animations:** Duration 0.3-0.5s, cubic-bezier(0.4, 0, 0.2, 1). Color transitions, subtle lift (translateY -2px), border color changes, shadow expansion.

**Decorative:** Dividers with gradient fade. Ornaments (circles, flourishes). Generous letter-spacing. Serif italic quotes. Emphasis via color/italic, NOT bold.

**Tailwind equivalents:**
```
bg-[#F4F1EA] bg-[#F9F7F4] bg-[#FAF8F5]
text-[#2a2520] text-[#8b8578] text-[#4a4540]
text-[#d4714f] bg-[#d4714f] border-[#d4714f]
border-[#e8e3da] border-[#dcd5ca]
font-serif font-sans
rounded-full (24px buttons) rounded-xl (12px cards)
tracking-wide uppercase text-xs
shadow-sm hover:shadow-md hover:-translate-y-0.5
transition-all duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]
```

---

### 13.5 🌀 STYLE 4: GLASSMORPHISM (Frosted Glass)

**When to use:** Modern landing pages, hero sections, overlay cards, futuristic interfaces, music/media sites, creative portfolios.

**Colors:**
- Background: Dark (`#0f172a`, `#1a1f3a`) or Light (`#f5f7fa`)
- Glass elements: Semi-transparent `rgba()` values
- Text: High contrast on background (white on dark, dark on light)

**Glass Effect (base):**
```css
background: rgba(255, 255, 255, 0.1);
backdrop-filter: blur(10px);
-webkit-backdrop-filter: blur(10px);
border: 1px solid rgba(255, 255, 255, 0.2);
border-radius: 12px;
padding: 24px;
```

**Buttons:** `padding: 12px 24px; background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.25); backdrop-filter: blur(12px); border-radius: 12px;` Hover: `background: rgba(255,255,255,0.25); border-color: rgba(255,255,255,0.4);`

**Cards:** `background: rgba(255,255,255,0.08); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.15); border-radius: 16px; box-shadow: 0 8px 32px rgba(0,0,0,0.1);` Hover: `background: rgba(255,255,255,0.12); border-color: rgba(255,255,255,0.25);`

**Inputs:** `background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); backdrop-filter: blur(10px); border-radius: 8px;` Focus: `background: rgba(255,255,255,0.15); border-color: rgba(255,255,255,0.4); box-shadow: 0 0 20px rgba(255,255,255,0.2);`

**Typography:** Display 36-48px, weight 600-700, color `#ffffff`. Body 15px, weight 400, color `rgba(255,255,255,0.9)`. Secondary: `rgba(255,255,255,0.6)`.

**Layering:** Layer 1: Background image. Layer 2: Color overlay `rgba(20,30,60,0.4)`. Layer 3: Glass elements on top (z-index 10).

**Navigation:** `position: fixed; top: 0; width: 100%; height: 64px; background: rgba(15,23,42,0.5); backdrop-filter: blur(20px); border-bottom: 1px solid rgba(255,255,255,0.1);`

**Tailwind equivalents:**
```
bg-white/10 bg-white/8 bg-white/15 bg-white/25
backdrop-blur-md backdrop-blur-lg backdrop-blur-xl
border border-white/20 border-white/30 border-white/40
rounded-2xl rounded-3xl
shadow-lg
hover:bg-white/15 hover:border-white/30
text-white text-white/90 text-white/60
```

---

### 13.6 🎪 STYLE 5: BOLD & MAXIMALISM

**When to use:** Creative agencies, art portfolios, music sites, event pages, fashion brands, youth-oriented products.

**Colors:** Vibrant saturated: Hot Pink `#ff006e`, Electric Blue `#0080ff`, Lime Green `#00ff00`, Sunset Orange `#ff6b35`. Multiple accents (3-5 colors). Gradients and patterns encouraged.

**Typography:**
- Display: 64-120px+, weight 700-900, uppercase, tight letter-spacing. Bold sans (Montserrat Bold, Futura).
- Decorative: Can be skewed, rotated. Mixed fonts boldly.

**Buttons:** `padding: 16px 32px; border-radius: 0 or 8px; background: gradient or solid vibrant; border: 2px solid; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;` Hover: `transform: scale(1.05) rotate(-1deg); box-shadow: 0 20px 40px rgba(color,0.4);`

**Cards:** `background: gradient bold or pattern; border: 3px solid color; border-radius: 0 or 16px; padding: 40px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); transform: rotate(-2deg);` Hover: `transform: rotate(0) scale(1.02);`

**Backgrounds:** `background: linear-gradient(135deg, #ff006e, #0080ff, #00ff00);` Animated gradients: `background-size: 400% 400%;` Pattern overlays with repeating-linear-gradient.

**Animations:** Duration 0.5-1s. Scale, rotate (1-5deg), skew, bounce. `@keyframes bounce-in { 0% { opacity:0; transform: scale(0.5) translateY(20px); } 100% { opacity:1; transform: scale(1) translateY(0); } }`

**Shadows:** `0 20px 60px rgba(0,0,0,0.3)` or multiple neon glows.

**Layout:** Overlapping elements (`margin: -20px`), asymmetric grids (`2fr 1fr 1.5fr`), full-bleed sections.

**Tailwind equivalents:**
```
bg-gradient-to-br from-pink-500 via-blue-500 to-green-400
text-6xl text-7xl text-8xl font-black uppercase tracking-tighter
border-4 border-pink-500
shadow-2xl shadow-pink-500/30
hover:scale-105 hover:-rotate-1
active:scale-95
animate-bounce-in
```

---

### 13.7 🎯 STYLE 6: NEUMORPHISM (Soft UI)

**When to use:** Mobile app UIs, settings panels, calculator apps, music players, any interface needing tactile feel.

**Colors:** Single muted tone (`#e0e5e9`, `#d4d8dd`). Lighter shade for raised effect. Darker shade for inset effect. All pastel/muted — NO vibrant colors.

**Shadow System:**
```css
/* Raised */
box-shadow: -8px -8px 16px rgba(255,255,255,0.7), 8px 8px 16px rgba(0,0,0,0.1);
/* Inset (pressed) */
box-shadow: inset -8px -8px 16px rgba(255,255,255,0.7), inset 8px 8px 16px rgba(0,0,0,0.1);
```

**Buttons:** `background: #e0e5e9; border: none; border-radius: 12px; box-shadow: -6px -6px 12px rgba(255,255,255,0.7), 6px 6px 12px rgba(0,0,0,0.1);` Active: `box-shadow: inset -4px -4px 8px rgba(255,255,255,0.7), inset 4px 4px 8px rgba(0,0,0,0.1);`

**Cards:** `background: #e0e5e9; border-radius: 16px; box-shadow: -12px -12px 24px rgba(255,255,255,0.7), 12px 12px 24px rgba(0,0,0,0.1);`

**Inputs:** `background: #e0e5e9; border: none; border-radius: 12px; box-shadow: inset -4px -4px 8px rgba(255,255,255,0.5), inset 4px 4px 8px rgba(0,0,0,0.05);`

**NO:** Vibrant colors, complex gradients, high contrast, bold borders.

**Tailwind equivalents:**
```
bg-[#e0e5e9]
shadow-[_-8px_-8px_16px_rgba(255,255,255,0.7),8px_8px_16px_rgba(0,0,0,0.1)]
shadow-[inset_-4px_-4px_8px_rgba(255,255,255,0.5),inset_4px_4px_8px_rgba(0,0,0,0.05)]
rounded-xl rounded-2xl
text-gray-600
```

---

### 13.8 📱 STYLE 7: 3D & IMMERSIVE

**When to use:** Product showcases, interactive portfolios, gaming sites, immersive landing pages, VR/AR demos.

**CSS 3D:** `perspective: 1200px; transform-style: preserve-3d;` Element: `transform: rotateX(10deg) rotateY(-15deg) translateZ(50px);` Hover: `transform: rotateX(0) rotateY(0) translateZ(100px);`

**Parallax:** `background-attachment: fixed; background-size: cover;` Fallback: `@supports not (background-attachment: fixed) { background-attachment: scroll; }`

**Depth Layering:** Layer 1: `translateZ(0px)`. Layer 2: `translateZ(50px)`. Layer 3: `translateZ(100px)`.

**Three.js integration:** Use for interactive 3D scenes, product configurators, particle effects.

**Tailwind equivalents:**
```
[transform:perspective(1200px)_rotateX(10deg)_rotateY(-15deg)]
hover:[transform:perspective(1200px)_rotateX(0)_rotateY(0)]
[transform-style:preserve-3d]
```

---

### 13.9 ✏️ STYLE 8: TYPOGRAPHY-FORWARD DESIGN

**When to use:** Editorial sites, magazines, news platforms, literary blogs, law firms, luxury brands.

**Display Typography:** 64-96px, line-height 1.1, letter-spacing -0.02em, weight 600-700. Serif (Playfair, Lora) or Bold Sans.

**Font Pairings:**
1. Playfair Display + Inter
2. Sohne Bold + Sohne Regular
3. Cormorant Garamond + Source Sans Pro

**Variable Fonts:** `font-variation-settings: 'wght' 700, 'wdth' 125;` Responsive: `font-size: clamp(32px, 8vw, 64px);`

**Hierarchy:** H1: 64px/1.2/700. H2: 48px/1.3/600. H3: 32px/1.4/600. Body: 16px/1.6/400. Caption: 13px/1.5/400.

---

### 13.10 📊 STYLE 9: DATA VISUALIZATION & CHARTS

**When to use:** Dashboards, analytics platforms, reports, financial sites, scientific applications.

**Chart Colors:** `['#0173b2', '#de8f05', '#cc78bc', '#ca9161', '#949494']`

**Chart Entry Animation:** `@keyframes chart-grow { from { opacity:0; height:0; } to { opacity:1; height:100%; } }`

**Tooltip:** `background: rgba(0,0,0,0.8); color: white; padding: 8px 12px; border-radius: 4px; font-size: 13px; box-shadow: 0 4px 12px rgba(0,0,0,0.2);`

---

### 13.11 🎬 STYLE 10: ANIMATION & MOTION DETAILS

**When to use:** ANY project that emphasizes interactivity, scroll experiences, storytelling pages.

**Micro-interactions:**
- Button press: `@keyframes button-press { 0% { transform:scale(1); } 50% { transform:scale(0.98); } 100% { transform:scale(1); } }`
- Ripple effect, fade-in, slide-in-up animations.

**Scroll Animations (Intersection Observer):**
```javascript
const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) entry.target.classList.add('animate');
  });
});
```

**Page Transitions:** Exit: `opacity:0; transform:translateY(-20px)`. Entry: reverse.

**Accessibility:** `@media (prefers-reduced-motion: reduce) { * { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; } }`

---

### 13.12 📐 UNIVERSAL SPACING & COLOR SYSTEMS

**8-Point Grid:** Space values: 0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 56, 64, 80, 96.

**Component Padding:** Button: 12px 24px. Card: 24-32px. Input: 12px 16px. Section: 48-96px.

**Gap:** Compact: 8-12px. Normal: 16-24px. Spacious: 32-48px.

**Semantic Colors (all styles):** Success: `#10b981`. Error: `#ef4444`. Warning: `#f59e0b`. Info: `#3b82f6`.

**Interactive States (ALL elements MUST have):** Default, Hover, Focus, Active, Disabled (muted), Loading (spinner/skeleton), Error (red), Success (green).

**Focus Ring:** `:focus-visible { outline: 2px solid var(--accent-color); outline-offset: 2px; }`

---

### 13.13 STYLE SELECTION DECISION TREE

```
START
  │
  ├── User specifies a style? → USE THAT STYLE
  │
  ├── Context clues found? → Match to styles in 13.1 table
  │     │
  │     ├── Single match → USE THAT STYLE
  │     │
  │     └── Multiple matches → RANDOMLY PICK ONE
  │
  └── No context / ambiguous → RANDOMLY PICK FROM ALL STYLES
        │
        ├── Ensure variety across recent tasks
        ├── Don't repeat the same style 3+ times in a row
        └── Log which style was selected in completion report
```

### 13.14 STYLE APPLICATION CHECKLIST

When applying a selected style, the agent MUST:
- [ ] Use the EXACT color values from the style definition
- [ ] Use the EXACT typography settings (font, size, weight, line-height, letter-spacing)
- [ ] Use the EXACT button styles (padding, border-radius, colors, shadows)
- [ ] Use the EXACT card styles
- [ ] Use the EXACT input/form styles
- [ ] Use the EXACT animation/transition values
- [ ] Maintain CONSISTENCY across all elements on the page
- [ ] Do NOT mix styles from different design systems
