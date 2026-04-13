# jetbrains-mcp-workspace.md

## Purpose
Define how agents should use JetBrains, MCP bridges, editor indexes, and workspace tools safely.

## Tool Role
These tools are for:
- navigation
- symbol lookup
- code search
- refactor assistance
- workspace context
- structured actions against local files

They are not repo truth by themselves.

## Rules
- Use JetBrains and MCP to accelerate reading and editing, not to replace source verification.
- Verify critical behavior in actual files, configs, tests, and schemas.
- Do not assume editor indexes are fresh or complete.
- Do not treat generated context windows as canonical truth.
- If editor state and git state diverge, git-tracked repo truth wins.

## Safe Workspace Loop
1. Use indexes/search to find relevant files.
2. Open the actual files.
3. Reconstruct behavior from source and tests.
4. Use IDE/MCP actions to patch narrowly.
5. Re-run validations from the repo, not from assumptions.

## Recommended Uses
- cross-reference symbol definitions
- trace call sites
- inspect file relationships
- perform small scoped refactors
- update multiple touched files when behavior changes

## Forbidden Uses
- broad automated refactors without task approval
- assuming a symbol graph proves runtime behavior
- using generated summaries in place of reading code
- treating IDE state as a substitute for tests

## Receipt Notes
If JetBrains/MCP materially shaped the work, note:
- what it helped locate or patch
- what was still verified manually in repo truth
