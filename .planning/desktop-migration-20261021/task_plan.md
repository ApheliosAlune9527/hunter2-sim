# Desktop migration package

## Objective
Create a verified package for the user to transfer with ToDesk from this Windows computer to the ASUS Windows desktop. Target project path: D:\rob-memory. Preserve all project files, the stopped Ubuntu-22.04 VHDX, Codex conversation/attachment/memory/config state and custom skills. Keep originals unchanged. Do not transmit files over the network.

## Phases
1. Inventory source data, available space and live-state constraints — complete
2. Build consistent local snapshots and target-specific restore instructions — complete
3. Create a ZIP64 transfer archive and verify contents/checksums — complete
4. Deliver the archive and minimal ToDesk/restore instructions — complete

## Decisions
- The user selected ToDesk transfer instead of LAN sharing.
- Temporary firewall rule CodexMigration-20261021-DesktopSMB was removed.
- Use a dedicated output directory outside F:\rob-memory to avoid recursive inclusion.
- SQLite stores must use SQLite online backup, not raw copies of an active database/WAL.
- Authentication and disposable machine-specific caches are not needed for a fresh login; explicitly record exclusions.
- A live Codex snapshot ends at the snapshot time; do not promise inclusion of subsequent messages.
- Package all 13.21 GB of regular project files directly from the source, plus a consistent Codex snapshot, .agents, and selected supplemental app artifacts. Do not follow the two node_modules runtime junctions.
- Preserve source files and historical transcript bodies. Adapt operational copies of database paths/global settings for C:\Users\ASUS and D:\rob-memory; preserve pre-adaptation metadata alongside them.
- Provide guarded PowerShell restoration scripts; do not run them on the source computer. Keep project scripts/evidence byte-for-byte intact and list F-to-D runtime path adjustments in the guide.

## Errors
First snapshot verification treated .jsonl.zst transcripts as missing .jsonl files. Investigation confirmed all files were copied, with 166 compressed normal transcripts and 2 compressed archived transcripts. The verifier now accepts Codex's compressed representation. Earlier LAN connection tests timed out; the user replaced that transfer approach.

The initial ZIP writer then rejected plugin timestamps before 1980. Recovered the valid partial archive, clamped 296 unsupported ZIP timestamps without changing file bytes, appended remaining files, and verified every file SHA256 against the source/snapshot. The reusable builder was amended to accept old timestamps and close SQLite connections explicitly.

## Verified deliverables
- F:\rob-memory-migration-20261021\rob-memory_迁移包_20261021.zip
- Size: 5,272,660,369 bytes; 14,293 archive entries.
- SHA256: d38c199fd1e5442eac2dcd707bd8eadb45d4b50fce2273e7ab2b21a89e0ce734
- 149 indexed conversations; 177 normal and 2 archived transcript files; 59 attachment files; 5 independently valid SQLite snapshots; zero missing indexed conversation files.
- The entire project payload (12,101 regular files, 13,206,725,054 bytes) was archived verbatim at capture time, including the stopped 7,974,420,480-byte Ubuntu VHDX. Two app-runtime node_modules links were recorded rather than followed.
- Five databases extracted from the ZIP and opened in immutable mode without WAL/SHM all passed integrity_check; the restored project root record is D:\rob-memory.
- New target restore scripts were syntax-checked and confirmed to refuse execution on the source computer. Full restoration still requires execution and validation on the ASUS desktop.
