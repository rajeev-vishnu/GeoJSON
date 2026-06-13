# AGENTS.md

## Pre-commit gate

After any code change, run `pre-commit run --all-files`. If it fails, fix
and re-run until clean. A task is not done until pre-commit passes.
On first run in a fresh clone, run `pre-commit install` first.

Ruff (Python), Biome (JS), Prettier (HTML), and editorconfig (LF / UTF-8)
are all enforced via pre-commit — anything they catch should be fixed.

## Python conventions

### Function calls

- Use keyword arguments for any function call with more than one
  argument. The only exception is positional-only parameters
  (e.g. builtins like `print()`).

### Function ordering

- Place public / entry-point functions first.
- Place private helper functions below the functions that call them,
  not above.

### Blank lines after dedent

- When the indentation level decreases (after a `with` block, `for`
  loop, or `if` branch), add a blank line before the next statement
  at the outer level.

### Nesting depth

- Avoid more than 3 levels of indentation. Refactor into smaller
  functions or use early returns to reduce nesting.

### Naming

- Follow PEP 8 naming conventions.
- Avoid shortened variable names: `hf`, `c`, `tmp`, `res`, `obj`, etc.
- Single-letter variable names are only acceptable in conventional
  cases (simple loop indices, mathematical code).
- Avoid domain-specific abbreviations in variable names — always spell
  out the full concept (e.g. `feature_properties`, not `feat_p`).
- When assigning the return value of a function, name the variable
  after what the function returns — mirror the function name where
  possible: `feature = get_feature(feature_id)`,
  `features_page = get_features_page(bbox, page)`.
- Avoid generic names like `result` or `data`.

### Imports

- Inline / local imports need to be strictly avoided. If it is unavoidable or is needed for lazy loading, reqest for explicit approval.

### Function length

- Keep functions under ~100 lines. Break long functions into smaller,
  single-purpose helpers to improve readability and testability.
