# OrcaCode Design System

This file defines the mandatory design system for ALL UI/frontend tasks.

## Mandatory Framework

For ALL web UI tasks, you MUST use **Tailwind CSS**. Plain CSS is forbidden when Tailwind is available.

### Setup Check
- If `tailwindcss` is NOT in package.json → install it: `npm install -D tailwindcss @tailwindcss/vite` (or appropriate plugin)
- Always use Tailwind v4 with `@tailwindcss/vite` or equivalent plugin
- Configure `tailwind.config.js` if not present
- Use Tailwind utility classes as primary styling, inline styles only for truly dynamic values

## Design Style Selection

Before writing ANY UI code, randomly select ONE design style from the list below. Do NOT reuse the same style. Cycle through them. The selection must be deliberate: name it in your plan, then apply its patterns consistently throughout the entire UI.

### 1. Modern Clean (default)
**Philosophy**: Clarity, white space, strong grid
- `bg-white text-gray-900`
- Generous padding: `px-8 py-6`, `gap-8`, `space-y-6`
- Max-width containers: `max-w-6xl mx-auto`
- Rounded minimal: `rounded-xl` on cards, `rounded-full` on buttons
- Shadow light: `shadow-sm` on cards, `shadow-lg` on hover
- Primary: `bg-indigo-600 hover:bg-indigo-700 text-white`
- Typography: `text-4xl font-bold` headings, `text-lg text-gray-600` body
- CTA: `px-8 py-4 text-lg font-semibold rounded-full`

### 2. Dark Minimal
**Philosophy**: Sophisticated, high contrast, minimal decoration
- `bg-gray-950 text-gray-100`
- Subtle borders: `border border-gray-800`
- Cards: `bg-gray-900 rounded-2xl border border-gray-800`
- Primary accent: `bg-emerald-500 hover:bg-emerald-400 text-gray-950`
- Secondary: `text-emerald-400`
- Typography: `font-light tracking-tight`, headings `text-5xl font-extralight`
- CTA: `px-6 py-3 bg-emerald-500 text-gray-950 font-medium rounded-lg`
- No heavy shadows, use borders instead

### 3. Glassmorphism
**Philosophy**: Translucent layers, blur, depth
- `bg-gradient-to-br from-purple-900 via-blue-900 to-indigo-900`
- Cards: `bg-white/10 backdrop-blur-xl border border-white/20 rounded-3xl`
- Text: `text-white` with `text-white/70` for secondary
- Primary: `bg-white/20 hover:bg-white/30 backdrop-blur-md text-white`
- Blur backgrounds: `backdrop-blur-2xl backdrop-blur-3xl`
- Subtle gradients on borders: `border-white/10`
- Typography: `font-light` with generous letter spacing `tracking-wide`
- CTA: `bg-white text-gray-900 px-8 py-4 rounded-2xl font-semibold shadow-2xl`

### 4. Brutalist Neo
**Philosophy**: Raw, bold, high contrast, sharp edges
- `bg-yellow-400 text-black` or `bg-lime-300 text-black`
- NO rounded corners: `rounded-none`
- Thick black borders: `border-4 border-black`
- Hard shadows: `shadow-[8px_8px_0px_0px_rgba(0,0,0,1)]`
- Cards: `bg-white border-4 border-black p-6`
- Typography: `font-black uppercase tracking-tighter`, headings `text-7xl`
- Primary: `bg-black hover:bg-gray-800 text-white`
- CTA: `bg-black text-white px-10 py-5 text-xl font-black uppercase border-4 border-black hover:bg-white hover:text-black`

### 5. Neumorphism
**Philosophy**: Soft 3D, embedded feel, monochrome
- `bg-gray-100` (light) or `bg-gray-900` (dark)
- Cards: `rounded-3xl bg-gray-100 shadow-[20px_20px_60px_#bebebe,-20px_-20px_60px_#ffffff]`
- Buttons (pressed): `shadow-[inset_5px_5px_10px_#bebebe,inset_-5px_-5px_10px_#ffffff]`
- Typography: `font-medium text-gray-700`
- Primary: `bg-gradient-to-br from-blue-500 to-purple-600 text-white rounded-2xl`
- No hard borders, everything through shadow depth
- CTA: `shadow-[8px_8px_16px_#bebebe,-8px_-8px_16px_#ffffff] hover:shadow-[inset_4px_4px_8px_#bebebe,inset_-4px_-4px_8px_#ffffff]`

