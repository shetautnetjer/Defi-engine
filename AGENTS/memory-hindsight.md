# memory-hindsight.md

## Purpose
Define how agents may use Hindsight and related memory systems without letting memory become hidden authority.

## Memory Role
Memory is support for:
- prior decisions
- prior receipts
- prior experiments
- prior bugs
- prior operator preferences
- comparable historical context

Memory is not truth by itself.

## Authority Law
Current repo truth comes from:
- current code
- current config
- current schemas
- current docs
- current tests

If memory conflicts with current repo truth, current repo truth wins.

## Allowed Memory Uses
Agents may use memory to:
- speed up repo understanding
- recall prior design choices
- compare past and current behavior
- surface relevant receipts or artifacts
- propose bounded next steps

## Forbidden Memory Uses
Agents may not use memory to:
- override current behavior without proof
- justify skipping validation
- redefine policy implicitly
- resurrect stale design docs as runtime truth
- substitute for reading the touched files

## Memory Working Loop
1. Read current repo truth first.
2. Pull memory only if it helps answer:
   - what was tried before?
   - what failed before?
   - what policy or decision was previously recorded?
3. Cite memory as supporting context, not final authority.
4. Validate against the current repo before acting.

## Memory Receipt Rules
When memory materially affects a decision, note:
- what memory source was used
- what it suggested
- how it was verified against current repo truth
- whether any conflict existed
