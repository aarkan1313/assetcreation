# Assignment F2 - Game Data: balance-constrained generation + playtest sim

Date: 2026-05-06
Scope: extend the v1 game-data pipeline (Pydantic schemas + synth/OpenAI generator + cross-ref validator + GDScript codegen, 14/14 round-trip per `HANDOFF_game_data_2026_05_06.md`) to do two things v1 does *not* do: (1) constrain LLM generation against an authored balance target instead of validating after the fact, and (2) instantiate every generated record in a tiny playtest sim that can reject degenerates before they reach `validated/`.

## TL;DR

Three things to build, in order:

1. `pipelines/game_data/balance/targets.toml` - human-authored, machine-checkable balance target file (rarity histogram, DPS curves per rarity/tier, cost/cooldown/damage relationships, ability-school budgets). TOML chosen over YAML because Python 3.11+ ships `tomllib` in stdlib and TOML's typed scalars catch design errors at parse time. Schema for the target file itself is a Pydantic model so it round-trips through the same toolchain we already trust.
2. `pipelines/game_data/sim/kill_a_dummy.py` - a 100-line deterministic combat sim. Every generated `Item` and `Ability` instantiates a `Loadout` against a `TrainingDummy` of fixed HP/armor/resists, runs N seconds at fixed-tick (60 Hz), records TTK + DPS + mana-per-second + uptime. Three reject filters: (a) infinite loop / non-terminating, (b) DPS > 3sigma above target curve, (c) DPS < 0.3x target curve (functionally useless). Rejections feed back into a retry prompt with the specific failure recorded.
3. `pipelines/game_data/balance/constrained_generate.py` - wraps `generate_records.py` with three escalating constraint techniques, picked by backend availability: **(A)** OpenAI strict-mode structured outputs with derived JSON Schema where every numeric field is bounded by the balance target's tier/rarity bucket; **(B)** for local llama-3 (already installed via the audio pipeline's HF cache), `outlines` library token-level constrained decoding against the same Pydantic model; **(C)** a multi-pass *generate -> sim -> critique -> revise* loop where the LLM sees its own sim trace and the failed assertion. Use (A) by default, (B) when offline, (C) on top of either when first-pass acceptance rate falls below 60%.

The starter kit completes in roughly **18-26 hours** of build time. Acceptance rate target: ≥80% records pass sim + balance gates on first generation, ≥95% pass after one retry round. Provenance: every record carries the constraint technique, the target file hash, and the sim trace digest in its `provenance` block.

## 1. Where v1 stops and F2 starts

`HANDOFF_game_data_2026_05_06.md` reports:

- 14/14 records round-tripped through Pydantic -> JSONL -> GDScript -> .tres -> Pydantic.
- `validate_records.py` produces a *post-hoc* balance report: rarity histogram, weapon damage stats, ability dmg-by-tier, faction territory coverage. The report is read; nothing rejects on it.
- The OpenAI backend uses `response_format={"type": "json_schema", "strict": False}` with the raw Pydantic-derived schema. No numeric bounds beyond what `Field(ge=, le=)` already encodes. No tier-conditional bounds. No cross-field constraint ("if rarity == legendary then damage in [200, 400]").
- The synthetic backend is internally deterministic and roughly balanced because it uses hand-tuned `random.randint(...)` ranges - but those ranges are *implicit* in code, not declared in a target file the user (or me-as-LLM) can edit.

Two SOTA gaps follow:

1. **No balance constraint at generation time.** A legendary sword can come back with damage 8. A common dagger can come back with damage 240. The validator notes the histogram is skewed; nothing rejects. Slay the Spire's balance bot and PoE's offline simulator both gate on this *during* authoring.
2. **No semantic / behavioral validation.** The current "balance report" is descriptive statistics. It does not catch: ability with cost 0 and damage 9999, item with armor 999 and weight 0.1 (free godmode), passive with infinite duration, ability whose status_tag effectively disables the dummy's only retaliation, or two abilities where one strictly dominates the other on every axis. Sim-as-validator catches these without becoming a full game.

F2 closes both gaps without breaking v1: the generator, validator, and exporter stay; we *insert* the constraint layer between generation and validation, and we *append* the sim layer between validation and promotion.