### 6. Gradient Aurora
**Philosophy**: Vibrant gradients, flowing colors, energetic
- `bg-gray-50` base with gradient hero sections
- Hero: `bg-gradient-to-br from-pink-500 via-purple-500 to-indigo-500`
- Cards: `bg-white rounded-2xl shadow-xl border border-gray-100`
- Text gradients: `bg-gradient-to-r from-pink-500 to-purple-600 bg-clip-text text-transparent`
- Primary: `bg-gradient-to-r from-pink-500 to-purple-600 hover:from-pink-600 hover:to-purple-700`
- Accent circles/blobs: `absolute rounded-full bg-gradient-to-r blur-3xl opacity-30`
- Typography: `font-bold`, headings `text-5xl md:text-7xl`
- CTA: `bg-gradient-to-r from-pink-500 to-purple-600 text-white px-10 py-5 rounded-full font-bold text-lg`

### 7. Swiss Modern
**Philosophy**: Typographic, asymmetric grid, Helvetica
- `bg-white text-black`
- Strict grid: `grid grid-cols-12` with asymmetric spans
- Typography: `font-['Helvetica Neue']` or `font-sans`, headings `text-6xl font-black tracking-[-0.04em]`
- Color accent: single vibrant color only — `text-red-600` or `text-blue-600`
- Cards: `bg-white border-b-2 border-black` (underline only, no full border)
- Minimal decoration, maximum type impact
- Numbers large: `text-8xl font-black`
- CTA: `border-b-2 border-black font-bold text-lg hover:border-red-600 hover:text-red-600`

### 8. Organic Soft
**Philosophy**: Warm, friendly, rounded everything, nature palette
- `bg-stone-50 text-stone-800`
- Fully rounded: `rounded-[2rem]` cards, `rounded-full` everything else
- Colors: `bg-amber-100`, `bg-emerald-50`, `bg-orange-50`
- Cards: `bg-white rounded-[2rem] p-8 shadow-sm border border-stone-200`
- Primary: `bg-emerald-600 hover:bg-emerald-700 text-white`
- Typography: `font-serif` for headings, `text-amber-800` for accents
- CTA: `bg-emerald-600 text-white px-8 py-4 rounded-full font-medium text-lg shadow-lg shadow-emerald-200`
- Soft pastel hover states

## Style Selection Rules

1. **Random pick**: Each new UI task MUST randomly select from styles 1-8.
2. **Name the style**: State your selection at the start: "Style: Brutalist Neo"
3. **Full commitment**: Apply the chosen style to EVERY element. No mixing styles.
4. **Consistency check**: After finishing, verify every color, radius, shadow, and font matches the chosen style.
5. **Cycle through**: Track which styles you've used and prefer unused ones.

## Layout Patterns

- Use `container mx-auto px-4` or `max-w-7xl mx-auto px-4 sm:px-6 lg:px-8`
- Sections: `py-16 md:py-24`
- Grid: `grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8`
- Flex centering: `flex items-center justify-center`
- Stack gaps: `space-y-4` or `gap-4` with flex/grid
- Responsive: Always include `sm:`, `md:`, `lg:` breakpoints

## Motion & Animation

- Use Tailwind's `transition`, `duration-*`, `ease-*` for simple transitions
- For richer animation, use `animate-*` with custom `@keyframes` in `<style>` tag
- Prefer: `transition-all duration-300 ease-out`
- Hover scale: `hover:scale-105 transition-transform`
- Fade in: `animate-[fadeIn_0.5s_ease-out]`
- Keep all animations under 500ms, prefer 200-300ms
- No motion that disorients; motion must serve clarity

## Forbidden Patterns

- Do NOT use generic gray-on-white with blue buttons (the "default template" look)
- Do NOT use `rounded-md` on everything without intention
- Do NOT skip responsive design
- Do NOT mix Tailwind with inline `<style>` blocks for the same element
- Do NOT leave `bg-white` cards on `bg-gray-50` body without intention — pick a style
