# Changelog

## Unreleased

- Enforced the Kilo identity at the combined streaming boundary so local and cloud
  provider names cannot leak through when a self-introduction is split across chunks;
  expanded provider/model coverage while preserving ordinary factual references.
- Reconciled the README and version-controlled Wiki with the current daemon, TUI, CLI,
  Ollama, cloud, Telegram, MCP, and installer behavior.
- Documented explicit route selection, live endpoint/model state, cloud model selection,
  and the local-only Ollama load and unload controls.
- Replaced obsolete setup descriptions with verified installation, operations, security,
  troubleshooting, and testing workflows.
- Added the self-contained `sudo kiloframe uninstall` command so removal works from any
  directory, and completed the missing `kiloframe local load` CLI operation.
- Fixed streamed TUI reply borders to follow one stable pane width for Sir's input and
  Kilo's reply, including split and resized SSH terminals, so output cannot spill into the
  sidebar or shift between turns.
- Reflow Sir and Kilo transcript boxes whenever the output pane changes width, keeping
  both side rails connected with no stale-width gap after a terminal resize.
- Removed the extra blank row between adjacent Sir and Kilo boxes, and reserve
  TextArea's edge cell so a terminal never soft-wraps a border into a phantom blank row.
- Current verification covers 205 automated tests plus production installer and Ollama
  checks.

## v1.0.0 (2024-09-07)

### Complete Rebrand
- Renamed from Kilobyte Framework to KiloFrame
- Updated all branding, commands, and references
- New ASCII art: "KILOFRAME" with "Developed by Citadel Research"

### Ollama Integration
- Removed all GGUF/custom brain handling
- Added full Ollama client and runtime
- Support for local and remote Ollama servers
- Commands: `/local`, `/localset`, `/switch`

### TUI Redesign
- Left sidebar with tasks, work, context, processes, memory
- OpenCode-inspired command system
- Hacker green accent color scheme
- Maintains Kilo/Sir conversation boxes

### New Commands
- `/local` - Ollama management
- `/localset` - Server configuration
- `/switch` - Toggle Ollama/cloud
- `/thinking` - Set reasoning depth
- `/private` - Tor routing

### Integrations
- Superpowers skills (14 skills)
- Serena MCP integration
- Context7 documentation lookup
- Provider support for 25+ cloud LLMs

### Installer/Uninstaller
- Cross-distro support (Arch, Debian, Fedora, openSUSE, Alpine)
- Automatic Ollama config seeding
- Clean uninstall with `uninstall.sh`

### Documentation
- README with installation guide
- Comprehensive Wiki
- API reference
- Troubleshooting guide
- Command reference

### Tests
- 154 tests passing
- Ollama protocol tests
- Runtime tests
- CLI tests
- Installation tests
