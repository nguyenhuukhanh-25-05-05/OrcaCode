# UI Design Skill — Quy tắc thiết kế giao diện cho AI

Khi được yêu cầu tạo HTML/CSS/UI, bạn BẮT BUỘC phải tuân thủ các quy tắc sau:

---

## 1. 3D & Spatial Design

### CSS 3D Tilt Card
- Dùng `perspective: 1000px` và `rotateX`, `rotateY` khi hover
- `transform-style: preserve-3d` cho card
- Nội dung bên trong dùng `translateZ(50px)` để nổi lên

```html
<div class="group [perspective:1000px]">
  <div class="[transform-style:preserve-3d] group-hover:[transform:rotateX(10deg)_rotateY(-10deg)_translateZ(20px)]">
```

### Noise Texture Overlay
Phủ lớp vân nhiễu mỏng lên toàn trang để tạo cảm giác sang trọng:
```html
<div class="pointer-events-none fixed inset-0 z-50 opacity-[0.02] mix-blend-overlay bg-[url('data:image/svg+xml;utf8,<svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg"><filter id="n"><feTurbulence type="fractalNoise" baseFrequency="0.65" numOctaves="3" stitchTiles="stitch"/></filter><rect width="100%" height="100%" filter="url(%23n)"/></svg>')]"></div>
```

---

## 2. Mesh Gradients (Bức tranh màu sắc)

Thay vì gradient tuyến tính, dùng blurry blobs:
```html
<div class="absolute top-1/4 left-1/4 w-96 h-96 bg-purple-500/30 rounded-full blur-[120px] mix-blend-screen animate-pulse"></div>
<div class="absolute top-1/3 right-1/4 w-[400px] h-[400px] bg-cyan-500/20 rounded-full blur-[150px] mix-blend-screen animate-pulse [animation-delay:2s]"></div>
```

---

## 3. Premium Visual Formula

### Viền siêu mỏng
- Dark: `border border-white/[0.08]`
- Light: `border border-black/[0.04]`
- KHÔNG dùng viền đậm

### Card Hover Glow
```
hover:-translate-y-1 hover:border-white/20 hover:bg-white/[0.06] transition-all duration-500 ease-out
```

### Text Gradient (Tiêu đề lớn)
```html
<h1 class="text-5xl font-extrabold tracking-tighter bg-clip-text text-transparent bg-gradient-to-r from-white via-zinc-200 to-zinc-500">
```

### Nền Grid/Dot cao cấp
```html
<div class="absolute inset-0 bg-[linear-gradient(to_right,#8080800a_1px,transparent_1px),linear-gradient(to_bottom,#8080800a_1px,transparent_1px)] bg-[size:14px_24px]"></div>
```

### Radial Glow
```html
<div class="absolute top-0 z-[-10] h-screen w-screen bg-[radial-gradient(100%_50%_at_50%_0%,rgba(120,119,198,0.15)_0%,rgba(255,255,255,0)_100%)]"></div>
```

---

## 4. Micro-Interactions

1. **Hover Card**: `hover:-translate-y-1 hover:border-white/20 transition-all duration-500`
2. **Nút bấm**: `active:scale-[0.97] transition-transform`
3. **Staggered Entrance**: Các phần tử xuất hiện lần lượt 100ms-500ms
4. **SVG Draw Animation**: `stroke-dasharray` + `stroke-dashoffset` animate

---

## 5. Quy tắc coding

1. KHÔNG dùng layout cơ bản. Dùng timeline, tab, hoặc sliding cards
2. Chỉ 1 accent color (~10%), 90% neutral tones
3. Icon PHẢI dùng SVG inline hoặc Lucide Icons. TUYỆT ĐỐI KHÔNG dùng emoji (✅, 🐋, 🔍, 🔄, 📊, 🛡️, ✏️, ⌨️, 🧠...) trong UI. Emoji phá vỡ thiết kế chuyên nghiệp.
4. Copywriting có hồn, truyền cảm hứng
5. Responsive bằng Tailwind `md:`, `lg:`
6. Font: Inter cho UI, JetBrains Mono cho code

