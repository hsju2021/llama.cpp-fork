# Server compute profile experiment

This directory is the immutable result set created for the CPU-only `llama-server` semantic phase experiment on 2026-09-05.

Start with:

- `REPORT.md`: conclusions, evidence, performance table, and validation status
- `REPRODUCE.md`: build and rerun commands
- `environment.md`: host, build, and model details
- `changes-tracked.diff`: tracked source changes
- `changes-new-server-test.diff`: new server pytest
- `changes-new-workload.diff`: HTTP workload driver
- `changes-new-trace-analyzer.diff`: trace analyzer

Machine-readable results:

- `analysis/functional-assertions.json`: legacy/AUTO output equivalence
- `analysis/trace-summary.json`: phase ratios and representative physical ubatch evidence
- `analysis/performance-summary.json`: five-repeat performance summaries
- `raw/functional.json`: raw functional HTTP results
- `raw/performance.json`: raw performance results
- `commands-functional.json` and `commands-performance.json`: exact server command arrays
- `execution-order.json`: deterministic shuffled performance order
- `tokenizer.json`: tokenizer and special-token observations

All server logs are under `logs/`. Files with `without-token-intervals` in their name are a preserved earlier trial and are not the reported final result.
