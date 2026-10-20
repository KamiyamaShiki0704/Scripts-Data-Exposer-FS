"""Resolve production AOBs/calls, verify target uniqueness and emit exact guards."""
import argparse,hashlib,json,re,struct
from pathlib import Path
import capstone
import pefile

parser=argparse.ArgumentParser()
parser.add_argument('--old',required=True)
parser.add_argument('--new',required=True)
parser.add_argument('--report',required=True)
args=parser.parse_args()
root=Path(__file__).resolve().parents[4]
source=(root/'game/AOBScan.h').read_text()
source='\n'.join(line for line in source.splitlines() if not line.lstrip().startswith('//'))
patterns=dict(re.findall(r'const char\*\s+(\w+)\s*=\s*"([^"]+)"',source))
decoder=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64)
profiles=[];lines=['// Generated from production AOB source and fixed EXEs.','#pragma once',
 'struct ExposerBinding {const char* name; uintptr_t rva; const unsigned char* bytes; size_t length;};']
for path,label,expected in [(args.old,'271','1a3547101327f65d0c76da2f9190ac0aa66871ea42bae2aecc61e11a8b597891'),
                            (args.new,'272','f9118fea2cfd8fa3901e8060bfadb1552cb2471771ded8a5b662c4e298ffb328')]:
    raw=Path(path).read_bytes();assert hashlib.sha256(raw).hexdigest()==expected
    pe=pefile.PE(data=raw,fast_load=True);section=pe.sections[0];text=section.get_data()[:section.Misc_VirtualSize]
    records=[]
    for m in re.finditer(r'RegisterAddress\("([^"]+)".*?,\s*(AOBScan\w+)\((\w+)([^)]*)\)\);',source):
        name,kind,key,tail=m.groups();tokens=patterns[key].split()
        rx=b''.join(b'.' if t in ('?','??') else re.escape(bytes([int(t,16)])) for t in tokens)
        hits=[section.VirtualAddress+h.start() for h in re.finditer(rx,text,re.S)]
        offsets=[int(v.strip(),0) for v in tail.split(',') if v.strip()]
        def resolve(at):
            if kind=='AOBScanCode':return at+(offsets[0] if offsets else 0)
            if kind=='AOBScanBase':
                end,operand=offsets if offsets else [7,3]
                return at+end+struct.unpack('<i',pe.get_data(at+operand,4))[0]
            if kind=='AOBScanCodeCall':
                end,operand=offsets
                return at+5+end+struct.unpack('<i',pe.get_data(at+operand+1,4))[0]
            raise AssertionError(kind)
        targets=sorted({resolve(h) for h in hits})
        assert len(targets)==1,(name,hits,targets)
        target=targets[0];guard=b''
        if kind!='AOBScanBase':
            for instruction in decoder.disasm(pe.get_data(target,48),target):
                guard+=instruction.bytes
                if len(guard)>=24 or instruction.mnemonic in ('ret','jmp','int3'):break
            assert guard
            symbol=f'Exposer{label}_{len(records)}'
            lines.append('inline constexpr unsigned char '+symbol+'[]={'+','.join(hex(v) for v in guard)+'};')
        records.append({'name':name,'kind':kind,'matches':[hex(h) for h in hits],'target':hex(target),'guard':guard.hex()})
    assert len(records)==21,len(records)
    lines.append('inline constexpr ExposerBinding ExposerBindings'+label+'[]={')
    for index,item in enumerate(records):
        symbol=f'Exposer{label}_{index}' if item['guard'] else 'nullptr'
        lines.append('{"'+item['name']+'",'+item['target']+','+symbol+','+str(len(item['guard'])//2)+'},')
    lines.append('};')
    profiles.append({'label':label,'sha256':expected,'records':records})
(root/'game/CompatibilityData.h').write_text('\n'.join(lines)+'\n')
Path(args.report).write_text(json.dumps(profiles,indent=2))
print('PASS: 21 production bindings per EXE; two Hkb caller signatures resolve one common target')
