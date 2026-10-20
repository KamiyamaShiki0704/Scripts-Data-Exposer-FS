"""Read-only HKS global proof, including RIP operands followed by immediates.

Uses the shared mapper from the sibling fsrs checkout. Executables are never
loaded or executed. A target is accepted only when mapped native consumers
agree; an observed section delta is not an input to resolution.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import capstone as cs
import numpy as np


def load_mapper():
    projects = next(p for p in Path(__file__).resolve().parents if p.name == '_Project')
    path = projects / 'fromsoftware-rs/Scripts/delivery/bug-er-1-17-2-dll-compat/script/map_private_rvas.py'
    spec = importlib.util.spec_from_file_location('native_mapper', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def references(mapper, old, new, target):
    sites = {}
    for residue in range(4):
        count = (len(old.code) - residue) // 4
        values = np.frombuffer(old.code, dtype='<i4', count=count, offset=residue).astype(np.int64)
        positions = np.arange(count, dtype=np.int64) * 4 + residue
        # cmp/test/mov RIP-relative byte operands can have a trailing imm8.
        for trailing in (0, 1, 2, 4, 8):
            hits = positions[values + positions + old.lo + 4 + trailing == target]
            for pos in hits:
                pos = int(pos)
                for back in range(1, 12):
                    start = pos - back
                    if start < 0:
                        continue
                    ins = next(mapper.DECODER.disasm(old.code[start:pos+20], old.lo+start, 1), None)
                    if not ins or ins.disp_offset != back or ins.disp_size != 4:
                        continue
                    if not any(o.type == cs.x86.X86_OP_MEM and o.mem.base == cs.x86.X86_REG_RIP for o in ins.operands):
                        continue
                    if ins.address + ins.size + ins.disp != target:
                        continue
                    # Reject alternate decodings inside an instruction by requiring
                    # a complete identical containing function or unique window.
                    mapped = mapper.map_code(old, new, ins.address)
                    if 'new' not in mapped:
                        continue
                    at = int(mapped['new'], 16)
                    after = next(mapper.DECODER.disasm(new.data(at, 20), at, 1), None)
                    if not after or mapper.neutral(ins.bytes, ins.address)[0] != mapper.neutral(after.bytes, at)[0]:
                        continue
                    sites[ins.address] = {
                        'old_site': hex(ins.address), 'new_site': hex(at),
                        'target': hex(at + after.size + after.disp),
                        'before': f'{ins.mnemonic} {ins.op_str}',
                        'after': f'{after.mnemonic} {after.op_str}',
                        'old_bytes': ins.bytes.hex(), 'new_bytes': after.bytes.hex(),
                        'function_equal': mapped.get('full_equal', False),
                        'unique_window_bytes': mapped.get('prefix'),
                    }
                    if len(sites) >= 8:
                        return list(sites.values())
    return list(sites.values())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    mapper = load_mapper()
    old, new = mapper.Image(mapper.OLD), mapper.Image(mapper.NEW)
    globals_ = {
        'GAME_DATA_MAN': 0x3d61f98, 'CS_NOW_LOADING_HELPER': 0x3d64f28,
        'CS_BULLET_MANAGER': 0x3d667a8, 'DMG_MAN': 0x3d6a3e8,
        'CS_GA_ITEM': 0x3d6d900, 'GAME_MAN': 0x3d6d988,
        'LOCK_TGT_MAN': 0x3d6e278, 'WORLD_MAP_MAN': 0x3d6e390,
        'CS_FE_MAN': 0x3d6f8f0, 'CS_SESSION_MANAGER': 0x3d7e540,
        'CS_WINDOW': 0x458f910, 'CSFLIPPER': 0x458db58,
        'NO_DEATH_PLAYER': 0x3d6a210, 'NO_DEATH_TORRENT': 0x3d6a211,
        'ONE_SHOT_EVERYTHING': 0x3d6a212, 'ALL_NO_CONSUMABLES_CONSUME': 0x3d6a213,
        'UNLIMITED_SP': 0x3d6a214, 'UNLIMITED_FP': 0x3d6a215,
        'ALL_NO_ARROW_CONSUME': 0x3d6a216, 'HIDE_PLAYER': 0x3d6a218,
        'SILENCE_PLAYER': 0x3d6a219, 'FORCED_PARRY': 0x3d6a21d,
    }
    results = []
    for name, target in globals_.items():
        sites = references(mapper, old, new, target)
        targets = sorted({s['target'] for s in sites})
        result = {'name': name, 'old': hex(target), 'new': targets[0] if len(targets) == 1 else None,
                  'targets': targets, 'references': sites}
        results.append(result)
        print(name, result['old'], result['new'], len(sites), flush=True)
    report = {'old_sha256': hashlib.sha256(mapper.OLD.read_bytes()).hexdigest(),
              'new_sha256': hashlib.sha256(mapper.NEW.read_bytes()).hexdigest(), 'globals': results}
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    if any(r['new'] is None for r in results):
        raise SystemExit('unresolved or ambiguous globals; no patch authorized by this result')


if __name__ == '__main__':
    main()
