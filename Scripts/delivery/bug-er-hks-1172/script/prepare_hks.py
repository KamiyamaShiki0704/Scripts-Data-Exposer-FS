"""Prepare seven address-only HKS updates, retaining exact byte preimages.

No game code is executed and no installed script is modified. Native mapping
reports must already exist. Replacement is simultaneous, so an old vector end
equal to the new vector base cannot be replaced twice.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

NEW_EXE_HASH = 'f9118fea2cfd8fa3901e8060bfadb1552cb2471771ded8a5b662c4e298ffb328'
FILES = ['c0000.hks', 'c9997.hks', 'Module/exposer/GameBasePointers.hks',
         'Module/MovementControl.lua', 'Module/LoadingScreens.hks',
         'Module/LockTargetTeleport.lua', 'Module/EnemySummon.lua']


def sha(data):
    return hashlib.sha256(data).hexdigest()


def rewrite(raw, replacements):
    counts = {}

    def substitute(match):
        old = int(match[0], 16)
        if old not in replacements:
            return match[0]
        counts[hex(old)] = counts.get(hex(old), 0) + 1
        text = format(replacements[old], 'X' if any(65 <= c <= 70 for c in match[0]) else 'x')
        return match[0][:2] + text.encode('ascii')

    updated = re.sub(rb'0[xX][0-9a-fA-F]+\b', substitute, raw)
    # Update an old version label only on the exact line whose address changed.
    updated = b''.join(new.replace(b'ER 2.7.0', b'ER 2.7.2') if old != new else new
                       for old, new in zip(raw.splitlines(keepends=True), updated.splitlines(keepends=True)))
    return updated, counts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--script-root', type=Path, required=True)
    parser.add_argument('--evidence-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('output already exists; refusing to replace a prepared transaction')
    globals_ = json.loads((args.evidence_root / 'hks-global-proof.json').read_text())
    if globals_['new_sha256'] != NEW_EXE_HASH or len(globals_['globals']) != 22:
        raise SystemExit('wrong or incomplete executable mapping')
    replacements = {}
    for record in globals_['globals']:
        if not record['new'] or len(record['targets']) != 1 or not record['references']:
            raise SystemExit('ambiguous or unresolved global')
        replacements[int(record['old'], 16)] = int(record['new'], 16)
    fields = json.loads((args.evidence_root / 'hks-field-proof.json').read_text())
    for old, new in [(0x1e648, 0x1e658), (0x1ece0, 0x1ecf0), (0x1f1d0, 0x1f1e0)]:
        observed = {int(r['new_field'], 16) for r in fields if int(r['old_field'], 16) == old}
        if observed != {new}:
            raise SystemExit(f'field mapping missing or ambiguous: {old:x}')
        replacements[old] = new
    # DLVector consumers prove allocator/+8 begin/+10 end/+18 capacity.
    # Evidence: old 505499/5069f5, new 5055cc/506c26; member layout unchanged.
    replacements.update({0x1f1d8: 0x1f1e8, 0x1f1e0: 0x1f1f0})
    protected = {str(f.relative_to(args.script_root)): sha(f.read_bytes())
                 for f in args.script_root.rglob('*') if f.is_file()}
    entries = []
    for name in FILES:
        target = args.script_root / name
        before = target.read_bytes()
        after, counts = rewrite(before, replacements)
        if not counts or before == after:
            raise SystemExit(f'no expected old offsets in {name}')
        # Only changed address literals may differ, including literal comments.
        if re.sub(rb'0[xX][0-9a-fA-F]+\b', b'ADDRESS', before) != re.sub(rb'0[xX][0-9a-fA-F]+\b', b'ADDRESS', after.replace(b'ER 2.7.2', b'ER 2.7.0')):
            raise SystemExit('non-address byte changed')
        backup, candidate = args.output / 'before' / name, args.output / 'candidate' / name
        for path, data in [(backup, before), (candidate, after)]:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            if path.read_bytes() != data:
                raise SystemExit('copy readback failed')
        entries.append({'relative': name, 'target': str(target), 'backup': str(backup),
                        'candidate': str(candidate), 'old_sha256': sha(before),
                        'new_sha256': sha(after), 'replacements': counts})
    manifest = {'status': 'PREPARED', 'game_sha256': NEW_EXE_HASH,
                'script_root': str(args.script_root.resolve()), 'files': entries,
                'protected': protected, 'scope': 'address literals only; game acceptance pending'}
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps({'files': len(entries), 'protected': len(protected),
                      'address_replacements': sum(sum(e['replacements'].values()) for e in entries),
                      'manifest': str(args.output / 'manifest.json')}))


if __name__ == '__main__':
    main()