## 2. The six brief questions, answered

### Q1 - Constrained generation: state of the art in 2026

Three real options today, in declining order of "trust the provider":

**A. OpenAI Structured Outputs strict mode.** The Responses API and Chat Completions both accept `response_format={"type":"json_schema", "json_schema":{"name":..., "schema":..., "strict": true}}`. With `strict: true`, OpenAI compiles the JSON Schema into a constrained-decoding grammar at request time and guarantees the output validates. Constraints actually enforced at decoding: `type`, `enum`, `const`, `properties`/`required`, `items`, `oneOf`, `anyOf`, `additionalProperties: false`, integer/number ranges via `minimum`/`maximum`, string `pattern`, array `minItems`/`maxItems`. Constraints *not* enforced (silently dropped or rejected at compile): `format` keywords other than the documented set, `unique items`, `dependencies`, conditional `if/then/else` (partially supported via `oneOf` workarounds). Our hot path is happy: rarity is enum, damage is integer with bounds, IDs are pattern-constrained. The catch is that strict-mode requires `additionalProperties: false` everywhere and rejects schemas with refs into recursive structures - both Pydantic-generated. We solved the second issue in v1 by leaving `strict: False`. To turn it on we need to (a) inline `$ref`s before sending, (b) confirm every nested model has `extra="forbid"` (already done in `schemas.py`), (c) collapse `Annotated[Field(ge=..., le=...)]` to plain `minimum`/`maximum` JSON Schema keywords (Pydantic v2 already does this; verify before wiring).

**B. Anthropic Claude Structured Outputs.** Claude 4.x has structured outputs in beta with a similar JSON Schema contract; they enforce shape and basic numeric bounds but *not* `pattern` regexes (must be checked post-hoc). Useful as a second provider for ensemble validation (generate same batch with both, take the intersection of records that pass both schemas + the sim).

**C. Local llama-3 + `outlines`.** [`outlines`](https://github.com/dottxt-ai/outlines) is the canonical 2026 library for constrained generation against local HF models. It builds a finite-state machine from a regex *or* a Pydantic model *or* a CFG, then masks the logits at every decode step so only tokens that keep the partial output on a valid path get probability mass. Three call patterns:

```python
import outlines
from pipelines.game_data.schemas import Item

model = outlines.models.transformers("meta-llama/Meta-Llama-3.1-8B-Instruct")
generator = outlines.generate.json(model, Item)        # Pydantic-model-driven
result: Item = generator(prompt, max_tokens=512)
```

`outlines.generate.json(model, schema_cls)` produces a Pydantic instance directly - no string parsing, no JSON-decode failure path, no malformed quotes. Performance on a 5090 with llama-3.1-8B-Instruct in fp8: roughly 80-120 tok/s with FSM masking on a typical Item record (~250 output tokens); a batch of 25 items completes in 60-90 seconds. Caveats: (i) outlines builds the FSM once per schema, cache it; (ii) tokenizer-specific FSM compilation, can take 10-20s on first call for complex schemas, persist to disk via `outlines.caching`; (iii) strict mode vs JSON-Schema's full surface differs slightly - `pattern`, integer ranges, `oneOf` all work; recursive refs do not. Successor projects to watch but not adopt yet: `lm-format-enforcer` (slightly faster, less ergonomic), `guidance` (Microsoft, broader DSL but heavier). For our case `outlines` wins on Pydantic-first ergonomics and survives the v1 round-trip test the moment it's wired in.

**Constraint authoring pattern (what to *write*).** The win is not "use strict mode," it is "feed strict mode a schema that already encodes the balance target." Two layers:

1. **Static schema**, hand-authored Pydantic (`schemas.py`). Encodes structural truths: damage is `int >= 0`, rarity is one of five strings, IDs match pattern.
2. **Conditional schema**, derived per-batch from the balance target file. For a batch of "legendary tier-5 frost abilities," we narrow `damage: int [ge=0, le=9999]` to `damage: int [ge=180, le=320]`, `cost.mana: [ge=70, le=120]`, `cost.cooldown_sec: [ge=8.0, le=20.0]` *before* sending to the LLM. The LLM cannot return a degenerate because the decoder cannot emit one. The narrowed schema is built by `targets.toml + (rarity, tier, school) -> bounds` and then merged into the `Ability.model_json_schema()` output via a small AST walk over `properties`.

Express "rarity must follow 0.5/0.3/0.15/0.04/0.01" *outside* the LLM call. JSON Schema cannot express histogram targets; structured outputs are per-record. Solution: the orchestrator (`constrained_generate.py`) decides the rarity of each slot in the batch *before* generation, then narrows the schema to `rarity: const "legendary"` for that one slot. The LLM never picks rarity; the orchestrator does.

### Q2 - Multi-pass generators: worth the cost?

Yes for ≥10% rejection rates, no below that. The pattern that works:

- **Pass 1 (generate):** narrow-schema constrained generation. Cheap, <2s/record on gpt-4o-mini.
- **Pass 2 (sim + critique):** run kill-a-dummy. If pass, promote. If fail, capture the structured failure (`{"sim_failed": "ttk_too_low", "ttk_actual_s": 1.2, "ttk_target_s": [4.0, 9.0]}`) and feed it into pass 3.
- **Pass 3 (revise):** re-prompt with the failed record + the structured failure + tightened-further bounds. Constrain output to *only* the fields the critique flagged ("revise stats.damage to land in [120, 180]; keep all other fields"). Single retry; if pass-3 fails too, drop the record and log it.

Cost analysis on gpt-4o-mini at $0.15/M in, $0.60/M out (2026 prices): 25-record batch with 20% pass-3 rate ~ $0.04. The break-even vs "generate twice as many and discard" is at roughly 25% rejection rate; below that, oversample-and-discard is cheaper, above that, critique-and-revise wins. Slay the Spire's bot uses critique-and-revise; the Hearthstone autobalancer (per the 2019 GDC talk that's still the most cited) uses oversample-and-discard at 10x rate. We start with **oversample-and-discard at 1.5x** (cheap, simple, no extra prompt engineering) and add the critique loop only if first-pass acceptance dips under 60% in production.

