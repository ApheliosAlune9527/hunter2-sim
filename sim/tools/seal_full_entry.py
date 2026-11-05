"""Hash only the fixed reviewed local entry files; never execute programs."""
import json
import sys

from check_full_entry import ROOT, MANIFEST_REL, SEALED_PATHS, local_file, sha256, validate_args


def build_manifest(root=ROOT):
    return {'schema_version': 1, 'files': [
        {'path': relative, 'sha256': sha256(local_file(root, relative))}
        for relative in SEALED_PATHS]}


def main():
    validate_args(sys.argv[1:])
    manifest = build_manifest()
    (ROOT / MANIFEST_REL).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'sealed_files': len(manifest['files']), 'manifest': MANIFEST_REL}))


if __name__ == '__main__':
    main()