---

## 6. Modern 2025-2026 Patterns

### Glassmorphism 2.0
```css
.glass {
  background: rgba(255, 255, 255, 0.03);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 24px;
}
```

### Bento Grid Layout
- Layout dạng lưới với các ô kích thước khác nhau (1x1, 2x1, 2x2)
- Dùng CSS Grid: `grid-template-columns: repeat(4, 1fr)`, mỗi item span column/row khác nhau
- Mỗi ô là 1 card độc lập với nội dung riêng, hover glow effect

### Skeleton Loading
```css
.skeleton {
  background: linear-gradient(90deg, #1a1a2e 25%, #252540 50%, #1a1a2e 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}
@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
```

### Scroll-Driven Animations
```css
@keyframes fade-up {
  from { opacity: 0; transform: translateY(30px); }
  to { opacity: 1; transform: translateY(0); }
}
.reveal {
  animation: fade-up linear both;
  animation-timeline: view();
  animation-range: entry 0% entry 100%;
}
```

### Container Queries
```css
@container (min-width: 400px) {
  .card { flex-direction: row; }
}
```

### Neon Accent Mode (cho dark theme cao cấp)
```css
.neon-accent {
  box-shadow: 0 0 20px rgba(99, 102, 241, 0.3), 0 0 60px rgba(99, 102, 241, 0.1);
  border-color: rgba(99, 102, 241, 0.5);
}
```

### Variable Fonts
```html
<link href="https://fonts.googleapis.com/css2?family=Inter:opsz,wght@14..32,100..900&display=swap" rel="stylesheet">
```
Dùng weight biến thiên 100-900, optical sizing tự động.

### Parallax Scrolling Effects
```css
.parallax-layer {
  transform: translateZ(-1px) scale(2);
  will-change: transform;
}
.parallax-container {
  perspective: 1px;
  height: 100vh;
  overflow-x: hidden;
  overflow-y: auto;
}
```

### Advanced Clip Path Animations
```css
.reveal-text {
  clip-path: polygon(0 0, 100% 0, 100% 100%, 0% 100%);
  animation: clipReveal 1s ease-in-out;
}
@keyframes clipReveal {
  from { clip-path: polygon(0 0, 0 0, 0 100%, 0% 100%); }
  to { clip-path: polygon(0 0, 100% 0, 100% 100%, 0% 100%); }
}
```

### Liquid/Blob Morphing Animations
```html
<svg class="absolute -z-10" viewBox="0 0 800 800">
  <defs>
    <linearGradient id="blob-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:rgb(99,102,241);stop-opacity:0.3" />
      <stop offset="100%" style="stop-color:rgb(139,92,246);stop-opacity:0.3" />
    </linearGradient>
  </defs>
  <path class="animate-blob" fill="url(#blob-gradient)" d="M400,200 Q600,200 600,400 T400,600 Q200,600 200,400 T400,200 Z">
    <animate attributeName="d" dur="10s" repeatCount="indefinite"
      values="M400,200 Q600,200 600,400 T400,600 Q200,600 200,400 T400,200 Z;
              M380,180 Q620,220 580,420 T420,620 Q180,580 220,380 T380,180 Z;
              M400,200 Q600,200 600,400 T400,600 Q200,600 200,400 T400,200 Z"/>
  </path>
</svg>
```

### Text Scramble Effect (Cyberpunk Style)
```js
function scrambleText(element, finalText) {
  const chars = '!<>-_\\/[]{}—=+*^?#________';
  let iteration = 0;
  const interval = setInterval(() => {
    element.innerText = finalText.split('').map((char, index) => {
      if(index < iteration) return finalText[index];
      return chars[Math.floor(Math.random() * chars.length)];
    }).join('');
    if(iteration >= finalText.length) clearInterval(interval);
    iteration += 1/3;
  }, 30);
}
```

---

## 7. Templates Mẫu Cho Các Loại Trang

### Landing Page SaaS:
Nav → Hero(Gradient+Illustration) → Clients Logo Bar → Features(3-cards) → Stats Counter → CTA → Footer

