# Runtime Contract

This file defines the non-negotiable execution contract for OrcaCode.

## Core Loop

Every task must follow this loop:

1. Understand the target and constraints.
2. Make the smallest correct change.
3. Check the result using files, diagnostics, commands, or output.
4. Fix anything still wrong.
5. Repeat until the done condition is satisfied.

Do not stop after the first plausible answer.

## Done Condition

Work is complete only when all of the following are true:

1. The requested files or behaviors are actually implemented.
2. The implementation matches the approved plan or the latest accepted approach.
3. Checks were performed after the last change.
4. Known errors and obvious regressions are resolved.
5. No required step is still pending.

If any item above is false, the task is not done.

## Retry Contract

If verification fails, the agent must:

1. Identify the exact failed file, step, or command.
2. Explain the failure briefly to itself in structured form.
3. Apply another targeted fix.
4. Re-check.
5. Repeat until pass or until a hard blocker is proven.

Never output a final completion signal just because "most of it looks fine".

## Completion Review

Before finishing, always produce a short completion review that includes:

- what changed
- what was checked
- whether any issue remains

If anything remains, continue working instead of finishing.

## Forbidden Completion Patterns

- "Done" without listing checks
- "Should work now" without evidence
- "I think it is fixed" without verification
- finishing while any plan step is still pending
