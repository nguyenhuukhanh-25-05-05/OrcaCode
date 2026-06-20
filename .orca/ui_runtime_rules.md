# UI Runtime Rules

Use these rules for UI, frontend, layout, animation, styling, and visual polish tasks.

## Stack Fidelity

1. Confirm the target frontend stack before coding.
2. **Tailwind CSS is mandatory for all UI tasks.** Install it if not present.
3. Use Tailwind utility classes as the primary styling method.
4. If Anime.js is needed, install it first (`npm install animejs`).
5. Reuse the project's existing styling and animation approach first, then enhance with Tailwind.

## Visual Quality Bar

UI is not complete if it still looks like a generic template.

Minimum quality bar:

1. Clear hierarchy
2. Consistent spacing
3. Balanced typography
4. Strong primary action
5. Clean states: hover, focus, active, disabled where relevant
6. Responsive behavior that does not collapse awkwardly

## Beauty Guardrails

- Prefer fewer, stronger sections over many weak sections.
- Prefer one visual idea executed well over many random effects.
- Use contrast, spacing, and hierarchy before using flashy animation.
- Motion should support clarity, not distract from it.
- Avoid muddy colors, random radii, and inconsistent shadows.

## UI Done Condition

A UI task is complete only when:

1. The layout works at the intended sizes.
2. Styling uses Tailwind CSS consistently throughout.
3. A complete design style from `design_system.md` was applied and is visible.
4. Interactive elements have sensible states.
5. Motion, if used, is subtle and intentional.
6. The result looks deliberate, not default.

## UI Retry Contract

If the UI still looks weak after implementation:

1. Re-evaluate hierarchy.
2. Re-evaluate spacing rhythm.
3. Re-evaluate typography scale.
4. Re-evaluate CTA emphasis.
5. Re-check responsiveness.
6. Improve and review again before finishing.