### Portfolio Creative:
Nav(glass) → Hero(Mesh gradient+typewriter) → Work Grid(bento) → About(split) → Skills(marquee) → Contact(form) → Footer

### Dashboard Admin:
Sidebar(fixed) → Header(sticky) → Stats Row(4 cards) → Charts Grid(2x2) → Table → Footer

### E-commerce Product Page:
Nav → Product(2-col: gallery+info) → Features Tabs → Related Products Carousel → Reviews → Footer

---

## 8. Performance Rules

1. **Font**: Chỉ load weight cần dùng (400, 500, 700), không load tất cả
2. **Animation**: Dùng `will-change: transform` cho element animate
3. **Image**: Luôn `loading="lazy"` + `decoding="async"` + WebP format
4. **CSS**: Không import font trong CSS file — dùng `<link>` trong `<head>`
5. **JS**: Defer non-critical JS (`<script defer>`)

---

### Ví dụ đúng/sai

**SAI (emoji trong UI):**
```html
<div class="text-2xl mb-2">🔍</div>
<div class="text-2xl mb-2">✅</div>
```

**ĐÚNG (SVG inline):**
```html
<div class="w-12 h-12 rounded-xl bg-violet-500/10 flex items-center justify-center">
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#8b5cf6" stroke-width="2">
    <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
  </svg>
</div>
```


---

## 9. Modern JS Libraries & Framework Combinations

### Animation Libraries Priority Order
1. **Framer Motion** (React) - Cho smooth animations, layout transitions
2. **GSAP** - Cho complex timeline animations, scroll-triggered effects
3. **Three.js** - Cho 3D backgrounds, particle systems, WebGL effects
4. **Lottie** - Cho After Effects animations (icons, illustrations)
5. **AOS (Animate On Scroll)** - Cho simple scroll reveals

### UI Component Libraries (Chọn theo stack)
**React:**
- **shadcn/ui** + **Radix UI** - Headless, fully customizable, Tailwind-first
- **Headless UI** - Official Tailwind component primitives
- **Chakra UI** - Full-featured với dark mode built-in
- **Framer Motion** - Luôn kết hợp với shadcn/ui

**Vue:**
- **Nuxt UI** - Modern, Tailwind-based, Vue 3
- **PrimeVue** - Enterprise-ready với nhiều themes
- **Vuetify** - Material Design 3

**Vanilla JS / Any Framework:**
- **Alpine.js** - Minimal reactive framework (như jQuery modern)
- **Lit** - Web Components standard
- **HTMX** - Server-side rendering với minimal JS

### Icon Systems (Theo thứ tự ưu tiên)
1. **Lucide React** - Clean, consistent, tree-shakeable
2. **Heroicons** - Tailwind official icons
3. **Phosphor Icons** - 6 weight variants mỗi icon
4. **Tabler Icons** - 3000+ icons, pixel-perfect

### Chart/Data Visualization
1. **Chart.js** - Simple, canvas-based, good for dashboards
2. **Recharts** (React) - Composable, declarative charts
3. **ECharts** - Feature-rich, 3D charts, maps
4. **D3.js** - Full control, custom interactive visualizations

---

## 10. Design Patterns By Use Case

### Startup Landing Page
```
Structure:
├── Hero (Mesh gradient background, bold headline, CTA)
├── Social Proof (Logo cloud with blur effect)
├── Features Grid (3 cols, icon + title + description)
├── Demo Video (Glassmorphism player with custom controls)
├── Testimonials (Carousel with fade transition)
├── Pricing (Bento-style cards với highlight on middle tier)
└── CTA Section (Gradient background + email capture)

Tech Stack:
- React + Framer Motion
- shadcn/ui components
- Lucide icons
- GSAP for scroll animations
```

### Portfolio / Agency Site
```
Structure:
├── Nav (Glass morphism, sticky)
├── Hero (Split screen: Text left, 3D visual right)
├── Work Grid (Masonry layout, hover reveal info)
├── Process Timeline (Vertical with scroll-triggered animations)
├── Clients (Infinite scroll marquee)
├── About (Parallax image + text)
└── Contact (Animated form với validation feedback)

Tech Stack:
- Three.js background (particle system)
- GSAP ScrollTrigger
- Masonry grid library
- Intersection Observer API
```