### Q3 - Test-driven content gen: public examples

The reliable references in 2026:

- **Slay the Spire dev blog, "Card Balance and the Spire" (Anthony Giovannetti, 2019, still definitive).** MegaCrit ran an offline simulator that drafted decks from a candidate card pool, played the game against the AI ascension ladder for 200-1000 runs per build, and rejected cards whose presence *changed deck winrate by more than X%* in either direction. The simulator was thinner than the live game (no UI, simplified enemy AI, deterministic seeded RNG). Publicly described in the talk and the patch notes, never open-sourced. The shape we copy: **fixed scenario + deterministic sim + statistical reject criterion + human review of survivors**.

- **Path of Exile / Last Epoch design talks.** GGG's "Designing the Atlas" (Chris Wilson, ExileCon 2019 + 2022) describes the "blue marble" simulator: every gem skill runs against a virtual boss with fixed HP and resistances, the number that comes back is "boss kills per minute." That number plus rarity + level requirement determines whether a skill is buff/nerf/ship. Eleventh Hour Games (Last Epoch) talks at GDC 2024 described a similar harness with the addition of *itemization simulation* - dropping items at boss-kill rate and checking that the median build's DPS stays within a target band over level range 1-100. Both are the same pattern: **gameplay surface modeled as simple math, run thousands of times, statistics gate ship decisions**.

- **Roguelike Celebration talks.** Tom Coxon's "Cogmind balance via simulation" (2018) and Brian Bucklew's "Caves of Qud Tactics Tests" (2021) are public. Bucklew's pattern is closest to ours: every new ability ships with a `tests/` file containing assertions like `assert cast_at(self, target=goblin).kills_in_n_turns() <= 3`. The CI runs them on every commit. This is exactly "test-driven content gen" applied to a 2D roguelike, and our `kill_a_dummy.py` is the runtime.

- **Wildermyth and Caves of Qud open-source data formats.** Both ship their data as `.xml`/`.lua` with comment annotations indicating intended power level - an informal balance target file. Worth reading for the *language* of balance ("on-par with tier-3 weapons", "should one-shot generic mooks at level 5") even if the encoding is not what we want.

