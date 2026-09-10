# Testing and verification

KiloFrame distinguishes source tests from a usable installed application. Release
verification covers all layers below.

## Source checks

From a checkout:

```bash
bash -n scripts/install.sh scripts/install-online.sh scripts/uninstall.sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
git diff --check
```

Tests cover RPC/model paths, TUI and Telegram command handling/rendering state, Telegram
directive enforcement on local and cloud routes, Ollama semantics, integration
configuration, permissions, status, installation scripts, and memory. Passing
them does not prove terminal usability or external connectivity.

## Installer acceptance

The public one-line command must be executed, not merely parsed. Verify:

- correct archive/revision downloaded without stale cache;
- dependencies and required integrations installed;
- command wrapper and system paths created;
- daemon starts or restarts on systemd and non-systemd;
- status is printed and returns accurately;
- rerun preserves configuration and data;
- failures return nonzero.

For changes to fresh-install behavior, test a clean install, launch, basic interaction,
exit, restart, uninstall, reinstall, and repeat interaction. Back up any target's existing
config/data before destructive testing.

## Integration acceptance

```bash
command -v context7-mcp
command -v serena
command -v playwright-cli
kiloframe logs -n 200
```

Confirm Context7 and Serena start and report discovered tools. Confirm Superpowers skills
are imported. Confirm Playwright agent skills were installed. Do not mark Exa, GitHub MCP,
Firecrawl, Telegram, or cloud providers verified without the needed external credentials.

With Telegram credentials available, send `/start`, `/local_models`, `/local_ps`, and a
short prompt on the local route, then `/cloud` or `/switch` and another short prompt. Check
that both completed answers begin `Sir, ` and end `, Sir.` and that local model controls
reflect the active Ollama server. The focused automated check is:

For each configured cloud provider, also ask the same machine-action question and verify
that Kilo keeps its identity, uses the supplied tools instead of denying access, requests
approval for state-changing work, and resumes after approval. Provider adapters send the
same consolidated system contract, so these expectations do not vary by endpoint.

```bash
PYTHONPATH=src python3 -m unittest tests.test_telegram -v
```

## Ollama acceptance

Against a real reachable endpoint:

```bash
kiloframe localset list
kiloframe local status
kiloframe local models
kiloframe local select <reported-model>
kiloframe chat "Reply with a short verification message."
kiloframe local ps
kiloframe local unload <reported-model>
```

Remote switching can only be called verified when two genuinely reachable endpoints were
used. Configurability can still be source/integration tested without claiming that.

## Human TUI acceptance

Run `kiloframe` in a real PTY and visibly inspect:

- KILOFRAME wordmark and credit alignment;
- borders, spacing, Kilo/Sir separation, and sidebar at supported widths;
- truthful offline/unselected/selected/loaded states;
- `/commands` completion and rendered list;
- interactive model/server menus and number selection;
- streamed real inference;
- live thinking/tool/recovery/failure events inside Kilo's box;
- `/new`, session browse/resume/delete, `/cancel`, and `/quit`;
- relaunch after daemon restart.

Automated keystrokes can reproduce paths, but the captured real terminal must still be
visually inspected. A mocked response cannot verify real inference.

## Final audit

Search for stale product branding, retired runtime paths, private addresses, secrets,
fake readiness language, documentation drift, broken links, ignored failures, and
unexpected contributor attribution. Confirm the installed CEO revision matches GitHub
and synchronize `docs/wiki/` to the hosted Wiki.
