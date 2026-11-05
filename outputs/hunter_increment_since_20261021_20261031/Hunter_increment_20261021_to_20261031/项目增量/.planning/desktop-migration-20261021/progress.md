# Migration progress

## 2026-10-21 Asia/Shanghai
- User requested an archive for ToDesk transfer and superseded LAN transfer setup.
- Removed the temporary inbound SMB firewall rule; no SMB shares or temporary users were created.
- Loaded planning-with-files-zh and verification-before-completion skills.
- Read preflight free space and Codex database sizes. Begin detailed inventory and snapshot design.
- Detailed inventory found about 13.21 GB of regular project data, with no read errors. The Ubuntu VHDX is stopped.
- Identified 149 indexed Codex conversations and 179 normal/archived transcript files. Database schema and app artifact storage locations inspected without printing conversation contents or secrets.
- Packaging design: ZIP64, online SQLite backups, operational path adaptation on copies, preserved original metadata, guarded restoration scripts, streamed checksums and complete archive verification.
- Initial index/file cross-check stopped before archiving because older transcripts use .jsonl.zst while database paths retain the logical .jsonl name. All 177 normal and 2 archived transcript files were present; amended the cross-check to accept compressed Codex transcripts. Preserve the first attempt separately and build a fresh snapshot.
- ZIP creation encountered 296 reproducible plugin timestamps before 1980. Retained all already-compressed large project/Ubuntu data, appended remaining files with ZIP timestamp compatibility, and verified all 14,293 entries against source/snapshot SHA256 plus ZIP CRC.
- Final archive size 5,272,660,369 bytes, SHA256 d38c199fd1e5442eac2dcd707bd8eadb45d4b50fce2273e7ab2b21a89e0ce734; an independent Windows file hash matches the sidecar checksum.
- Independently extracted and opened all five SQLite databases without sidecar journals. All integrity checks passed, with 149 threads and D:\rob-memory as the target project root. Zero indexed transcript files are missing, including compressed records.
- Source-machine guards in both restore scripts refused execution as intended. Authentication credentials and Windows sandbox are excluded; user configuration, attachments, memories, skills and the Ubuntu VHDX are retained.
- Final files are ready under F:\rob-memory-migration-20261021. Remove only verified task-generated staging copies; leave project originals and final deliverables intact.
- Automatic approval review rejected the generated-staging cleanup command with only "blocked by policy" and no specific reason. The command did not run. Preserve _work and the first-attempt directory; do not retry destructive cleanup through another mechanism. The verified ZIP, checksum and restoration guide are ready and unaffected.
