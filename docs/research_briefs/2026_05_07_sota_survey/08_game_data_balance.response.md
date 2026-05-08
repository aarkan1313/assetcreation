# Research Response — Game Data / Balance Pipeline (2026 SOTA)

**Date:** 2026-05-07
**Hardware target:** RTX 5090 Laptop, 24 GB VRAM, sm_120, CUDA 12.8+, Windows 11
**Source brief:** `08_game_data_balance.md`

---

## TL;DR — what to actually do

1. **Record generation backend:** swap the bulk path from synthetic to **DeepSeek V4-Pro** (~$0.18–$0.51 per 1K records, 30–100× cheaper than Opus) for items/abilities/NPCs; reserve **Claude Opus 4.7** for the ~10% of records that carry creative weight (lore_terms, key NPC voice, faction ideology). GPT-5.5 is the safer single-vendor bet. The Anthropic + OpenAI cloud routes you already plumbed are correct — just *run* them.
2. **Constrained decoding:** when vLLM ships compatibility, upgrade local stack to **XGrammar-2** (released 2026-05-04, 10–80× faster compile, "Structural Tag" abstraction). For cloud paths, use OpenAI's `response_format: {type: "json_schema"}` and Anthropic tool-use schemas — both now offer 100% schema adherence and remove the validate-and-retry loop.
3. **Few-shot expansion:** wire **DSPy + GEPA** (ICLR 2026 Oral) into `generate_records.py` for items/abilities, where you can write a numeric quality metric (schema valid + Pareto-non-dominated + embedding distance from existing records). Skip GEPA for lore where the metric is fuzzy — hand-curated examples win there.
4. **Balance analysis:** keep the DuckDB reports as the backbone. Add **one** thing: a `pareto_dominated_records.py` utility on top of **pymoo** (NSGA-II non-dominated sorting). One day of work, surfaces "this ability is strictly worse than that one" in seconds. RuleSmith / RL self-play / Machinations.io are wrong-shaped or premature for &lt;1000 static records.
5. **Combat sim:** keep `kill_dummy_sim.py`. Do **not** set up RL agents now — combat isn't built. When it is, add **scripted-heuristic Monte Carlo in PettingZoo** (no training, just AEC scaffolding) for a standard interface, and a one-afternoon **LLM-as-tester** pass (Claude Sonnet finds degenerate ability combos, ~$5 per run).
6. **Dialogue:** Yarn is fine if it's working — migration to Ink or Dialogic 2 is lateral. The real wins are universal: a ~100-line static analyzer on the compiled Yarn graph for unreachable nodes + dead ends, and a Claude-based authoring lint pass. **Do not adopt Inworld/Convai** — those are runtime NPC products, not authoring tools.
7. **Lore:** start with `source/lore/*.md` + Obsidian + Smart Connections (BYO API key). Do **not** buy World Anvil / LegendKeeper / Kanka — they are worldbuilding-as-product; you need lore-as-data, in git, alongside the records that reference it. Defer Neo4j / Graphiti until ~500 entries.
8. **Localization:** Godot's gettext (.po) pipeline is the right baseline. **Crowdin Free** + DeepL (UI) / Claude Haiku (dialogue) for ML pre-translate (~$50–$200 total compute for 50K words across 12 languages), native-speaker MTPE on the top 4–6 languages (~$1.5–2.5K per language), community translation for the rest. Pseudo-localization on day one (`TranslationServer.set_pseudolocalization_enabled(true)`).
9. **Schema migration:** keep your Alembic-style `migrations/`. Add a CI compatibility check using `getsentry/json-schema-diff` (BACKWARD/FORWARD/BREAKING gate). Adopt Confluent's compatibility vocabulary in migration filenames. Re-evaluate when the JSON Schema GSoC 2026 SchemaShift CLI ships (late 2026).
10. **Cross-ref at scale:** custom linker is fine through ~20K records *if* lookups go through pre-built `dict[id → record]` maps (audit this — it's the only scaling cliff). Add `fastjsonschema` or `okjson` (50–100× faster than stock `jsonschema`). Add a hash-based incremental linker (~50 LOC) before considering DuckPGQ. Re-evaluate at 50K records.

The single highest-leverage move: **run the cloud LLM cascade you've already plumbed**, on real DeepSeek + Claude keys, with GEPA-optimized prompts and DuckDB Pareto reports gating which generated records make it into `validated/`. The infrastructure is best-in-project; only synthetic has been used. Switching that flag is the unlock.

---

## Q1 — 2026 SOTA for game-data record generation

### 1. Best LLMs for game content (May 2026)

The frontier split into "expensive but creative" and "cheap and reliable for schema-following." For game records both axes matter.

| Model | Price (in/out, $/Mtok) | Strength for game data |
|---|---|---|
| **Claude Opus 4.7** (Apr 2026) | $5 / $25 | Best prose rhythm, subtext, tone consistency. Use for lore, key NPC voice, faction ideology. |
| **GPT-5.5** (Apr 2026) | $2.50 / $15 | Most disciplined at maintaining narrative consistency across a 50-record batch. Native JSON-Schema structured outputs (100% adherence). |
| **DeepSeek V4-Pro** (1.6T MoE, MIT, Apr 2026) | $0.07 / $0.11–$0.44 | **Value king.** Within 0.2 pt of Claude on SWE-bench Verified. JSON output supported in all modes. ~30–100× cheaper than Opus. |
| **Claude Haiku 4.5** | $1 / $5 | Sweet spot for high-volume mechanical records. |
| **Gemini 3.1 Pro / Flash-Lite** | $1.25 / Pro; $0.10 / $0.40 Flash-Lite | "Less literary; better for informational." Fine for items/abilities, weak for lore. |
| **Llama 4 Scout** (10M context) | open weights | Useful only if feeding an enormous worldbuilding bible per call. |
| **Kimi K2.5 / Qwen 3.5 / Nemotron Ultra** | open weights | Top of IFEval (94.0/92.6/89.5). Strongest local-only schema-following options. |

**Concrete recommendation for this pipeline:**
- Bulk mechanical records (items, abilities, stats): **DeepSeek V4-Pro** via `generate_records.py`'s OpenAI-compatible endpoint. Already 90% plumbed since the cascade exists.
- ~10% creative weight (lore_terms, key NPCs like Caedis Halloran / Mara Vex, faction ideology): **Claude Opus 4.7** via the existing Anthropic route.
- Local vLLM remains useful only if you're already paying GPU cost or have privacy needs. At $0.14/Mtok DeepSeek input the math against an RTX-class machine is rough.

### 2. Constraint techniques newer than xgrammar

The big news: **XGrammar-2 dropped 2026-05-04**, three days before this brief.

- 10–80× compilation speedup over v1 (cross-grammar caching, repetition-state compression, batching/speculative decoding support).
- New "**Structural Tag**" abstraction — composable JSON protocol covering OpenAI harmony format, tool calling, reasoning channels, and custom output structures.
- Already integrated into vLLM, SGLang, TensorRT-LLM, MLC-LLM, with strict-mode tool calling for DeepSeek V4 and Qwen 3.6.
- ([XGrammar-2 announce](https://blog.mlc.ai/2026/05/04/xgrammar-2-fast-customizable-structured-generation), [GitHub](https://github.com/mlc-ai/xgrammar))

**Nothing displaced XGrammar — XGrammar displaced itself with v2.** Competing landscape:
- **llguidance** (Microsoft) — fastest TTFT, but more compile failures on complex schemas.
- **Outlines** — FSM-based; flattens recursive schemas, *unsuitable* for nested ability-effect trees. Not an upgrade path.
- **LM Format Enforcer** — character-level constraints, niche.
- **OpenAI Structured Outputs / Anthropic tool-use schemas / Gemini response_schema** — all three cloud APIs now offer 100% schema-adherence guarantees. For cloud paths these eliminated the need for client-side validate-and-retry loops.

**Action:** when vLLM ships XGrammar-2 compatibility, upgrade `local_llm_backend.py`. Free 10–80× speedup on the constrained stage with no schema rewrites. For cloud routes, swap `constrained_generate.py`'s post-hoc validation to provider-native structured outputs.

### 3. Few-shot expansion: "5 examples → 50 in style"

The genuine 2026 advance is **DSPy + GEPA**:

1. **GEPA** ("Reflective Prompt Evolution Can Outperform Reinforcement Learning," Agrawal et al., arXiv 2507.19457, **ICLR 2026 Oral**). +13% over MIPROv2, +20% over GRPO with **35× fewer rollouts**. 67% → 93% on MATH. Available as `dspy.GEPA` and standalone `pip install gepa`. ([GitHub](https://github.com/gepa-ai/gepa))
2. **MIPROv2** — earlier Stanford optimizer, cheaper to run for simpler tasks.
3. **BootstrapFewShot / BootstrapRS** — DSPy's classic teacher-LM-validates-with-metric loop.

**No game-content-specific DSPy module exists.** Path is generic: `dspy.Signature` matching your record schema → 5 hand-authored examples → metric (JSON Schema valid AND embedding distance from existing records > threshold AND not Pareto-dominated by existing records of same type) → run BootstrapFewShot or GEPA.

**Honest scope:** GEPA shines for items/abilities where the metric is numeric. For lore/NPC voice, the metric is subjective and GEPA's gain shrinks — keep hand-curated few-shot prompts there.

### 4. Fine-tuned game-content models — honest read

**They do not really exist in production-useful form.** Hugging Face has `chendren/deepseek-dnd-lora` and `Leiyan525/dnd-model-lora-en`, both hobbyist 7B LoRAs with unverified data quality. No reputable lab-published game-content fine-tune. Image side is full of LoRAs (FLUX Dungeons-and-Diffusion etc.) but those are art models.

**Why empty:** SOTA general-purpose models write D&D-style content well enough out of the box. The economic case for a custom LoRA flipped further when DeepSeek V4 dropped to $0.14/Mtok input.

**Skip.** If you want stylistic specialization, do it with few-shot + DSPy GEPA, not a custom fine-tune.

### Cost — per 1K records

Assuming ~500 input tokens (prompt + few-shot) + ~400 output tokens per record:

| Backend | $ per 1K records |
|---|---|
| GPT-5.5 standard | $7.25 |
| GPT-5.5 Pro | $87.00 |
| Claude Opus 4.7 | $12.50 |
| Claude Sonnet | $7.50 |
| Claude Haiku | $0.625 |
| **DeepSeek V4-Pro** | **$0.18–$0.51** |
| Gemini 3.1 Pro | ~$3.625 |
| Gemini 3.1 Flash-Lite | $0.21 |

Generating 10K records on DeepSeek V4: ~$2–$5. Same on Opus: ~$125. The gap widened over the past six months.

### Honest comparison

The existing **OpenAI → Anthropic → synthetic → vLLM** cascade in `generate_records.py` is the right architecture for May 2026. You don't need a new backend; you need to **route DeepSeek into the cascade as the bulk option** (it's OpenAI-API-compatible, plug into the existing `openai_client` path with a base_url override) and finally **run** the cloud routes that have only ever been dry-runned. The two factions both being "verdant + balance" and the "fireball_cast" SFX appearing on every ability are *synthetic-only* artifacts — running real LLM passes will eliminate both immediately.

**Sources:**
- [Best AI Models May 2026 Leaderboard](https://www.buildfastwithai.com/blogs/best-ai-models-may-2026-leaderboard)
- [DeepSeek V4-Pro vs Claude Opus 4.7 (DataCamp)](https://www.datacamp.com/blog/deepseek-v4-vs-claude-opus-4-7)
- [DeepSeek V4-Pro on HF](https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro)
- [LLM API pricing May 2026 (costgoat)](https://costgoat.com/compare/llm-api)
- [XGrammar-2 announcement](https://blog.mlc.ai/2026/05/04/xgrammar-2-fast-customizable-structured-generation)
- [vLLM Structured Outputs](https://docs.vllm.ai/en/latest/features/structured_outputs/)
- [OpenAI Structured Outputs](https://openai.com/index/introducing-structured-outputs-in-the-api/)
- [DSPy Optimizers](https://dspy.ai/learn/optimization/optimizers/)
- [GEPA paper (ICLR 2026 Oral)](https://arxiv.org/abs/2507.19457)
- [GEPA repo](https://github.com/gepa-ai/gepa)

---

## Q2 — ML-driven game balance analysis

### Honest framing

For &lt;1000 static records, this is **still overwhelmingly a manual designer + spreadsheet/SQL job in May 2026**. The ML balance literature has grown; the deployable tooling has not caught up. Two genuine 2026 papers:

1. **RuleSmith** (arXiv 2602.06232, Feb 2026) — multi-agent LLM self-play + Bayesian optimization over a tunable rule space. Reduced inter-faction win-rate gap to 0% on "CivMini." **Requires an executable rule engine** to run thousands of self-play games against. Doesn't apply to a static record set without a sim.
2. **"Simulation-Driven Balancing of Competitive Game Levels with RL"** (arXiv 2503.18748) — PCG + balancing agent + reward modeling. Targets level/map balance, not ability/item balance.

Neither is a "point at your `validated/abilities.jsonl` and get a balance report" product. For data-only balance, the actual 2026 path is still: descriptive stats → outlier detection → designer review.

### Recommendations

1. **Keep DuckDB + custom SQL as the backbone.** `duckdb_reports.py` already covers per-rarity item value/damage stats, per-school ability cost/effect, faction-ability crosstabs. Bottleneck is human interpretation, not compute.
2. **Add a pymoo NSGA-II Pareto-dominance utility.** Single concrete win, ~1 day of work.
   - Dump abilities to a numeric matrix (damage, cost, cooldown, radius, duration, utility-score).
   - `pymoo.util.nds.non_dominated_sorting.NonDominatedSorting`.
   - Surface the dominated abilities to the designer with their dominators.
   - Generalizes to N objectives without case-by-case SQL.
   - ([pymoo](https://github.com/anyoptimization/pymoo), [NSGA-II](https://pymoo.org/algorithms/moo/nsga2.html))
3. **Skip the rest.** RuleSmith / RL self-play need a runnable combat sim; you're not there. **Machinations.io** is genuinely strong for *economy/feedback-loop* balance (Wooga uses it for June's Journey) but a poor fit for static record sets and indie pricing is opaque ([machinations.io/balance](https://machinations.io/balance), [Wooga case study](https://machinations.io/articles/how-wooga-uses-machinations-to-balance-junes-journeys-game-economy)).

### Maturity / cost / license

- pymoo: Apache 2.0, Michigan State (Julian Blank), production-grade since 2020.
- DuckDB: MIT, ~no maintenance burden.
- RuleSmith / academic balance papers: research code only, no shipped library.
- Machinations.io: commercial SaaS, indie-to-AAA tiers (custom-quoted, not cheap).

### Honest comparison

**Nothing in 2026 beats DuckDB + designer-reviewed SQL outputs at &lt;1000 records.** The pymoo Pareto utility is a genuine free win and slots in alongside `duckdb_reports.py` cleanly — call it `pareto_dominated_records.py`, write to `reports/balance_pareto_*.md`, mirror the existing balance report cadence. RuleSmith and friends become relevant *after* the combat sim exists and after the record corpus is large enough that designers can't eyeball the outliers.

**Sources:**
- [RuleSmith (arXiv 2602.06232)](https://arxiv.org/abs/2602.06232)
- [Simulation-Driven Balancing with RL](https://arxiv.org/html/2503.18748v1)
- [Toward Automated Game Balance — IEEE](https://ieeexplore.ieee.org/document/9619032/)
- [pymoo](https://github.com/anyoptimization/pymoo)
- [Machinations.io Balance](https://machinations.io/balance)
- [Omnic — ML and Game Balance](https://blog.omnic.ai/posts/Machine-Learning-and-Game-Balance/)

---

## Q3 — Agent-based combat simulation

### Landscape, May 2026

**Tier 1 — RL research frameworks (training agents, reading off balance):**
- **PettingZoo** (Farama, MIT) — multi-agent Gym successor. v1.24+ in 2026. AEC + parallel APIs. ([github.com/Farama-Foundation/PettingZoo](https://github.com/Farama-Foundation/PettingZoo))
- **OpenSpiel** (DeepMind, Apache 2.0) — n-player zero-sum / co-op / general-sum, tightly coupled with CFR/MCTS. Bridged via Shimmy.
- **Stable-Baselines3** (DLR, MIT) — PPO/SAC/etc. v2.9.x in 2026.
- **Unity ML-Agents** v3.x/v4.x — canonical "make N agents try abilities and find dominant ones" workflow, but heavy.
- **Godot RL Agents** (edbeeching, Apache 2.0) — bridges to SB3/RLlib/CleanRL. Tutorials are toy nav/jump; combat balance is not a documented use case.

**Tier 2 — Academic 2025 balance research:**
- "Simulation-Driven Balancing of Competitive Game Levels with RL" (arXiv 2503.18748) — level/map balance, not ability/item.
- "Level the Level" (arXiv 2503.24099) — asymmetric handicap balancing.

**Tier 3 — LLM-driven (the new thing):**
- **RuleSmith** (covered in Q2) — most directly relevant 2026 paper, but research artifact.
- **"LLMs May Not Be Human-Level Players, But They Can Be Testers"** (arXiv 2410.02829) — argues LLM agents are useful for *measuring difficulty*, not for winning. **Closer to what you'd actually want.**
- **D&D Agents** (NeurIPS 2025) — LLM DMs/players/monsters running canonical D&D combat scenarios. Claude 3.5 Haiku beat GPT-4 and DeepSeek-V3. Useful precedent that LLMs can play tactical combat coherently.
- **RPGBench** (arXiv 2502.00595) — LLM-as-RPG-engine; finding: engaging stories yes, consistent verifiable mechanics often no.

**Tier 4 — Production / indie:**
- **Machinations.io** — Bayesian-optimization AI module, custom quotes. Best for economies, not ability sets.
- **BalanceGraph** (Unity Asset Store, Apr 2026) — node-based Monte Carlo balance simulator inside the Unity Editor. New, single-author tool; capacity at 60+ entities not benchmarked. ([forum thread](https://discussions.unity.com/t/tool-balancegraph-node-based-game-balance-simulator-unity-editor-extension/1715682))

### Recommendations

1. **Stick with `kill_dummy_sim.py` + Monte Carlo.** Combat doesn't exist yet. RL is a search algorithm over a *fixed* environment; if you set it up now you'll burn weeks tuning rewards against placeholder mechanics, then re-train every time the rules change. Threshold rule-of-thumb: RL pays off above ~10⁶ combinatorial states *with non-trivial sequencing*. ~30 abilities × ~30 items is well below that.
2. **When the dummy sim plateaus, graduate to scripted-heuristic self-play in PettingZoo.** No RL training, just AEC scaffolding around your existing simulator. You get standard tooling and trivially diff results across builds. Free, MIT, no GPU needed.
3. **One-afternoon LLM-as-tester pass.** When combat is partially built, give Claude Sonnet the ability list + the rules and ask for degenerate combos. Cost: ~$5 per run. Expected value: per the D&D Agents and arXiv 2410.02829 results, this outperforms any RL setup at this scale.
4. **Skip Unity ML-Agents, Godot RL Agents, BalanceGraph for now.** The Unity tools require Unity. BalanceGraph is single-author, untested at scale. Godot RL Agents is alpha-grade for this specific use case.

### Honest comparison

The dummy simulator + Monte Carlo at this scale **is** SOTA-equivalent in terms of catching balance issues per dev hour spent. Indie postmortems consistently report that Monte Carlo + spreadsheets caught 90% of issues; the remaining 10% needed playtesters, not RL. RuleSmith / PCG-RL papers all use multi-agent self-play *because the rules are already known and stable* — they're validation tools for shipped systems, not exploration tools for unbuilt ones.

**Sources:**
- [PettingZoo](https://github.com/Farama-Foundation/PettingZoo)
- [OpenSpiel via Shimmy](https://shimmy.farama.org/environments/open_spiel/)
- [Stable-Baselines3](https://stable-baselines3.readthedocs.io/)
- [Unity ML-Agents](https://unity-technologies.github.io/ml-agents/)
- [Godot RL Agents](https://github.com/edbeeching/godot_rl_agents)
- [Simulation-Driven Balancing with RL (arXiv 2503.18748)](https://arxiv.org/abs/2503.18748)
- [Level the Level (arXiv 2503.24099)](https://arxiv.org/html/2503.24099v1)
- [LLMs as Game Difficulty Testers (arXiv 2410.02829)](https://arxiv.org/html/2410.02829v1)
- [RPGBench (arXiv 2502.00595)](https://arxiv.org/abs/2502.00595)
- [D&D Agents NeurIPS 2025 roundup](https://www.ttrpginsider.news/p/news-roundup-ai-researchers-test-its-ability-to-experience-d-d-combat)
- [Machinations.io](https://machinations.io/)
- [BalanceGraph (Unity)](https://discussions.unity.com/t/tool-balancegraph-node-based-game-balance-simulator-unity-editor-extension/1715682)

---

## Q4 — Dialogue tooling beyond Yarn

### Landscape, May 2026

| Tool | License | Engines | Notes |
|---|---|---|---|
| **Yarn Spinner** | MIT | Unity (mature), Godot (alpha, C# bindings), Unreal (in dev) | v3.1 shipped Dec 2025; new ReactFlow VS Code editor; parameter-level validation; Visual Novel Kit incoming as paid add-on. |
| **Ink (inkle)** | MIT | Unity (official), Unreal, Godot (GodotInk needs .NET; pure-GDScript inkgd ~50× slower) | Stable, very mature. Inky editor is the most polished writer-facing tool in this list. 80 Days, Sable, Vampire Bloodlines 2. |
| **Twine** | open | Web/HTML | IF/prototyping. |
| **Articy:Draft X** | Free ≤700 objects, then €6.99+/mo | Unity, Unreal | AAA standard (Disco Elysium, Hogwarts Legacy, Talos 2). Mature flow editor + orphan detection. |
| **Arcweave** | Free non-commercial; $15–30/mo/seat commercial | engine plugins, JSON | Real-time multiplayer; Star Trucker, Galacticare. |
| **Dialogic 2** | MIT | **Godot only** (4.3+) | Visual timeline editor in-engine. **Most Godot-native dialogue tool.** ([github](https://github.com/dialogic-godot/dialogic)) |
| **StoryFlow Editor** | $30 one-time | Unity, Unreal, **Godot** | Indie-priced articy alternative. |
| **Mountea Dialogue System** | Free, open | Unreal | Ships its own validation system. |
| **NarrativeFlow** | Paid | multi-engine (GDScript, C#, etc.) | Markets real-time error/logic checking. |

**Structure validation:** Yarn 2026 added parameter-level validation on commands/functions. Compiler catches missing-node refs. Unreachable-node detection is *not* documented. Articy and Mountea ship orphan detection. **No widely-adopted tool ships a true graph-coverage analyzer** with "% of nodes reachable from start under all variable assignments" — it's a custom-script problem regardless of authoring tool.

**Branching coverage:** **Yarn Spinner Story Solver** (web tool, in dev for 2026) — closest first-party Yarn product but not yet a coverage analyzer in the formal sense. ([Yarn 2026 roadmap](https://yarnspinner.dev/blog/yarn-spinner-in-2026))

**LLM-assisted authoring** — critical distinction: most "AI dialogue" products are **runtime NPC AI**, not authoring tools.
- **Inworld AI** — pivoted to general-purpose realtime voice/AI infra in 2025. Not authoring.
- **Convai** — NVIDIA partnership, runtime NPC behavior + voice. Not authoring.
- **Charisma.ai** — uniquely combines a story editor + AI conversation engine; closest to authoring.
- **Custom Claude/GPT writers'-room assistants** — feed the existing Yarn corpus, ask for branch suggestions, validation passes, missing-state detection. Cheap, flexible, no lock-in. **The genuine 2026 best practice for indies.**

### Recommendations

1. **If Yarn is wired up and working — keep it.** Migration to Ink or Dialogic 2 is lateral, not a clear win. Yarn's Godot story is alpha but improving; the gap to Ink (writer-comfort) and Dialogic 2 (Godot-native UX) is small.
2. **If Yarn is *not* yet wired up to Godot in this project**, evaluate **Dialogic 2** (most Godot-native, MIT, free) or **Ink + GodotInk** (best writer experience, requires C#). Don't pick Yarn for a new Godot project in 2026 — wait for non-alpha Godot support.
3. **Build a ~100-line static analyzer** over your compiled Yarn graph (`.yarnc`) that flags unreachable nodes, dead-ends without explicit terminal markers, undefined variable references. Universal across tools, ~1 day of work, gives you what no tool ships.
4. **Add a runtime coverage hook** that logs visited node IDs to a file, diff against the static node set after playtests.
5. **Add a Claude-based authoring lint pass** as a CI step. ~1 day of work, more leverage than evaluating any AI-NPC product.
6. **Skip Inworld / Convai.** Wrong product category — they solve runtime NPC behavior, not authoring.

### Honest comparison

For an indie Godot project in May 2026, the tool choice (Yarn / Ink / Dialogic) is a **lateral move with migration cost**. The wins are universal: custom static analyzer, runtime coverage tracker, Claude-based lint. Yarn's `yarn_link.py` already validates `[[choice|target]]` and `<<jump target>>` references — extend it to the static-analyzer + coverage tracker; that's worth more than a tool swap.

**Sources:**
- [Yarn Spinner in 2026](https://yarnspinner.dev/blog/yarn-spinner-in-2026)
- [Yarn Monthly Update Jan '26](https://yarnspinner.dev/blog/monthly_jan_26/)
- [StoryFlow — Best Narrative Tools 2026](https://storyflow-editor.com/blog/best-narrative-design-tools-for-game-developers-2025/)
- [NarrativeFlow comparison](https://narrativeflow.dev/blog/twine-vs-yarn-spinner-vs-ink-vs-narrativeflow-which-branching-dialogue-tool-is-right-for-your-game/)
- [Dialogic 2](https://github.com/dialogic-godot/dialogic)
- [Mountea Dialogue System](https://github.com/Mountea-Framework/MounteaDialogueSystem)
- [Ink (inkle)](https://github.com/inkle/ink) / [Inky](https://github.com/inkle/inky)
- [GodotInk thread](https://forum.godotengine.org/t/godotink-an-integrated-narrative-scripting-language-for-godot/35531)
- [ConvAI alternatives 2026](https://www.gladecore.com/blog/the-4-best-convai-alternatives-for-ai-npcs)
- [Charisma.ai overview](https://skywork.ai/skypage/en/Charisma.ai-A-Deep-Dive-into-Crafting-Your-Storyimmersive-AI-Universe/1976816712164241408)

---

## Q5 — Lore database tools

### Landscape, May 2026

**Dedicated worldbuilding platforms:**
- **World Anvil** — wiki-article-centric, template-heavy, async collab. Manuscripts module cross-links scenes to canon. Strong for novelists/TTRPG; weakest at programmatic export.
- **LegendKeeper** — $9/mo or $90/yr, only owner pays, unlimited free guests. Real-time multiplayer, interactive maps. Polished but closed format.
- **Kanka** — open-source, real free tier, paid host. Public API + JSON export. **Most pipeline-friendly of the dedicated tools**; closest free OSS competitor to World Anvil.
- **Campfire Writing** — modular (17 modules), à la carte pricing. Better for prose authors than structured data.
- **Notion / Obsidian / Scrivener / Causality / LegendKeeper / Kanka / Fantasia Archive** — covered in source material; only Obsidian and Kanka have credible programmatic stories.

**LLM-augmented (what actually shipped):** Honest read — **no shipped, polished, off-the-shelf "RAG-over-your-lore-that-flags-contradictions" product targeted at game devs in May 2026.** World Anvil added AI assistant features but they help drafting, not validation. Patchview (arXiv 2408.04112) and Karpathy's "LLM Wiki" pattern (Apr 2026) are reference implementations, not products. **Contradiction Detection in RAG** (arXiv 2504.00180) shows the technique works when prompted — but no game-dev-targeted product wraps it.

**Programmatic alternatives:**
- **Obsidian + Smart Connections** ([github](https://github.com/brianpetro/obsidian-smart-connections)) — embedding-based semantic search over a vault, supports Claude/Gemini/GPT/Llama. Caveat: reads static `.md` content, not Dataview-generated.
- **Obsidian + Dataview** — SQL-ish queries over note frontmatter.
- **Neo4j** — NODES AI 2026 keynote ("Graph-Powered Storyworlds") shows the workflow. **neo4j-labs/llm-graph-builder** automates extraction. Free Community edition.
- **Graphiti** ([github](https://github.com/getzep/graphiti)) — temporal validity windows on facts ("X true in 1402, superseded in 1450"). Correct shape for evolving lore.
- **SQLite + sqlite-vec + FTS5** — boring, works, queries fast.

### Recommendations

1. **Start with `source/lore/*.md` + Obsidian + Smart Connections.** Pipeline already speaks Markdown + frontmatter. Stays git-versioned alongside the records that reference it. Smart Connections gives you "find lore semantically related to this new claim" for free (BYO API key) — 80% of contradiction-check value.
2. **Define YAML frontmatter schema:** `id`, `kind`, `era`, `aliases`, `contradicts`, `supersedes`, `localization_key`. Re-use the existing JSON Schema infrastructure to validate frontmatter.
3. **Migration path when you outgrow it (~500 entries):** add typed relations → run `llm-graph-builder` → Neo4j AuraDB Free → Cypher queries for `contradicts` edges. Or simpler: SQLite + sqlite-vec embeddings.
4. **Skip dedicated worldbuilding platforms.** World Anvil / LegendKeeper / Kanka / Campfire are *worldbuilding-as-product*; you need *lore-as-data*. They are the wrong category — even Kanka, the most pipeline-friendly, makes you live in their entity model.

### Honest comparison

For an indie Godot dev with `source/lore/` empty, **a dedicated tool is the wrong shape**. The product category is "non-technical writer collaboration on a public reader-facing wiki," which is not your problem. File-based + Obsidian dominates on every axis that matters for game-data integration: git-tracked, schema-validated, programmatically accessible, free, no lock-in. The 2026 LLM-canon dream (RAG over your lore that flags contradictions on every new claim) is buildable today in ~150 LOC on top of Smart Connections embeddings — write that script when you have ~50 entries.

**Sources:**
- [LegendKeeper alternatives](https://www.legendkeeper.com/best-world-anvil-alternatives/)
- [Kanka vs World Anvil 2026](https://kanka.io/kanka-vs-worldanvil)
- [World Anvil April 2026 updates](https://blog.worldanvil.com/newsletter/world-anvil-updates-april-2026/)
- [Best AI for Worldbuilding April 2026](https://www.jenova.ai/en/resources/best-ai-for-worldbuilding)
- [Patchview (arXiv 2408.04112)](https://arxiv.org/html/2408.04112v1)
- [Contradiction Detection in RAG (arXiv 2504.00180)](https://arxiv.org/abs/2504.00180)
- [LLM Wiki at Scale (Apr 2026)](https://michalnasternak.medium.com/the-llm-wiki-at-scale-from-personal-research-tool-to-production-rag-247710a1284c)
- [Obsidian Smart Connections](https://github.com/brianpetro/obsidian-smart-connections)
- [Neo4j NODES AI 2026 — Graph-Powered Storyworlds](https://neo4j.com/videos/nodes-ai-2026-graph-powered-storyworlds-using-neo4j-to-keep-1m-word-litrpg-epics-coherent-w-ai/)
- [Neo4j LLM Graph Builder](https://neo4j.com/labs/genai-ecosystem/llm-graph-builder/)
- [Graphiti](https://github.com/getzep/graphiti)

---

## Q6 — Localization & i18n

### Godot baseline

Godot 4 supports CSV, gettext (.po/.mo), and POT generation; XLIFF is not native. The 2026 indie consensus:
- **CSV** for very small projects (&lt;1K strings, 2–3 languages).
- **gettext (.po) for anything serious** — actual indie standard in 2026, plays well with every TMS, plays well with Weblate.
- Footgun: any string assembled at runtime, in resource files, or not wrapped in `tr()` is invisible to POT generation. Audit pass is non-negotiable.

### TMS options (May 2026 prices)

| Platform | Entry price | Free tier | Indie fit |
|---|---|---|---|
| **Crowdin** | $59/mo Pro (60K hosted words) | Free 60K words, 1 project, AI included | **Best indie fit.** Free for OSS. Direct .po + Godot integration. |
| **Weblate** (self-host) | Free or ~€19/mo Hosted | Self-host or libre on Hosted Weblate | Open-source. Godot itself is translated on Hosted Weblate (115 languages). |
| **Lokalise** | $120/mo Start | 14-day | Polished UX; cost scales fast. |
| **Phrase** | ~$375/mo | 14-day | Enterprise-leaning, overkill. |
| **OneSky** | $0 community / paid | Generous community plan | Decent, less mindshare in 2026. |
| **Smartling** | Quote-only | None | Enterprise. Skip. |

### ML-translation prices (May 2026)

- **DeepL API Pro:** ~$25 / Mchar (~167K words). 50K words ≈ ~$7. Best raw NMT for European pairs.
- **GPT-4o:** $2.50 in / $10 out per Mtok. ~$30–60 / Mchar end-to-end. Batch API 50% off.
- **Claude Haiku 4.5:** $1 in / $5 out. **Dialog-translation sweet spot in 2026** — handles tone/register/in-character voice better than DeepL for narrative. ~$10–20 / Mchar.
- **Claude Sonnet:** $3/$15. High-stakes story beats.

### Cost reality, 50K words, 12 languages

- Pure ML pre-translate raw cost: **&lt;$50 per language**. Do not ship unedited — 2026 sources unanimous that unedited MT gets review-bombed.
- MTPE (machine + native-speaker post-edit): **~$1.5K–$2.5K per language**.
- Cold human translation: ~$5K–$7.5K per language.

**For 12 languages:** pure ML pre-translate ~$600 total compute. MTPE on top 4–6 + ML-only on the rest gated by an "experimental translation" disclaimer ≈ **~$10K–$15K**. Full human MTPE on all 12 ≈ **~$25K–$35K**.

### Recommendations (minimum-viable indie stack)

1. **Godot's gettext .po pipeline as ground truth.** CSV only if you literally have &lt;500 strings.
2. **Crowdin Free** (or Weblate self-hosted if privacy-paranoid). Push `.pot`, pull `.po`.
3. **Pre-translate with Claude Haiku for dialogue + DeepL for UI/system strings.** Python script in your existing pipeline, you control the prompt and cost. Budget ~$50–$200 for 50K words across 12 languages.
4. **Native-speaker MTPE on top 3–5 launch languages** (EN→ES, FR, DE, JP, ZH-S). ~$1.5K–$2.5K each. Rest ship with disclaimer.
5. **Pseudo-localization built in from day one** — `TranslationServer.set_pseudolocalization_enabled(true)`. Catches 80% of layout bugs free.
6. **Pre-flight CI script** that reads `localization_key` fields from the validated records, diffs against `.pot`, fails CI on missing keys. **Highest-leverage thing to build now while `source/lore/` is empty.** Slot into `validate_records.py` or as a sibling script.

### Honest comparison

A full TMS subscription before you have content is not worth the price tag. The 2026 reality is: **Crowdin Free + DeepL/Claude API + git-tracked .po + native-speaker post-edit** holds through ship. Lokalise/Phrase/Smartling are upgrade paths if you grow into them, not starting points.

**Sources:**
- [Godot — Localization with gettext](https://docs.godotengine.org/en/stable/tutorials/i18n/localization_using_gettext.html)
- [DeepL — Indie Game Localization with Godot](https://developers.deepl.com/docs/learning-how-tos/cookbook/automating-indie-game-localization-with-the-deepl-api-and-godot)
- [Godot Engine on Hosted Weblate](https://hosted.weblate.org/projects/godot-engine/)
- [Crowdin pricing](https://crowdin.com/pricing) / [breakdown 2026](https://www.autolocalise.com/blog/crowdin-pricing-breakdown-alternatives)
- [Best Translation API 2026 — GPT vs Claude vs DeepL](https://intlpull.com/blog/ai-translation-api-comparison-2026)
- [Crowdin — Real cost of AI translations](https://crowdin.com/blog/ai-translation-cost)
- [Game Localization Costs 2026 (Transphere)](https://www.transphere.com/game-localization-costs/)
- [Top 10 Game Localization QA Checks 2026](https://etranslationservices.com/localization/top-10-game-localization-qa-checks-for-2026/)

---

## Q7 — Schema migration & record evolution

### Honest framing

The JSON Schema ecosystem in May 2026 still does **not** have a mature, production-grade equivalent of Alembic-for-JSON-files. Three signals to know:

1. **JSON Schema GSoC 2026** has accepted **JSON Schema Compatibility Checker** (issue #984) and **SchemaShift / Migration Assistant** (issues #969, #990). Deliverables target late 2026. They are the first official, sanctioned attempts at "Alembic for JSON Schema." Not shippable today.
2. **Existing diff tools** (`getsentry/json-schema-diff`, npm `json-schema-diff`) are explicitly WIP with incomplete keyword coverage. They tell you *what changed*, not how to migrate. Useful as a CI gate.
3. **The Confluent / Kafka school of schema evolution** is the dominant production pattern: BACKWARD / FORWARD / FULL compatibility levels, additive-only changes with defaults, version-tagged schemas, CI-enforced breakage checks. **This is what your `migrate_records.py` should encode.**

**Database-style tools (Atlas, Liquibase, Flyway, dbt)** are SQL-centric and don't migrate JSON file records.

**ML-assisted migration:**
- **MetaConfigurator** (arXiv 2508.05192) — open-source, oriented to authoring/mapping, not deterministic migration codegen.
- **Google's internal LLM migration tooling** (arXiv 2504.09691, FSE 2025) — 595 changes across 39 migrations, 74% LLM-generated, 50% time savings. Internal, not released, but proves the pattern works at scale.
- Practical pattern today: feed Claude/GPT both schemas + sample old record → ask for `migrate_v3_to_v4(record)` → unit-test against real records → commit. ~Same as what you'd do anyway, just faster.

**Game-engine-specific:**
- **Unity ScriptableObject:** still `[FormerlySerializedAs]` + `ISerializationCallbackReceiver` + custom `AssetPostprocessor`. Pro: **Odin Inspector / Validator** (~$80) has migration callbacks. AAA engines have not solved this either.
- **Unreal DataTable:** struct schema changes silently break row association. Mitigation: reimport from CSV + `UEditorValidatorBase` post-load checks.

### Recommendations

1. **Keep Alembic-style hand-written migrations.** At 14 → 500–2000 records, with 5 schemas, the overhead of any new framework dwarfs the work.
2. **Add a CI compatibility check** using `getsentry/json-schema-diff` or hyperjump tooling. Fail the build if a schema change is BREAKING without a numbered migration file. **Highest-ROI move today.**
3. **Adopt Confluent's compatibility vocabulary** in migration filenames/docstrings (e.g. `0003_ability_add_reagent_field.BACKWARD.py`). Forces explicit thinking and makes future tooling adoption trivial.
4. **Use Claude/GPT for migration drafts** — feed both schema versions + a sample record, get a first-draft `migrate(record)` function, human-review, commit.
5. **Re-evaluate in late 2026** when SchemaShift CLI lands. If it ships and is solid it could replace `migrate_records.py` directly. Until then it is vapor.

### Honest comparison

Existing setup wins. Atlas / Liquibase are wrong domain (SQL); SchemaShift is unfinished. The CI compatibility gate + Confluent vocabulary + LLM-drafted migrations is the meaningful upgrade and stays within the existing architecture.

**Sources:**
- [GSoC 2026: JSON Schema Compatibility Checker](https://github.com/json-schema-org/community/issues/984)
- [GSoC 2026: SchemaShift / Migration Assistant](https://github.com/json-schema-org/community/issues/990)
- [getsentry/json-schema-diff](https://github.com/getsentry/json-schema-diff)
- [Schema changes without breakage — 15 tools (Feb 2026)](https://medium.com/tech-with-abhishek/schema-changes-without-breakage-15-tools-that-let-you-evolve-safely-3c1554e188d2)
- [Top Database CI/CD and Schema Change Tools 2026 (dbvis)](https://www.dbvis.com/thetable/top-database-cicd-and-schema-change-tools-in-2025/)
- [Confluent — Schema Evolution & Compatibility](https://docs.confluent.io/platform/current/schema-registry/fundamentals/schema-evolution.html)
- [Confluent moves schema IDs to Kafka headers (InfoQ May 2026)](https://www.infoq.com/news/2026/05/confluent-kafka-header-schema-id/)
- [MetaConfigurator (arXiv 2508.05192)](https://arxiv.org/html/2508.05192v2)
- [Migrating Code At Scale With LLMs At Google (arXiv 2504.09691)](https://arxiv.org/abs/2504.09691)
- [Atlas (ariga.io)](https://github.com/ariga/atlas)
- [Unity ScriptableObject manual](https://docs.unity3d.com/Manual/class-ScriptableObject.html)

---

## Q8 — Cross-reference integrity at scale

### Honest framing

500–2000 records is **small** for any serious tool. With ~5 reference fields per record that's ~10K edges. **Naive Python dict-lookup linking handles this in well under a second.** The naive cost only becomes a problem in the 100K–10M record range. Every 2026 graph tool surveyed is built for that range, not yours.

### Performance baseline

- **Pydantic** ~3.5× faster than `jsonschema` for structured validation (dasroot.net Feb 2026).
- **fastjsonschema** (compiled): 0.099s for 1000 records vs `jsonschema`'s 5.22s — ~50× faster.
- **ValidX** (Cython): ~20× faster than `jsonschema`.
- **AJV** (Node): ~50% faster than nearest competitor; 20–190% faster than older libs.

At 2000 records with cross-ref via `record_id_set = {r["id"] for r in all_records}` + per-record `if ref in record_id_set`: **&lt;10ms total in CPython.** Naive does not become slow until ~100K records or until N² nested loops creep in.

### DuckPGQ (the genuinely interesting 2026 option)

- **DuckPGQ** is a community DuckDB extension (not native), v0.1.0 paired with DuckDB v1.1.3.
- Implements SQL:2023 SQL/PGQ — pattern matching, shortest-path, basic graph algorithms.
- DuckDB blog claims 10–100× faster than Neo4j for analytical graph queries. MIT-licensed.
- Use case: load records → `CREATE PROPERTY GRAPH` → `MATCH (a:ability)-[:vfx_id]->(v:vfx) WHERE v IS NULL` finds dangling refs in one query.
- ([duckpgq.org](https://duckpgq.org/), [github.com/cwida/duckpgq-extension](https://github.com/cwida/duckpgq-extension))

**Overkill at 2000 records, useful at 100K+** — but if/when DuckDB integrates SQL/PGQ natively (rumored, not shipped), it becomes the obvious choice for any pipeline that already has DuckDB. **Keep on the radar.**

### Other graph tools

- **KuzuDB** — embedded property graph, Cypher dialect, MIT. Active in 2026. Genuine 10× over Neo4j on analytics. Heavy ceremony at 2K records.
- **Neo4j Community / Memgraph / TigerGraph** — server-process, enterprise-flavored. Skip.

### Validators

- **AJV** (Node, MIT) — fastest validator. `compileAsync` for dynamic ref resolution.
- **Hyperjump JSON Schema** — modern correctness-first, all draft versions, OpenAPI 3.0/3.1, human-readable error rendering. Active March 2026.
- **fastjsonschema / okjson / ValidX** — speed options. **okjson is 116× faster than fastjsonschema** in basic benchmarks; 2× faster than `jsonschema`. ValidX wins via Cython.

JSON Schema's `$ref` is **schema reference**, not record reference. Cross-record FK validation needs a custom AJV/jsonschema keyword OR a post-validation pass OR a graph engine. Your linker is doing the post-validation pass — that's the right answer at this scale.

### Engine-specific

- **Unity:** Odin Validator (~$80) is best-in-class for missing/null asset references. `jeffcampbellmakesgames/unity-asset-validator` (MIT) is the free option.
- **Unreal:** Data Validation plugin (`UEditorValidatorBase`) is Epic's official answer. AAA studios add commandlets walking `FAssetRegistryModule`.
- **Godot:** Zodot (MIT, runtime), or Godot-SQLite GDExtension if you want real FK enforcement at build time.

The pattern across all three engines: **validation plugins + custom commandlets**, not a dedicated tool. Same architecture as your custom linker.

### Recommendations

1. **Audit lookup complexity.** Ensure refs resolve through pre-built `dict[id → record]` maps, not list scans. If currently O(N·M), fixing that beats any new tool.
2. **Add `fastjsonschema` or `okjson`** for record-level validation — 50–100× speedup is free if you're using stock `jsonschema`.
3. **Add a hash-based incremental linker** (~50 LOC): hash each record, store hash + ref-list in `.cache/linker.json`, only revalidate records whose hash changed plus dependents. 90% of Bazel's incrementality at 1% of the engineering cost.
4. **Add `lint_records.py` to CI + pre-commit** — load all records, build ref index once, report orphans. ~100 LOC.
5. **Re-evaluate at 50K records** or when ref-graph queries get genuinely complex (multi-hop "find all NPCs in factions whose lore_term references a deprecated ability"). At that point DuckPGQ or KuzuDB become legitimately attractive — both MIT, embedded, slot in without a server.

### Honest comparison

Existing custom linker wins. Every "real" graph tool surveyed is lateral or worse at this scale. The genuine 2026 option to track is **DuckPGQ** when DuckDB integrates SQL/PGQ natively — at that point switching the linker to a single Cypher-like query is worth it, but not before.

**Sources:**
- [DuckPGQ](https://duckpgq.org/) / [github](https://github.com/cwida/duckpgq-extension) / [VLDB paper](https://dl.acm.org/doi/10.14778/3611540.3611614)
- [KuzuDB](https://github.com/kuzudb/kuzu) / [docs](https://docs.kuzudb.com/)
- [Embedded databases (2): Kùzu (The Data Quarry)](https://thedataquarry.com/blog/embedded-db-2/)
- [AJV](https://ajv.js.org/) / [GitHub](https://github.com/ajv-validator/ajv)
- [Hyperjump JSON Schema](https://github.com/hyperjump-io/json-schema)
- [fastjsonschema](https://horejsek.github.io/python-fastjsonschema/)
- [okjson](https://github.com/mufeedvh/okjson)
- [ValidX benchmarks](https://validx.readthedocs.io/en/latest/benchmarks.html)
- [Pydantic vs JSON Schema 2026](https://dasroot.net/posts/2026/02/structured-output-validation-pydantic-json-schema/)
- [Unity Asset Validator (jeffcampbellmakesgames)](https://github.com/jeffcampbellmakesgames/unity-asset-validator)
- [Odin Validator](https://assetstore.unity.com/packages/tools/utilities/odin-validator-227861)
- [Unreal Data Validation docs](https://dev.epicgames.com/documentation/en-us/unreal-engine/data-validation-in-unreal-engine)
- [Zodot (Godot)](https://godotengine.org/asset-library/asset/2261)

---

## Cross-cutting recommendations — phased roadmap

### Phase A — "run what you already plumbed" (1–2 days, no new infra)
1. Wire **DeepSeek V4-Pro** into `generate_records.py`'s OpenAI-compatible cascade.
2. Run real Anthropic + DeepSeek passes on items, abilities, NPCs, factions, lore_terms — replace the 14 toy synthetic records with ~50 real ones each. Eliminates the "two factions both verdant + balance" and "every ability uses fireball_cast SFX" artifacts immediately.
3. Switch cloud route validation to provider-native structured outputs (OpenAI `response_format`, Anthropic tool-use). Remove client-side validate-and-retry loops on cloud paths.
4. Cost projection: 250 records at DeepSeek bulk + 25 at Opus ≈ **~$0.50–$2** total.

### Phase B — "free wins on existing infra" (3–5 days)
5. Add `pareto_dominated_records.py` (pymoo NSGA-II) as a sibling to `duckdb_reports.py`. Surface dominated abilities/items with their dominators.
6. Swap `jsonschema` → `fastjsonschema` (or `okjson`) in `validate_records.py` for the 50–100× speedup.
7. Add hash-based incremental linker (~50 LOC) on top of the existing custom linker.
8. Add `getsentry/json-schema-diff` CI gate against the migrations directory — fail BREAKING changes without a numbered migration.
9. Add a `localization_key` pre-flight CI script that diffs validated records against `.pot`.

### Phase C — "force multipliers" (1–2 weeks)
10. Wire **DSPy + GEPA** into `generate_records.py` for items/abilities (mechanical, metric-based). Hand-author 5 examples per record type, write metric (schema valid + Pareto-non-dominated + embedding-distance > threshold), let GEPA optimize prompts.
11. Add a Yarn static analyzer (~100 LOC) and runtime coverage hook to `yarn_link.py`.
12. Stand up `source/lore/` with YAML-frontmatter Markdown + Obsidian + Smart Connections vault rooted there. Validate frontmatter via the existing JSON Schema infra.
13. Stand up Crowdin Free + Godot `.po` workflow + Claude Haiku pre-translate script. Pseudo-localization on by default in dev builds.

### Phase D — "after combat exists" (later, conditional)
14. LLM-as-tester one-afternoon pass for degenerate combo detection (~$5 per run).
15. Scripted-heuristic Monte Carlo wrapped in PettingZoo AEC scaffolding when `kill_dummy_sim.py` plateaus.
16. Re-evaluate Machinations.io if the game grows feedback-loop economies.

### What to never do
- Custom game-content LoRA fine-tunes — the niche doesn't exist in usable form.
- RL training on combat balance before combat is built — sunk-cost spiral.
- World Anvil / LegendKeeper / Kanka / Campfire — wrong product category for lore-as-data pipelines.
- Inworld / Convai for dialogue — runtime NPC products, not authoring tools.
- Lokalise / Phrase / Smartling pre-launch — Crowdin Free does the job.
- Atlas / Liquibase for JSON-file schema migration — wrong domain.
- Neo4j / KuzuDB / Memgraph at &lt;20K records — architectural cosplay.

---

## Summary

The pipeline already has best-in-project infrastructure. The 2026 SOTA story is mostly **"run the cascade you plumbed, on real keys, with one extra optimization layer (GEPA) and one extra balance utility (pymoo Pareto)"** — not a wholesale rebuild. The big news items in the brief's window:

- **XGrammar-2** (2026-05-04) — free local-vLLM speedup.
- **DeepSeek V4-Pro** — 30–100× cost reduction vs Opus on the bulk path.
- **DSPy + GEPA** (ICLR 2026 Oral) — genuine prompt-optimization advance for metric-driven record types.
- **JSON Schema GSoC 2026** (SchemaShift) — to track, not yet usable.
- **DuckPGQ** — to track for when SQL/PGQ goes native in DuckDB.

Everything else — Machinations, Inworld, World Anvil, Lokalise, Atlas, Neo4j — is either wrong-shaped, premature, or lateral at the project's current scale and shape.
