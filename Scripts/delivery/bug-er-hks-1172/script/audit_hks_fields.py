"""Compare WorldChrMan field consumers; do not extrapolate a struct-wide delta."""
import argparse
import difflib
import json
import struct
from pathlib import Path

from audit_hks_globals import load_mapper


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    mapper = load_mapper()
    old, new = mapper.Image(mapper.OLD), mapper.Image(mapper.NEW)
    fields = [0x10fa8, 0x1e508, 0x1e648, 0x1ece0, 0x1f1d0, 0x1f1d8, 0x1f1e0]
    functions = set()
    for field in fields:
        pattern = struct.pack('<I', field)
        cursor = 0
        while True:
            hit = old.code.find(pattern, cursor)
            if hit < 0:
                break
            cursor = hit + 1
            bounds = old.function(old.lo + hit)
            if bounds:
                functions.add(bounds[0])

    def key(ins):
        value = bytearray(mapper.neutral(ins.bytes, ins.address)[0])
        if ins.disp in fields or 0x1e500 <= ins.disp < 0x1f800:
            if ins.disp_size == 4:
                value[ins.disp_offset:ins.disp_offset+4] = b'\xaa' * 4
        return bytes(value)

    results = []
    for start in sorted(functions):
        mapped = mapper.map_code(old, new, start)
        if 'new' not in mapped:
            continue
        at = int(mapped['new'], 16)
        if at not in new.functions:
            continue
        before = list(mapper.DECODER.disasm(old.data(start, old.functions[start]-start), start))
        after = list(mapper.DECODER.disasm(new.data(at, new.functions[at]-at), at))
        for tag, i, j, k, l in difflib.SequenceMatcher(None, list(map(key, before)), list(map(key, after)), autojunk=False).get_opcodes():
            if tag != 'equal':
                continue
            for a, b in zip(before[i:j], after[k:l]):
                if a.disp in fields:
                    results.append({'old_field': hex(a.disp), 'new_field': hex(b.disp),
                                    'old_site': hex(a.address), 'new_site': hex(b.address),
                                    'before': f'{a.mnemonic} {a.op_str}', 'after': f'{b.mnemonic} {b.op_str}',
                                    'old_bytes': a.bytes.hex(), 'new_bytes': b.bytes.hex()})
    args.output.write_text(json.dumps(results, indent=2), encoding='utf-8')
    for field in fields:
        matches = [r for r in results if int(r['old_field'], 16) == field]
        print(hex(field), sorted({r['new_field'] for r in matches}), len(matches))


if __name__ == '__main__':
    main()