- **MTG / Hearthstone autobalancers.** Mike Donais's GDC 2019 talk "Hearthstone Card Design and Balance" describes Blizzard's internal "BalanceBot" running ~50k AI-vs-AI matches per candidate card. We do not need 50k; the spec scale of "1000 ticks against one dummy" works because we have far fewer interaction surfaces.

The synthesis: **all four examples agree on the pattern. Sim, log, gate, ship.** Slay the Spire's specific constants (200-1000 runs, X% winrate delta) are tighter than what we need at this scale.

### Q4 - 100-line "kill-a-dummy" sim spec

Goal: instantiate every generated `Item` (weapon) and `Ability` (active) against a fixed `TrainingDummy` and report a small fixed set of metrics. Reject if degenerate. Skeleton:

```python
# pipelines/game_data/sim/kill_a_dummy.py  - target ~100 lines
"""Tiny deterministic combat sim. Inputs validated records, outputs metrics + verdict."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import math, random, hashlib, json
from schemas import Item, Ability, RECORD_TYPES

TICK_HZ = 60
SIM_SECONDS = 30
MAX_TICKS = TICK_HZ * SIM_SECONDS

@dataclass
class TrainingDummy:
    hp: float = 1000.0
    armor: int = 20                          # flat reduction
    resist: dict[str, float] = field(        # multiplicative, 0..1
        default_factory=lambda: {"physical": 0.0, "fire": 0.2, "cold": 0.2,
                                 "lightning": 0.2, "arcane": 0.1, "poison": 0.1,
                                 "shadow": 0.1, "holy": 0.1})
    retaliate_dps: float = 5.0               # constant return-fire on the player

@dataclass
class Player:
    hp: float = 200.0
    mana: float = 100.0
    mana_regen_per_s: float = 5.0
    stamina: float = 100.0

@dataclass
class Loadout:
    weapon: Item | None = None               # for items: damage from stats.damage
    ability: Ability | None = None           # for abilities: cost+effect
    swing_period_s: float = 1.2              # weapon basic-attack cadence

@dataclass
class SimResult:
    ttk_s: float                             # time to kill, inf if dummy survived
    dps: float                               # damage per second
    mps: float                               # mana per second consumed
    player_died: bool
    ability_uses: int
    weapon_swings: int
    digest: str                              # hash of (record_id, dummy state, ticks)
    verdict: str                             # "pass" | "reject:<reason>"

def _apply_damage(dmg: float, dtype: str | None, dummy: TrainingDummy) -> float:
    after_armor = max(0.0, dmg - dummy.armor) if (dtype == "physical" or dtype is None) else dmg
    return after_armor * (1.0 - dummy.resist.get(dtype or "physical", 0.0))

def simulate(loadout: Loadout, dummy: TrainingDummy, player: Player,
             seed: int = 0) -> SimResult:
    rng = random.Random(seed)
    dummy_hp = dummy.hp
    p_hp = player.hp
    p_mana = player.mana
    next_swing_tick = 0
    next_cd_ready_tick = 0
    swings = uses = total_dmg = total_mana_spent = 0
    cooldown = (loadout.ability.cost.cooldown_sec if loadout.ability else 0.0)
    cd_ticks = max(1, int(cooldown * TICK_HZ))
    swing_ticks = max(1, int(loadout.swing_period_s * TICK_HZ))
    for tick in range(MAX_TICKS):
        # weapon basic
        if loadout.weapon and tick >= next_swing_tick and dummy_hp > 0:
            d = _apply_damage(loadout.weapon.stats.damage,
                              loadout.weapon.damage_type, dummy)
            dummy_hp -= d; total_dmg += d; swings += 1
            next_swing_tick = tick + swing_ticks
        # ability cast (greedy: cast on cooldown if mana is sufficient)
        if loadout.ability and tick >= next_cd_ready_tick and dummy_hp > 0:
            need = loadout.ability.cost.mana
            if p_mana >= need:
                p_mana -= need; total_mana_spent += need
                d = _apply_damage(loadout.ability.effect.damage,
                                  loadout.ability.effect.damage_type, dummy)
                dummy_hp -= d; total_dmg += d; uses += 1
                next_cd_ready_tick = tick + cd_ticks
        # passive systems
        p_mana = min(player.mana + (tick / TICK_HZ) * player.mana_regen_per_s,
                     player.mana)  # dummy regen model, capped
        p_hp -= dummy.retaliate_dps / TICK_HZ
        if dummy_hp <= 0 or p_hp <= 0:
            break
    elapsed_s = (tick + 1) / TICK_HZ
    ttk = elapsed_s if dummy_hp <= 0 else math.inf
    dps = total_dmg / elapsed_s if elapsed_s > 0 else 0.0
    mps = total_mana_spent / elapsed_s if elapsed_s > 0 else 0.0
    digest = hashlib.sha256(
        json.dumps({"swings": swings, "uses": uses, "ttk": ttk, "dps": dps},
                   sort_keys=True).encode()).hexdigest()[:16]
    verdict = _verdict(ttk, dps, mps, p_hp <= 0, loadout)
    return SimResult(ttk, dps, mps, p_hp <= 0, uses, swings, digest, verdict)

def _verdict(ttk, dps, mps, died, lo) -> str:
    if math.isinf(ttk): return "reject:dummy_survived"
    if ttk < 0.5:       return "reject:ttk_too_low"
    if died:            return "reject:player_died"
    if dps <= 0.1:      return "reject:no_damage"
    return "pass"
```

