"""usage: sv.py <ClassDir> <suffix> [--set=key=val ...] [--content=<type>] — run verify_<suffix>_workbook.py against a scratch copy
(artifact slots cleared, Sensitivity stripped for speed). Prints TOTAL DPS line + status."""
import sys, re, subprocess, openpyxl, os, importlib.util
cls, suffix = sys.argv[1], sys.argv[2]
R='/Users/yaniv/private/MapleStoryIdleOptimizer'
spec=importlib.util.spec_from_file_location('bmod', f'{R}/src/build_{suffix}_workbook.py')
bm=importlib.util.module_from_spec(spec); sys.path.insert(0,f'{R}/src'); spec.loader.exec_module(bm)
wb=openpyxl.load_workbook(f'{R}/{cls}/{cls}-DPS-Calculator.xlsx'); wi=wb['Inputs']
for r in bm.INPUT_ARTIFACT_SLOT_ROWS:
    for c in range(3,13): wi.cell(r,c).value='(none)'
for a in sys.argv[3:]:
    if a.startswith('--set='):
        k,v=a[6:].split('=',1)
        try: v=float(v)
        except ValueError: pass
        if k == 'companion_level':
            _cw=wb['CompanionsInput']
            for _r in range(1,_cw.max_row+1):
                if _cw.cell(_r,1).value in bm.cm.COMPANIONS: _cw.cell(_r,2).value=int(v) if isinstance(v,float) else v
        elif k in ('level','content_type'): wi.cell(bm.IN[k],2).value=v
        else:
            for c in range(3,13): wi.cell(bm.IN[k],c).value=v
for ws_ in wb.worksheets:
    for row_ in ws_.iter_rows():
        for c_ in row_:
            if isinstance(c_.value,str) and c_.value.startswith('=') and 'Sensitivity!' in c_.value: c_.value=0
if 'Sensitivity' in wb.sheetnames: del wb['Sensitivity']
out=f'/tmp/pvp/{suffix}_{os.getpid()}.xlsx'; wb.save(out)
s=open(f'{R}/src/verify_{suffix}_workbook.py').read()
s,n=re.subn(r'XLSX_PATH *=.*', f'XLSX_PATH = Path("{out}")', s, count=1); assert n==1
tmp=f'{R}/src/_tmp_v_{suffix}_{os.getpid()}.py'; open(tmp,'w').write(s)
try: p=subprocess.run([sys.executable,tmp],capture_output=True,text=True,cwd=R)
finally: os.remove(tmp); os.remove(out)
txt=p.stdout+p.stderr
tot=re.search(r'^TOTAL DPS\s+=\s+([0-9.e+]+)', txt, re.M)
ok='All rows match' in txt
mism=[l.split()[0] for l in txt.splitlines() if 'MISMATCH' in l]
tail=[l for l in txt.splitlines() if 'Traceback' in l or 'Error' in l][:3]
extra=' | '.join(l.strip() for l in txt.splitlines() if re.match(r'\s*(Actions/sec|Actions per second|Cast rate|Basic attacks/sec|Basic Attacks/sec)',l))
print(extra)
for _l in txt.splitlines():
    if '[compare Lv10]' in _l: print(_l)
if os.environ.get('DUMPMIS'): print('\n'.join(l for l in txt.splitlines() if 'MISMATCH' in l or 'Traceback' in l))
if os.environ.get('ROWS'): print('\n'.join(l for l in txt.splitlines() if re.match(r'^[A-Z_]+\s+[\d.]+\s+[\d.]+\s+(OK|MISMATCH)',l)))
print(f"{suffix:20s} {' '.join(a for a in sys.argv[3:]):50s} total={tot.group(1) if tot else None} {'OK' if ok else 'FAIL '+str(mism)+str(tail)}")
