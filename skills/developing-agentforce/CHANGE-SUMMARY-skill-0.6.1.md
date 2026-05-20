# Developing Agentforce Skill 0.6.1 Change Summary

Date: 2026-05-20

## Goals

- Reduce redundancy and tighten skill structure.
- Make guidance more requirement-driven and use-case centric.
- Encode product posture: default agentic, deterministic controls with cause.
- Keep adjacent operational references while improving navigation and consistency.

## What Changed

### 1) SKILL Router Simplification

- Simplified `SKILL.md` framing and removed non-load-bearing narrative.
- Added draft-first lifecycle guidance:
  - iterate in draft (validate/deploy/preview)
  - publish + activate only on explicit user approval
- Improved compile-error workflow to explicitly parse concrete returned errors before fix.
- Replaced repeated tail sections with concise reference quick links.

### 2) Spec and Posture Updates

- Reworked `agent-design-and-spec-creation.md` toward outcome-first discovery.
- Added explicit subagent posture considerations in spec design.
- Renamed ambiguous "Directional vs Observational" framing to clearer planned/existing implementation framing.
- Added new `posture-and-determinism.md` reference.

### 3) Architecture/Pattern Consolidation

- Added `patterns-by-requirement.md` as primary pattern selector.
- Repositioned `architecture-patterns.md` as implementation mechanics and migration details.
- Updated naming to **router-first architecture**.
- Removed implied mandatory "back-to-hub" transitions; transitions are now use-case-driven.

### 4) Examples and Asset Hygiene

- Renamed architecture template from `hub-and-spoke.agent` to `router-first.agent`.
- Updated template/readme references accordingly.
- Merged `minimal-examples.md` into `examples.md`; removed redundant file.

### 5) Reference Cleanup and Safety Language

- Added `reference-map.md` to define primary vs supplemental references.
- Updated `README.md` to reflect current structure and references.
- Cleaned stale links and terminology drift in key references.
- Replaced "pattern scoring boost" framing with requirement-fit review guidance in `assets/patterns/README.md`.
- Updated action/deploy/discover/scaffold docs to align with draft-first release posture.

## Notable Non-Goals

- No risky bulk deletions of adjacent references.
- No deep technical rewrites of all long-form docs in this pass.

## Follow-Up Candidates

- Decide if `feature-validity.md` should merge into `actions-reference.md`.
- Decide whether `action-prompt-templates.md` remains standalone or becomes a section in `actions-reference.md`.
- Optional pass to tighten very long legacy references for concision.