### SaaS Dashboard
```
Structure:
├── Sidebar (Fixed, collapsible, icon + text)
├── Header (Search, notifications, user dropdown)
├── Stats Row (4 cards: metrics + sparkline charts)
├── Main Content Area (Table với sorting/filtering)
├── Charts Section (2x2 grid: line, bar, doughnut, area)
└── Recent Activity (Timeline component)

Tech Stack:
- React + TanStack Table
- Chart.js or Recharts
- Zustand (state management)
- React Hook Form + Zod (forms)
```

### E-commerce Product Page
```
Structure:
├── Breadcrumb navigation
├── Product Gallery (Zoom on hover, thumbnails, 360° view)
├── Product Info (Title, rating, price, size selector, add to cart)
├── Description Tabs (Details, Specs, Reviews)
├── Related Products (Horizontal scroll carousel)
└── Recently Viewed (Sticky bottom bar)

Tech Stack:
- Swiper.js (gallery carousel)
- React Zoom Pan Pinch
- Star rating component
- Add to cart animation (Framer Motion)
```

---

## 11. Color Psychology & Palettes

### Industry-Specific Color Schemes

**Tech / SaaS:**
- Primary: Blue (#2563eb) / Violet (#8b5cf6)
- Accent: Cyan (#06b6d4) / Pink (#ec4899)
- Neutral: Slate/Zinc scales
- Vibe: Professional, trustworthy, innovative

**Creative / Agency:**
- Primary: Purple (#a855f7) / Orange (#f97316)
- Accent: Yellow (#eab308) / Green (#10b981)
- Neutral: Warm grays
- Vibe: Bold, energetic, creative

**Finance / Legal:**
- Primary: Navy (#1e3a8a) / Forest (#064e3b)
- Accent: Gold (#d97706) / Teal (#0d9488)
- Neutral: Cool grays
- Vibe: Stable, secure, authoritative

**Health / Wellness:**
- Primary: Teal (#14b8a6) / Sage (#84cc16)
- Accent: Sky blue (#0ea5e9) / Coral (#fb923c)
- Neutral: Warm whites
- Vibe: Calming, natural, caring

**Gaming / Entertainment:**
- Primary: Neon purple (#c026d3) / Electric blue (#0284c7)
- Accent: Neon green (#22c55e) / Hot pink (#f43f5e)
- Neutral: Dark slate (almost black)
- Vibe: Exciting, immersive, energetic

### Gradient Combinations (Copy-paste ready)
```css
/* Sunset */
bg-gradient-to-br from-rose-500 via-orange-400 to-yellow-300

/* Ocean */
bg-gradient-to-br from-blue-600 via-cyan-500 to-teal-400

/* Purple Dream */
bg-gradient-to-br from-purple-600 via-pink-500 to-rose-400

/* Forest */
bg-gradient-to-br from-emerald-600 via-green-500 to-lime-400

/* Midnight */
bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900

/* Cyberpunk */
bg-gradient-to-br from-fuchsia-600 via-purple-600 to-blue-600
```

---

## 12. Advanced CSS Techniques

### Custom Scrollbar Styling
```css
/* Dark Theme */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
::-webkit-scrollbar-track {
  background: rgba(255,255,255,0.02);
  border-radius: 10px;
}
::-webkit-scrollbar-thumb {
  background: rgba(255,255,255,0.1);
  border-radius: 10px;
  transition: background 0.2s;
}
::-webkit-scrollbar-thumb:hover {
  background: rgba(255,255,255,0.2);
}
```

### Text Selection Styling
```css
::selection {
  background-color: rgba(139, 92, 246, 0.3);
  color: white;
}
::-moz-selection {
  background-color: rgba(139, 92, 246, 0.3);
  color: white;
}
```

### Focus Visible (Accessibility + Beauty)
```css
*:focus-visible {
  outline: 2px solid rgb(139, 92, 246);
  outline-offset: 2px;
  border-radius: 4px;
}
```

### Backdrop Filter Compatibility
```css
.glass-effect {
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  /* Fallback for unsupported browsers */
  @supports not (backdrop-filter: blur(20px)) {
    background: rgba(255, 255, 255, 0.15);
  }
}
```

### Smooth Scroll Snap
```css
.scroll-container {
  scroll-snap-type: y mandatory;
  scroll-behavior: smooth;
  overflow-y: scroll;
}
.scroll-section {
  scroll-snap-align: start;
  scroll-snap-stop: always;
  min-height: 100vh;
}
```

---

## 13. Performance Optimization Checklist

### Images
- [ ] Sử dụng WebP format với AVIF fallback
- [ ] Lazy loading: `loading="lazy"` cho tất cả images below-the-fold
- [ ] Responsive images: `srcset` với multiple sizes
- [ ] Blur placeholder với LQIP (Low Quality Image Placeholder)
- [ ] Dimensions specified: `width` + `height` attributes để prevent layout shift

```html
<img 
  src="image.webp" 
  srcset="image-400.webp 400w, image-800.webp 800w, image-1200.webp 1200w"
  sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
  alt="Descriptive alt text"
  loading="lazy"
  decoding="async"
  width="1200"
  height="800"
  class="blur-sm transition-all duration-300 data-[loaded]:blur-0"
/>
```

### Fonts
```html
<!-- Preconnect to font CDNs -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>

<!-- Load only needed weights + display=swap -->
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&display=swap" rel="stylesheet">
```

### CSS
- [ ] Critical CSS inline trong `<head>` (above-the-fold styles)
- [ ] Non-critical CSS defer load hoặc async
- [ ] Purge unused CSS với PurgeCSS hoặc Tailwind JIT
- [ ] CSS Grid > Flexbox khi có thể (better performance)
- [ ] Avoid excessive `box-shadow` và `filter` (GPU intensive)

### JavaScript
```html
<!-- Critical JS: inline trong <head> -->
<script>
  // Dark mode detection, theme initialization
</script>

<!-- Non-critical JS: defer -->
<script defer src="main.js"></script>

<!-- Third-party scripts: async hoặc defer -->
<script async src="analytics.js"></script>
```

### Animation Performance
```css
/* GOOD - Hardware accelerated */
.fast-animation {
  will-change: transform, opacity;
  transform: translateX(0);
  transition: transform 0.3s ease-out;
}

/* BAD - Triggers layout recalculation */
.slow-animation {
  transition: width 0.3s, left 0.3s;
}
```

---

## 14. Accessibility (A11y) Requirements

### Semantic HTML Structure
```html
<header>
  <nav aria-label="Main navigation">
    <ul>
      <li><a href="/" aria-current="page">Home</a></li>
    </ul>
  </nav>
</header>

<main>
  <article>
    <h1>Page Title</h1>
    <section aria-labelledby="intro-heading">
      <h2 id="intro-heading">Introduction</h2>
    </section>
  </article>
</main>

<aside aria-label="Related articles">
  <!-- Sidebar content -->
</aside>

<footer>
  <!-- Footer content -->
</footer>
```

### Keyboard Navigation
- [ ] Tất cả interactive elements phải có `tabindex` hợp lý
- [ ] Focus states rõ ràng với `focus-visible`
- [ ] Skip to main content link: `<a href="#main" class="sr-only">Skip to main content</a>`
- [ ] Dropdown menus: Escape để đóng, Arrow keys để navigate

### Screen Reader Support
```html
<!-- Aria labels cho icon-only buttons -->
<button aria-label="Close menu">
  <svg>...</svg>
</button>

<!-- Aria-describedby cho form errors -->
<input 
  id="email" 
  aria-describedby="email-error"
  aria-invalid="true"
/>
<p id="email-error" class="text-red-500">Invalid email format</p>

<!-- Aria-live cho dynamic content -->
<div aria-live="polite" aria-atomic="true">
  Loading results...
</div>
```

### Color Contrast
- Normal text: minimum 4.5:1 ratio
- Large text (18px+ or 14px+ bold): minimum 3:1 ratio
- Interactive elements: minimum 3:1 against background

Test tool: https://webaim.org/resources/contrastchecker/

---

## 15. Code Quality Standards

### Component File Structure (React example)
```
components/
├── ui/                  # Shared UI primitives
│   ├── Button.tsx
│   ├── Card.tsx
│   └── Input.tsx
├── features/            # Feature-specific components
│   ├── auth/
│   │   ├── LoginForm.tsx
│   │   └── SignupForm.tsx
│   └── dashboard/
│       ├── StatsCard.tsx
│       └── ChartWidget.tsx
└── layouts/             # Layout components
    ├── Header.tsx
    ├── Sidebar.tsx
    └── Footer.tsx
```

### Naming Conventions
- **Components**: PascalCase (`Button`, `ProductCard`)
- **Files**: Match component name (`Button.tsx`, `ProductCard.tsx`)
- **CSS classes**: kebab-case hoặc Tailwind utilities
- **Functions**: camelCase (`handleClick`, `fetchUserData`)
- **Constants**: SCREAMING_SNAKE_CASE (`API_BASE_URL`, `MAX_RETRIES`)

### Comment Guidelines
```tsx
// GOOD: Explain WHY, not WHAT
// Using backdrop-filter for glassmorphism since we need Safari support
// and -webkit prefix is required for iOS 15.4+

// BAD: Obvious comments
// This is a button
<button className="btn">Click me</button>
```

### Props Destructuring & TypeScript
```tsx
interface ButtonProps {
  variant?: 'primary' | 'secondary' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  children: React.ReactNode;
  onClick?: () => void;
}

export function Button({
  variant = 'primary',
  size = 'md',
  isLoading = false,
  children,
  onClick
}: ButtonProps) {
  return (
    <button
      className={cn(
        'rounded-xl font-medium transition-all',
        variantStyles[variant],
        sizeStyles[size],
        isLoading && 'opacity-50 cursor-not-allowed'
      )}
      onClick={onClick}
      disabled={isLoading}
    >
      {isLoading ? <Spinner /> : children}
    </button>
  );
}
```

---

## 16. Testing Checklist Before Delivery

### Visual Testing
- [ ] Kiểm tra trên Chrome, Firefox, Safari
- [ ] Kiểm tra trên mobile (iOS Safari, Chrome Android)
- [ ] Kiểm tra ở các breakpoints: 375px, 768px, 1024px, 1920px
- [ ] Dark mode hoạt động đúng (nếu có)
- [ ] Không có horizontal scrollbar ở bất kỳ breakpoint nào
- [ ] Images load và display đúng tỷ lệ
- [ ] Fonts load đúng (không flash FOUT/FOIT)

### Functional Testing
- [ ] All links navigate đúng
- [ ] Forms submit và validate đúng
- [ ] Buttons có hover/active/focus states
- [ ] Modals open/close đúng
- [ ] Dropdowns expand/collapse đúng
- [ ] Animations chạy smooth (60fps)
- [ ] Scroll behavior smooth và natural

### Performance Testing
- [ ] Lighthouse score: Performance > 90
- [ ] First Contentful Paint < 1.8s
- [ ] Largest Contentful Paint < 2.5s
- [ ] Cumulative Layout Shift < 0.1
- [ ] Total bundle size < 200KB (gzipped)

### Accessibility Testing
- [ ] Keyboard navigation hoạt động hoàn toàn
- [ ] Screen reader test với NVDA/JAWS
- [ ] Color contrast ratios pass WCAG AA
- [ ] Focus indicators visible rõ ràng
- [ ] Alt text có ý nghĩa cho all images

---

## 17. AI Agent Workflow

Khi nhận task tạo UI, AI agent BẮT BUỘC phải:

1. **Xác định context:**
   - Đây là trang gì? (Landing, Dashboard, Product, Portfolio)
   - User persona? (Developer, Business, Creative, Consumer)
   - Brand vibe? (Professional, Playful, Luxury, Minimal)

2. **Chọn tech stack:**
   - Framework: React / Vue / Vanilla JS
   - Component library: shadcn/ui / Chakra / Headless UI
   - Animation: Framer Motion / GSAP / AOS
   - Icons: Lucide / Heroicons / Phosphor

3. **Thiết kế color palette:**
   - Chọn 1 accent color từ Section 11
   - Neutral scale: Slate / Zinc / Gray
   - Verify contrast ratios

4. **Code structure:**
   - Semantic HTML5 elements
   - Mobile-first Tailwind classes
   - Responsive breakpoints: md: / lg: / xl:
   - Component composition (DRY principle)

5. **Visual polish:**
   - Add glassmorphism / gradient mesh
   - Hover states cho all interactive elements
   - Loading states cho async operations
   - Error states cho form validation
   - Empty states cho no-data scenarios

6. **Performance optimization:**
   - Lazy load images
   - Defer non-critical JS
   - Inline critical CSS
   - Tree-shake unused code

7. **Accessibility check:**
   - Semantic HTML
   - ARIA labels where needed
   - Keyboard navigation
   - Focus management

8. **Testing:**
   - Visual test ở 3 breakpoints minimum
   - Functional test all interactions
   - Performance test với Lighthouse

9. **Documentation:**
   - Comment complex logic
   - Provide usage examples
   - List dependencies + versions

---

## 18. Common Mistakes to AVOID

### ❌ Using Emojis in Production UI
```html
<!-- BAD -->
<div class="text-2xl">🔍 Search</div>

<!-- GOOD -->
<div class="flex items-center gap-2">
  <SearchIcon className="w-6 h-6" />
  <span>Search</span>
</div>
```

### ❌ Inline Styles Instead of Tailwind
```html
<!-- BAD -->
<div style="margin-top: 20px; color: #333;">Content</div>

<!-- GOOD -->
<div class="mt-5 text-gray-700">Content</div>
```

### ❌ Missing Alt Text
```html
<!-- BAD -->
<img src="hero.jpg">

<!-- GOOD -->
<img src="hero.jpg" alt="Team collaboration in modern office space">
```

### ❌ Fixed Pixel Widths
```html
<!-- BAD -->
<div style="width: 600px;">Content</div>

<!-- GOOD -->
<div class="w-full max-w-2xl mx-auto">Content</div>
```

### ❌ Non-Semantic HTML
```html
<!-- BAD -->
<div class="header">
  <div class="nav">...</div>
</div>

<!-- GOOD -->
<header>
  <nav aria-label="Main navigation">...</nav>
</header>
```

### ❌ Blocking Script Tags
```html
<!-- BAD -->
<script src="heavy-library.js"></script>

<!-- GOOD -->
<script defer src="heavy-library.js"></script>
```

---

## 19. Quick Reference Commands

### Install Tailwind + PostCSS
```bash
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

### Install shadcn/ui
```bash
npx shadcn-ui@latest init
npx shadcn-ui@latest add button card input
```

### Install Framer Motion
```bash
npm install framer-motion
```

### Install Icons
```bash
npm install lucide-react       # React
npm install @heroicons/react   # React (Tailwind official)
npm install phosphor-react     # React with variants
```

### Install GSAP
```bash
npm install gsap
```

### Install Chart Libraries
```bash
npm install chart.js react-chartjs-2  # Chart.js for React
npm install recharts                  # Recharts (React native)
```

---

## 20. Final Mandate

**EVERY UI component created by AI agent MUST:**

✅ Use SVG icons (Lucide/Heroicons), NEVER emojis  
✅ Be fully responsive (mobile-first)  
✅ Have hover/focus states on all interactive elements  
✅ Use glassmorphism or gradient mesh backgrounds  
✅ Include loading/error/empty states  
✅ Pass WCAG AA accessibility standards  
✅ Lazy load below-the-fold images  
✅ Have smooth transitions (200-300ms duration)  
✅ Use semantic HTML5 elements  
✅ Include proper TypeScript types (if React/Vue)  

**If ANY of these are missing, the work is INCOMPLETE.**
