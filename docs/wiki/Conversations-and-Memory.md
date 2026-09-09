# Conversations and memory

KiloFrame persists terminal conversations and operational memory in
`/var/lib/kiloframe/memory.sqlite3`. Closing the TUI or restarting the daemon does not
erase them.

## Sessions

- A first normal prompt creates a session.
- `/new` detaches the current TUI from that session so the next prompt creates another.
- `/chats` lists recent terminal sessions with time, title, and message count.
- `/chats N` resumes a session from the most recently displayed list.
- `/delete` opens a selector; `/delete N`, `/delete N,M`, and `/delete all` remove selected
  sessions and their messages.

`/clear` only clears what is rendered on screen. It does not delete the persisted session.
`/quit` only closes the client. Use the delete commands when actual history removal is
intended.

## Automatic compaction

KiloFrame can compact conversation context. It does this automatically when replaying
history would exceed the configured model-facing budget:

1. recent turns are retained in chronological order;
2. older turns become a bounded, role-labelled summary of requests, decisions, and
   references;
3. the daemon emits a `compaction` event;
4. the TUI shows `conversation compacted` with the number of earlier turns affected.

The full stored messages are not overwritten by this operation. Compaction limits what is
sent to the model for the current request; it is not destructive summarization of the
SQLite history. There is therefore no manual `/compact` command.

## Tool-result compaction

Tool output has its own budget. When a command, file listing, or structured result is too
large, KiloFrame preserves useful head/tail content, surrounding structure, exit status,
and paths while marking omitted content. This avoids crowding the user's current task out
of the context window.

## Facts, skills, and audit

The database also contains:

- bounded learned facts used for relevant recall;
- bounded skills ordered by observed reliability;
- a tool audit containing session, tool, arguments, outcome, remote flag, and timestamp.

Imported Superpowers procedures use the skill system. Relevant skills are injected as a
separate context message only when applicable rather than permanently added to the system
prompt.

## Limits and backup

Default bounds in the application include 10,000 stored messages, 2,000 facts, and 200
skills. The model-facing history budget is separate from those storage bounds.

Back up while preserving ownership and permissions:

```bash
sudo cp -a /var/lib/kiloframe /var/lib/kiloframe.backup
```

`sudo kiloframe uninstall` removes this data. Reinstallation without uninstall preserves it.
