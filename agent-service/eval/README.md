# Automated evaluation

Output-quality eval for the required 7-step scenario. Runs the real conversation against the
self-hosted Qwen and scores it two ways:

- **Deterministic checks** (`scenario_eval.py`) — ground-truth assertions:
  - `voice_correction_persisted` — the "warm/grassroots" correction was saved to memory
  - `suggestions_in_ledger` — suggested posts were recorded
  - `next_month_idea_is_new` — the "next month" idea introduced a new ledger title (no repeat)
- **LLM-as-judge** (`judge.py`) — 1-5 scores for what assertions can't capture:
  - `voice_adherence` — the Instagram caption is warm/grassroots, not corporate
  - `platform_adaptation` — the LinkedIn vs Instagram drafts are genuinely platform-appropriate
  - `novelty_next_month` — the new suggestion isn't a rephrase of an earlier one
  - `qa_grounded` — the programs answer matches the org's real programs

The draft steps are judged on the **actual caption** the `draft_post` tool produced (captured via
the draft sink), not the conversational wrapper message — judging the wrapper would be unfair.

## Run

Needs a Postgres for the app schema and the LLM (+ embedder for grounding):

```bash
cd agent-service
DATABASE_URL=postgresql://npo_app:changeme@localhost:55432/npo \
MIGRATION_DATABASE_URL=postgresql://npo_owner:changeme@localhost:55432/npo \
LLM_BASE_URL=http://localhost:6888/v1 \
EMBED_BASE_URL=http://localhost:8090/v1 \
.venv/bin/python -m eval.scenario_eval
```

Prints a scorecard, writes a full JSON report (incl. the transcript + captions) to
`eval/results/`, and exits non-zero if the judge mean is below `PASS_THRESHOLD` (3.5) or any
deterministic check fails — so it can gate CI.

## Caveats / next steps

- **Self-judging bias.** The judge is the same Qwen, which tends to favour its own style. Mitigated
  by a concrete rubric + the deterministic checks. Next: a different judge model family + a small
  human-rated golden set to calibrate.
- **Run-to-run variance.** Decoding is at temperature 0.3, so scores move a little between runs;
  the deterministic checks are the stable signal.
- See `docs/DESIGN.md` §5 for the fuller discussion.