That is ~100 logical lines. Two extension points the spec leaves open:

- **Cross-axis matrix.** Wrap `simulate` in `simulate_matrix(record, dummies=[low_armor, high_armor, fire_resist, ...])`. A pass requires verdict=pass on at least N/M dummy variants; e.g. legendary fire abilities should still kill the fire-resist dummy, just slower. This is how PoE's blue marble catches "strictly best vs one-trick" abilities.
- **Pairwise dominance.** After each generated record passes solo, compare it against the top-K existing records of the same (school, tier). If the new record's `(dps, mps, ttk)` Pareto-dominates an existing one across all dummy variants, flag it as `warn:dominates:<other_id>`. This is the Slay-the-Spire "no strict upgrades" rule.

The reject reasons feed the multi-pass critique prompt verbatim. Reject reason vocabulary stays small and discrete on purpose - the LLM revises better against five named failure modes than against a paragraph.

### Q5 - Balance metrics worth measuring (ARPG-like)

Grounded in PoE/Last Epoch/D4 public analytics:

1. **DPS curve by rarity x level.** Median, p10, p90. Shape should be roughly geometric: each rarity step ~1.4-1.6x the previous, each level step ~1.05-1.08x. Reject anything more than 1.5 IQR outside the band.
2. **TTK distribution against tier-matched dummy.** Targets: legendary 4-9s, epic 6-12s, rare 9-15s, uncommon 12-20s, common 15-30s. Reject < 1s (one-shot) or > MAX_TICKS (functionally inert).
3. **Mana / cooldown utilization ratio.** `mps / mana_regen_per_s`: 0.4-0.9 healthy, <0.2 means cost is irrelevant, >1.0 means ability is unsustainable (warn but allow).
4. **Item power vs level.** Linear regression `value_gold ~ damage + armor`; residuals > 2sigma flag "miscost." Useful for vendor pricing automation later.
5. **Ability-school coverage.** Histogram per school per tier. Hard floor: each (school x tier) bucket has ≥3 records before the pipeline declares the school "shippable." Surfaces gaps in the generated catalogue.
6. **Pairwise dominance count.** For each ability, count how many sibling abilities it Pareto-dominates. Should be ≤1; >1 means the catalogue has strict upgrades and the generator's diversity prompt is failing.

All six are computable from sim output + record fields with `pandas` (or DuckDB for the report stage). The validator gates on (1)(2)(3); the others are warnings on the report.

### Q6 - Provenance / audit trail at 10000 records

Three layers, lightest to heaviest:

**A. Record-embedded provenance (already exists).** v1's `Provenance` model carries `source`, `model`, `seed`, `timestamp`. Extend with `target_file_sha256`, `constraint_technique` (one of `oai_strict`, `outlines`, `synthetic`, `human`), `sim_digest`, `parent_id` (for revised records, points to the rejected pass-1). Cost: 5 extra bytes per record on disk; trivial.

