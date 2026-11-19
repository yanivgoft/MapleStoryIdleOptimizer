import sys, math, time
sys.path.insert(0,'/Users/yaniv/private/MapleStoryIdleOptimizer/src')
import openpyxl, formulas, numpy as np
import status_timeline as st
sys.path.insert(0,'/tmp/tl')
from hosts import make_host
which = sys.argv[1] if len(sys.argv)>1 else 'WB'
h = make_host(which)
items = st.cells(h)
wb = openpyxl.Workbook(); ws = wb.active; ws.title='T'
lay = st.Layout(items, 1, 1)
lay.write(ws)
wb.save('/tmp/tl/strip.xlsx')
t=time.time()
sol = formulas.ExcelModel().loads('/tmp/tl/strip.xlsx').finish().calculate()
print('eval', round(time.time()-t))
def val(addr):
    for k,v in sol.items():
        if k.upper().endswith("T'!"+addr.replace('$','')):
            return np.asarray(v.value).reshape(-1)[0]
py = st.solve(h['py'])
bad=0
def chk(name, a, b):
    global bad
    if abs(a-b) > 1e-6*max(1,abs(b)):
        bad+=1; print('MISMATCH', name, a, b)
for row,phi in py['rows'].items():
    chk('phi.'+row, float(val(lay.s('phi.'+row))), phi)
for row,fs in py['fs'].items(): chk('fs.'+row, float(val(lay.s('fs.'+row))), fs)
chk('phi_unif', float(val(lay.s('phi_unif'))), py['phi_unif'])
chk('Bbuff_mean', float(val(lay.s('Bbuff_mean'))), py['Bbuff_mean'])
for gid,g in py['groups'].items():
    chk('n.'+gid, float(val(lay.s(f'grp.{gid}.n'))), g['n'])
for bid,b in py['buffs'].items():
    chk('nb.'+bid, float(val(lay.s(f'buff.{bid}.n'))), b['n'])
print('mismatches', bad)
