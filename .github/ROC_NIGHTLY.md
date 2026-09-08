# Roc nightly updates

The caller checks daily at 13:31 UTC. Compiler pins live in the `roc` header
fields selected by `.github/roc-nightly.json`; all selected headers must agree.
The updater changes those literals only. Dependency URLs require a separate
reviewed change. `.roc-version` has been removed.

Both reusable workflows are pinned to
`b60d561cbd53c911b29238b30624827f8487113a`. The shared workflow pins its nested
nightly action to `ce402b2786852d7061dd6c91a6a118e886521e3c`.
Automatic merging is explicitly disabled. The caller grants `statuses: write`
as required by the shared workflow's permission ceiling; individual jobs narrow
permissions. Candidate CI has read-only repository permissions and cannot release
or deploy. Dependabot proposes reviewed workflow updates.

The pin reader in `scripts/compiler_pins.py` is vendored from the same reviewed
workflow revision under UPL-1.0. CI export and C glue generation use that reader.

Follow the [integration guide](https://github.com/lukewilliamboswell/roc-automation/blob/b60d561cbd53c911b29238b30624827f8487113a/docs/integration.md).
Reserve `automation/roc-nightly` for bot pin-only commits; put source fixes on a
separate branch. Do not weaken tests or rewrite release URLs to accept a nightly.

## Rollout evidence and remaining work

- The 2026-09-07 [scheduled run](https://github.com/lukewilliamboswell/roc-platform-template-go/actions/runs/34151126852)
  failed when calling the PR-creation API. The old controller hid API stderr.
- Inspection on 2026-09-08 found read-only default token permissions, all Actions
  allowed, and Actions PR creation disabled (`can_approve_pull_request_reviews:
  false`). GitHub uses this setting for both PR creation and approval; the
  controller only creates PRs and never approves them. The setting was enabled
  on 2026-09-08 and read back successfully; default permissions remain read-only.
- `main` now requires PRs and the strict GitHub Actions `CI result` check, with
  zero additional reviewer approvals, no bypass actors, and force-push/deletion
  protections. Automatic nightly merging remains disabled.
- No platform release exists. Current-source CI tests fresh bundles. Follow the
  [first-release checklist](../CONTRIBUTING.md#release-checklist) to establish
  immutable public URLs, starters, and a separate published-download lane.
- The migrated [live updater](https://github.com/lukewilliamboswell/roc-platform-template-go/actions/runs/34199665795)
  created [PR #22](https://github.com/lukewilliamboswell/roc-platform-template-go/pull/22).
  Its GitHub-verified commit changes only the 13 configured compiler-pin literals;
  validation was dispatched against that exact head. The stale reserved branch
  from the failed legacy updater contained only a `.roc-version` change and was
  reset to the migrated base after preserving its commit locally.
- Manual mode does not mirror required status checks. GitHub held the ordinary
  bot PR workflows for approval; these were approved after inspecting the pin-only
  diff. The bootstrap PR merged through the required `CI result` rule without a
  bypass. Compiler promotion remains a separate manual review.

## Local migration validation (2026-09-08)

With the unchanged header nightly and Go 1.27.0 / Zig 0.16.0:

- Shared controller `check`, five maintenance regression tests, generated C glue,
  Roc formatting, Go tests/vet, docs generation, and runtime checksums passed.
- All ten Go host archives rebuilt. All 12 examples checked/tested and all 120
  application/target combinations cross-compiled on Linux x86-64.
- Both Linux x86-64 target variants passed all 27 cases from retained artifacts.
  The exact retained archive also passed 12 checks, 12 tests, 12 native builds,
  and 27 cases through `--bundle`.
- The README's direct example command printed `Hello, World!`.
- Published mode correctly rejected the current local dependencies. No published
  download test or macOS/Windows native execution is claimed by this local run.

The nightly migration is part of the runtime publisher bootstrap PR. The live
nightly updater trial is separate from the runtime release acceptance run.