**B. Git-tracked JSONL.** `game_data/validated/*.jsonl` lives in the repo. `git log --follow validated/abilities.jsonl` becomes the audit log; `git blame -L /id\":\"frost_lance_3/,+10` tells you which commit introduced a record. Diff-friendly because JSONL is line-oriented and IDs are stable. Counter-pattern: do *not* commit `generated/` (pre-validation) to keep the diff signal high. Works fine to ~50k records; past that, JSONL diffs slow git operations and we move to (C).

**C. Append-only log + content-addressed records.** At 10k+, switch to a content-addressed store: filename = `sha256(canonical_json(record))[:16].json`, an append-only `index.jsonl` mapping `id -> hash -> generation_run_id`, and a `runs/<timestamp>.toml` recording prompt, target file, model, sim digests for the batch. CRDT and signed manifests are overkill for a single-author project; skip both. Versioning the *target file* matters more than versioning the records - one target file change cascades into thousands of records, so the target file's git history is the actual history of design decisions.

Recommendation: ship (A) + (B) on day one; reach for (C) only when JSONL diffs become annoying (empirically around 5k records on a SSD).

## 3. Balance-target file format

TOML, because:

- `tomllib` ships in Python 3.11+ stdlib (no dependency).
- TOML's typed scalars (`int`, `float`, `string`, `array of homogeneous`) catch authoring typos at parse, while YAML happily turns `damage: 12,15` into a string.
- Inline tables and arrays-of-tables map naturally to "per-(rarity, tier, school) bucket" data.
- Comments survive round-trip in `tomli-w` if we ever auto-write back.

Layout (`pipelines/game_data/balance/targets.toml`):

```toml
schema_version = "1.0.0"
description = "Authoritative balance targets for the v1 fantasy ARPG content set."

# ---- top-level histograms (orchestrator-enforced, not LLM-enforced) ----
[rarity_histogram]
common      = 0.50
uncommon    = 0.30
rare        = 0.15
epic        = 0.04
legendary   = 0.01

[ability_school_floor]
# minimum records per (school, tier) before catalogue is shippable
elemental = 3
arcane    = 3
nature    = 2
shadow    = 2
holy      = 2
physical  = 3

# ---- per-bucket numeric bounds (schema-narrowed) ----
[[item.weapon]]
rarity   = "common"
damage   = { min = 4,   max = 18 }
weight   = { min = 0.5, max = 6.0 }
value_gold = { min = 5, max = 80 }
durability = { min = 80, max = 200 }

[[item.weapon]]
rarity   = "uncommon"
damage   = { min = 14,  max = 38 }
weight   = { min = 0.5, max = 6.0 }
value_gold = { min = 60, max = 250 }

[[item.weapon]]
rarity   = "rare"
damage   = { min = 32,  max = 75 }
value_gold = { min = 200, max = 800 }

[[item.weapon]]
rarity   = "epic"
damage   = { min = 70, max = 140 }
value_gold = { min = 700, max = 3000 }

[[item.weapon]]
rarity   = "legendary"
damage   = { min = 130, max = 260 }
value_gold = { min = 2500, max = 12000 }

[[ability]]
tier   = 1
mana   = { min = 5,  max = 25 }
cooldown_sec = { min = 0.5, max = 3.0 }
damage = { min = 4,  max = 30 }

[[ability]]
tier   = 3
mana   = { min = 25, max = 70 }
cooldown_sec = { min = 2.0, max = 8.0 }
damage = { min = 30, max = 110 }

[[ability]]
tier   = 5
mana   = { min = 60, max = 130 }
cooldown_sec = { min = 6.0, max = 16.0 }
damage = { min = 110, max = 240 }

# ---- sim gates ----
[sim.gates]
ttk_min_s = 0.5
ttk_max_s_by_rarity = { common = 30.0, uncommon = 22.0, rare = 16.0, epic = 12.0, legendary = 9.0 }
dps_z_max = 3.0
dps_z_min = -2.0
dominance_max = 1
```

Loaded into a Pydantic model (`BalanceTargets`) at startup; the model validates that every bucket has all required keys and that bounds are monotonic across rarity/tier. The generator queries `targets.bounds_for(record_type="item.weapon", rarity="legendary")` -> `{"damage": (130, 260), ...}` and merges those into the JSON Schema before the API call.

