# Project Stack Truth

Use this file as the source of truth before choosing frameworks, libraries, and UI patterns.

## Workspace Map

1. Repository root (`d:\OrcaCode-main`) is a Python application.
2. The main app uses Textual/TUI patterns, not a browser UI framework.
3. The web/docs site lives in `codegraph-main/site`.

## Frontend Reality

- `codegraph-main/site` uses Astro + Starlight.
- Styling is primarily plain CSS and Astro component styling.
- **Tailwind CSS is the PREFERRED styling method** for all new UI work. If Tailwind is not installed in the target project, install it first, then use it.
- **Anime.js**: Install it if animation needs go beyond CSS transitions. Check `package.json` for `animejs` first.
- Always verify the target `package.json` before writing code.

## Mandatory Checks Before Coding

Before writing code, determine the exact target surface:

1. Which subproject is being edited?
2. Which package manager manifest controls that subproject?
3. Which styling system is already present there?
4. Which animation approach is already present there?

Never mix conventions from different subprojects in the same implementation.

## Rules For Library Usage

- Only use a library after confirming it is installed in the target project.
- **Tailwind CSS is mandatory for all web UI code.** Install it if missing.
- If the user requests Anime.js and it is not installed, install it (`npm install animejs`).
- Prefer Tailwind utility classes over raw CSS or inline styles.
- If the repo already has CSS-only patterns, migrate them to Tailwind patterns.

## Rules For UI Work

- Do not generate "template-looking" UI.
- **Always apply a complete design style** (open `.orca/design_system.md` to see the style catalog).
- Use Tailwind utility classes exclusively for styling.
- Randomly select a distinct design style for each new UI task — never repeat the last one used.
- Derive layout, spacing, colors, and motion from the chosen design style.
- Match the stack that is actually present in the target folder.
- If the request is purely backend or Python/TUI, ignore web UI rules entirely.
