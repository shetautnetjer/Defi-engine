# TMux Machine-Law And Packet Gap

## Stage

Stage 1: current truth consolidation.

## Current truth

The repo already has a policy-only machine-readable swarm packet:

- `.ai/swarm/swarm.yaml`
- `.ai/swarm/lane_rules.yaml`
- `.ai/swarm/promotion_ladder.yaml`
- `.ai/swarm/doc_owners.yaml`

The repo also has a four-lane tmux workflow with research, builder,
architecture, and writer-integrator.

## Gap

The machine-law layer is no longer missing the first research-stage policy
surfaces.

Landed now:

- `.ai/swarm/story_classes.yaml`
- `.ai/swarm/instrument_scope.yaml`
- `.ai/swarm/strategy_registry.yaml`
- `.ai/swarm/metrics_registry.yaml`

The remaining gap is narrower:

- a typed completion and handoff contract that the live supervisor can use
  directly instead of relying on freshness and artifact heuristics alone
- clearer packet/build-order generation for the live swarm when research-stage
  proposal review is enabled

## Why it matters

Without the remaining machine-readable law, the swarm still depends too heavily
on prompt tradition and prose-only packet discipline.

## Close when

- the remaining machine-readable files exist or are explicitly rejected
- the packet read order is encoded clearly enough that future assistants do not
  rediscover it from chat
- docs truth and backlog truth are machine-routable without creating a second
  runtime source of truth
- the live supervisor has a typed enough handoff contract to progress active
  research stories automatically