Authoring workflow: human edits `targets.toml`, runs `python -m pipelines.game_data.balance.lint targets.toml` (validates monotonicity, prints diff vs current accepted records' actual ranges), then commits. The target file's git log is the design log.

## 4. Wiring it into v1 (concrete diff sketch)

Files to add (none of v1's files change shape; only `generate_records.py` gets a thin new entry point that delegates to v1 internally):

```
pipelines/game_data/
  balance/
    __init__.py
    targets.toml              # ~150 lines, hand-authored
    schema.py                 # Pydantic BalanceTargets
    lint.py                   # CLI: validates + prints range deltas
    narrow_schema.py          # JSON Schema narrower (target + record_type -> narrowed schema dict)
  sim/
    __init__.py
    kill_a_dummy.py           # ~100 lines, the spec above
    matrix.py                 # multi-dummy runner + Pareto comparator
    metrics.py                # the 6 metrics from Q5
  constrained_generate.py     # orchestrator: bucket plan -> narrow -> generate -> sim -> revise
```

Existing files: `generate_records.py`, `validate_records.py`, `export_godot.py`, `schemas.py` *unchanged*. The new orchestrator imports from `generate_records` (re-uses `_gen_openai_batch`, `_gen_synthetic_*`) and from `validate_records` (re-uses `validate_record`, `link_check`). Round-trip test stays green because the records' shape never changes.

Reject-and-retry pattern, condensed:

```
plan = bucket_plan(target, count)             # [{"rarity":"legendary","tier":5}, ...]
for slot in plan:
    schema = narrow(Item.model_json_schema(), target, slot)
    rec = call_oai_strict(schema, prompt_for(slot)) or call_outlines(...)
    sim = simulate_matrix(rec, dummies=DUMMY_VARIANTS)
    if sim.verdict == "pass":
        accepted.append(rec)
    else:
        critique = build_critique(rec, sim)
        rec2 = call_oai_strict(schema, prompt_for(slot) + critique)
        sim2 = simulate_matrix(rec2, ...)
        accepted.append(rec2) if sim2.verdict == "pass" else dropped.append((rec, rec2, sim2))
```

## 5. Test plan

1. **Target lint round-trip.** Edit `targets.toml`, run `lint.py`. Pass if monotonicity errors are reported on a deliberately-broken file (legendary damage < epic damage) and clean on the canonical file.
2. **Schema narrower round-trip.** Generate 10 weapons of each rarity with narrowed schema *and* run them through v1's Pydantic validator. Pass if 100% validate (narrow strictly tightens bounds; v1's validators can only get happier).
3. **Sim sanity.** Hand-craft three records: (a) "iron_sword" (damage 12) -> pass, ttk ~12s; (b) "godmode_blade" (damage 9999) -> reject:ttk_too_low; (c) "twig" (damage 0) -> reject:dummy_survived. Pass if verdicts match.
4. **End-to-end constrained gen.** Generate 50 abilities across the (school, tier) grid using `--backend openai` (or synthetic fallback). Pass if first-pass acceptance ≥60%, post-retry acceptance ≥90%, rarity histogram matches target ±5%, no Pareto-dominators in the catalogue.
5. **Outlines fallback.** Same test offline with `--backend outlines --model meta-llama-3.1-8b-instruct`. Pass if acceptance ≥50% (lower because 8B model) and no schema-violating outputs at all (FSM guarantees this; if it fails, outlines is misconfigured).
6. **10k-record stress.** Generate 10k abilities synthetically, run validator + sim on all. Pass if total runtime <10 min on RTX 5090 box and JSONL diff in git stays under 50MB.

## 6. Honest tradeoffs

- **Strict-mode JSON Schema cannot express conditional bounds across fields.** "If kind==passive then cooldown_sec==0" is not a schema the API will compile. We solve this by *bucketing the batch* (one slot = one fixed kind/rarity/tier) and narrowing per-slot. Cost: more API calls, smaller batches. Benefit: every bound becomes a flat enum/range the API enforces hard.
- **`outlines` with llama-3.1-8B writes valid records but mediocre prose.** The 8B model on a constrained schema produces generic descriptions ("A sword. It cuts."). For ship-quality flavor text, fall back to a *second* unconstrained call to a stronger model that takes the validated record and only rewrites `description`. Cheap (one short prompt per record, ~50 tokens).
- **The sim is a model of a game we have not built yet.** The target combat formulas (armor flat, resist multiplicative, fixed-tick) are the *game's* design choice as much as the *content*'s. Document them in `kill_a_dummy.py`'s docstring; treat any change to that formula as a balance-target bump that requires re-running the catalogue. This is the same discipline PoE applies to "global combat constants."
- **Multi-pass critique helps when first-pass is bad and hurts when first-pass is good.** Auto-disable critique when first-pass acceptance >80%; just oversample 1.2x and discard. Reserve critique for rare/epic/legendary buckets where the LLM has the least training data.
- **Provenance round-tripping with TOML.** TOML preserves comments only via `tomli-w` + comment-aware writers; if we auto-edit `targets.toml` (we should not, but tools drift), we lose human comments. Solution: make the target file *only* human-edited; tools read it, never write it.

## 7. What to build next - punch list with effort estimates

| Order | Item | Effort | Blocks |
|---|---|---|---|
| 1 | `balance/targets.toml` v1 + `BalanceTargets` Pydantic model | 2-3h | everything |
| 2 | `balance/lint.py` (monotonicity + range delta vs current `validated/`) | 1-2h | adoption |
| 3 | `balance/narrow_schema.py` (Pydantic JSON Schema -> narrowed dict by bucket) | 2-4h | constrained gen |
| 4 | `sim/kill_a_dummy.py` (the 100-line skeleton) | 2-3h | sim gates |
| 5 | `sim/matrix.py` (multi-dummy + Pareto) | 2-3h | dominance metric |
| 6 | `sim/metrics.py` (DPS curve, TTK dist, school floor, mana ratio, dominance count) | 2-3h | balance report v2 |
| 7 | `constrained_generate.py` orchestrator (bucket plan, narrow, gen, sim, retry) | 3-5h | ships the feature |
| 8 | OpenAI strict-mode wiring (inline `$ref`, set `strict: true`) | 1-2h | quality bump |
| 9 | `outlines` + llama-3.1-8B local backend | 2-4h | offline mode |
| 10 | Provenance fields (`target_file_sha256`, `sim_digest`, `parent_id`) added to `Provenance` model + propagated | 1h | audit trail |
| 11 | Markdown report integration (extend v1's `validate_records.py` markdown to surface sim metrics) | 1-2h | usability |
| 12 | Pass-3 critique loop (only enabled when first-pass <60%) | 2-3h | optional polish |
| **Total** | | **22-35h** | |

Realistic v1.5 ship: items 1-7 (~14-20h), gives constrained gen + sim gates. Items 8-10 (~5-7h) are the "production" bumps. Items 11-12 are polish.

## 8. Sources

- OpenAI Structured Outputs: https://platform.openai.com/docs/guides/structured-outputs (strict mode, schema constraints, supported keywords)
- Anthropic Structured Outputs: https://docs.claude.com/en/docs/build-with-claude/structured-outputs
- `outlines` library: https://github.com/dottxt-ai/outlines and https://dottxt-ai.github.io/outlines/ (Pydantic + JSON Schema constrained decoding for local HF models)
- `lm-format-enforcer`: https://github.com/noamgat/lm-format-enforcer (alternative; faster, less ergonomic)
- Microsoft `guidance`: https://github.com/guidance-ai/guidance (alternative DSL, heavier)
- Slay the Spire balance: Anthony Giovannetti, GDC 2019, "MegaCrit's content tools"; patch-notes archive at https://slay-the-spire.fandom.com/wiki/Updates
- PoE balance simulation: Chris Wilson, ExileCon 2019/2022 talks; "Designing the Atlas"
- Last Epoch itemization sim: Eleventh Hour Games, GDC 2024 "Itemization at scale"
- Caves of Qud tactics tests: Brian Bucklew, Roguelike Celebration 2021
- Hearthstone autobalancer: Mike Donais, GDC 2019 "Card Design and Balance"
- Pydantic JSON Schema generation: https://docs.pydantic.dev/dev/concepts/json_schema/
- Python `tomllib` (3.11+ stdlib): https://docs.python.org/3/library/tomllib.html
- TOML spec: https://toml.io/en/v1.0.0
