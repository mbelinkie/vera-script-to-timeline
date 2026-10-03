"""Verify/extract published evidence using only Python's standard library.

Never imports Resolve, runs a collector, dispatches an action or changes sources.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', type=Path, help='Create a NEW directory of decoded logical records')
    parser.add_argument('--refresh-document-hashes', action='store_true', help='Publication preparation only: record edited Markdown hashes')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    manifest_path = Path(__file__).with_name('publication-manifest.json')
    manifest = json.loads(manifest_path.read_text())
    if args.extract:
        args.extract.mkdir(parents=True, exist_ok=False)
    changed = 0
    text_count = 0
    for row in manifest['records']:
        relative = Path(row['published'])
        logical = Path(row['source'])
        assert not relative.is_absolute() and '..' not in relative.parts
        assert not logical.is_absolute() and '..' not in logical.parts
        path = root / relative
        stored = path.read_bytes()
        data = gzip.decompress(stored) if row['compressed'] else stored
        if args.refresh_document_hashes and digest(stored) != row['publishedSha256']:
            assert logical.suffix == '.md', f'Non-document changed: {relative}'
            row.update(publishedSha256=digest(stored), decodedPublishedSha256=digest(data), bytes=len(stored), decodedBytes=len(data), editorialCorrection=True)
            changed += 1
        assert digest(stored) == row['publishedSha256'], f'Stored hash mismatch: {relative}'
        assert digest(data) == row['decodedPublishedSha256'], f'Decoded hash mismatch: {relative}'
        assert len(stored) < 100_000_000, f'GitHub file limit: {relative}'
        if row['sanitizedText']:
            text = data.decode('utf-8')
            assert '/Users/' not in text, f'Private home path: {relative}'
            assert '/private/var/' not in text, f'Private temporary path: {relative}'
            text_count += 1
        else:
            assert b'/Users/' not in data, f'Private path in binary metadata: {relative}'
        if args.extract:
            target = args.extract / logical
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    if args.refresh_document_hashes:
        manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'recordsVerified': len(manifest['records']), 'sanitizedTextRecords': text_count, 'correctedDocumentHashes': changed, 'nativeActions': 0}))


if __name__ == '__main__':
    main()
