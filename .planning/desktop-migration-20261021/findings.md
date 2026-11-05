# Migration findings

- Source project: F:\rob-memory; source Windows profile C:\Users\Aphelios.
- Destination project: D:\rob-memory; destination Windows profile C:\Users\ASUS, confirmed by user-provided PowerShell output.
- Source Codex home: C:\Users\Aphelios\.codex, default CODEX_HOME.
- Other user skills: C:\Users\Aphelios\.agents.
- Supplemental app data: C:\Users\Aphelios\AppData\Roaming\Codex.
- Ubuntu-22.04 is registered under F:\rob-memory\wsl\Ubuntu22.04; VHDX length observed earlier: 7,974,420,480 bytes; default Linux user aphelios.
- Source F: has about 233.9 GiB free; C: about 67.8 GiB free at preflight.
- Codex has active processes. Database backups and completed transcript records are required for a consistent snapshot.
- Project scripts contain F:\rob-memory and /mnt/f/rob-memory references. Historical evidence must remain unmodified; adapt runtime copies during restoration.
- No source-root AGENTS.md files were discovered; user-level .codex/AGENTS.md is empty.

## Documentation already consulted
- https://learn.chatgpt.com/docs/config-file/config-advanced#config-and-state-locations
- https://learn.chatgpt.com/docs/reference/troubleshooting (local sessions/archived_sessions)
- https://learn.microsoft.com/en-us/windows/wsl/basic-commands#import-a-distribution-in-place

These links establish storage locations and WSL import commands; they do not guarantee cross-computer Codex UI restoration.

## Detailed inventory
- Project: 12,097 regular files, 13,206,690,757 bytes at inventory time; two node_modules junctions point to the app-managed dependency runtime.
- Codex: approximately 1.62 GB including disposable sandbox/cache/temp files; 149 indexed conversations, 177 normal transcript files, 2 archived transcript files, 59 attachment files.
- .agents: 264 files, approximately 3.1 MB.
- Roaming data: Chromium profile including caches, authentication stores and about 4.1 MB of artifact-session data. Preserve artifact sessions and preferences as supplementary data; exclude browser credentials/caches and live LevelDB profiles.
- WSL Ubuntu-22.04 remains stopped. Its VHDX can be archived without starting/stopping Linux processes.
- No reparse-point directories in .agents or .codex/skills. One cached Chrome plugin latest junction also points to its sibling versioned package; record it for restoration.
