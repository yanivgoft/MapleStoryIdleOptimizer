"""usage: CT='Chapter Boss' KEEP=stat,stat CLVL=5 CINC=0 python3 sens_comp.py <ClassDir> <suffix>  — Sensitivity block total vs main sheet re-evaluated at the swept Input's New Value,
artifacts equipped (Bottle of Emotion, Reindeer's Spear star 5), companion Wind Archer enabled."""
import sys, os, importlib.util, numpy as np, openpyxl, formulas
cls, suffix = sys.argv[1], sys.argv[2]
R='/Users/yaniv/private/MapleStoryIdleOptimizer'; sys.path.insert(0, f'{R}/src')
spec=importlib.util.spec_from_file_location('bm', f'{R}/src/build_{suffix}_workbook.py'); bm=importlib.util.module_from_spec(spec); spec.loader.exec_module(bm)
CT=os.environ.get('CT','Chapter Boss'); KEEP=os.environ.get('KEEP','damage,attack_speed').split(',')
ARTS=os.environ.get("ARTS","Bottle of Emotion|Reindeer's Spear").split("|")
ci=3+bm.CONTENT_TYPES.index(CT)
def prep(strip, setinput=None):
    wb=openpyxl.load_workbook(os.environ.get('WB',f'{R}/{cls}/{cls}-DPS-Calculator.xlsx')); wi=wb['Inputs']
    for i,r in enumerate(bm.INPUT_ARTIFACT_SLOT_ROWS):
        for c in range(3,13): wi.cell(r,c).value = ARTS[i] if i<len(ARTS) else '(none)'
    for k,label in bm.ARTIFACT_LABELS.items():
        if label in ARTS: wb['ArtifactsInput'].cell(bm.ARTIFACTS_INPUT_ROW[k],2).value=5
    wi.cell(bm.IN['content_type'],2).value=CT
    if 'companion_choice' in bm.IN:
        _cn=os.environ.get('COMP','Wind Archer'); wi.cell(bm.IN['companion_choice'],ci).value=_cn
        for _r in range(1,wb['CompanionsInput'].max_row+1):
            if wb['CompanionsInput'].cell(_r,1).value in bm.cm.COMPANIONS: wb['CompanionsInput'].cell(_r,2).value=int(os.environ.get('CLVL','5'))
        if os.environ.get('CINC'): wi.cell(bm.IN['companion_summon_time_increase_pct'],ci).value=float(os.environ['CINC'])
    if os.environ.get('SED'): wi.cell(bm.IN['status_effect_damage'],ci).value=float(os.environ['SED'])
    if setinput:
        k,v=setinput; wi.cell(bm.IN[k],ci).value=v
    if strip:
        for w in wb.worksheets:
            for row in w.iter_rows():
                for c in row:
                    if isinstance(c.value,str) and c.value.startswith('=') and 'Sensitivity!' in c.value: c.value=0
        del wb['Sensitivity']
    return wb
def evaluate(wb, tag):
    out=f'/tmp/ha/sc_{suffix}_{tag}_{os.getpid()}.xlsx'; wb.save(out)
    sol=formulas.ExcelModel().loads(out).finish().calculate(); os.remove(out)
    def val(sheet,cell):
        suf=f"{sheet.upper()}'!{cell.upper()}"
        for k,v in sol.items():
            if k.upper().endswith(suf): return np.asarray(v.value).reshape(-1)[0]
    return val
v=evaluate(prep(False),'full')
base=float(v('SUMMARY',f'B{bm.R_TOTAL}')); print(CT,'baseline total',base)
bad=0
for key in KEEP:
    r=bm.SENSITIVITY_ROW_FOR[key]
    new_val=float(v('SENSITIVITY',f'E{r}')); blk_total=float(v('SENSITIVITY',f'G{r}'))
    vm=evaluate(prep(True,(key,new_val)),key)
    main_total=float(vm('SUMMARY',f'B{bm.R_TOTAL}'))
    ratio=blk_total/main_total if main_total else float('nan')
    ok=abs(ratio-1)<1e-6
    bad+=0 if ok else 1
    print(f'  {key:34s} block={blk_total:.6e} main={main_total:.6e} ratio={ratio:.5f} {"OK" if ok else "MISMATCH"}')
print('ALL OK' if not bad else f'{bad} MISMATCHES')
