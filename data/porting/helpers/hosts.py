def make_host(which):
    T,ko,hexv = {'WB':(75,[(24,34),(59,69)],0),'ENH':(25,[(20.5,25)],10),'CB':(70,[],0)}[which]
    kos = (ko+[(0,0),(0,0)])[:2]
    S = 20 if which!='CB' else 0
    buffs=[dict(id='MED',kind='atk',dur=19.5,cd=30,F=20,on=1),
           dict(id='MG',kind='atk',dur=15,cd=21,F=15,on=1),
           dict(id='INF',kind='ramp',dur=15,dur0=15,cd=30,F=21.7,on=1,p0=15,p1=25,ramp_t=10)]
    groups=[dict(id='METEOR',cd=33,on=1,slot=1,entries=[dict(row='METEOR',typ='burst',w=3000)]),
            dict(id='MIST',cd=24.5,on=1,slot=1,entries=[dict(row='MIST_B',typ='burst',w=800),dict(row='MIST_DOT',typ='dot',w=2000,L=20),dict(row='ERUPT',typ='end',w=3000,L=20)]),
            dict(id='HAZE',cd=25,on=1,slot=1,entries=[dict(row='HAZE_B',typ='burst',w=1000),dict(row='HAZE_DOT',typ='dot',w=2500,L=20)])]
    h=dict(on=1,T=T,S=S,ko=kos,hex_v=hexv,hex_period=20,hex_max=3,A0=10,hex_avg=0,charm_v=5,buffs=buffs,groups=groups,c_slot=20,stun=None)
    py=dict(h); py['ko']=ko
    py['buffs']=[dict(b,on=bool(b['on'])) for b in buffs]; py['groups']=[dict(g,on=bool(g['on']),slot=bool(g['slot'])) for g in groups]
    h['py']=py
    return h

def make_host_pst(which='WB'):
    h = make_host(which)
    # Hero-like Rush: 2.5 s stun every 22 s fixed schedule; a Frostprey-like periodic one
    pst = [dict(id='RUSH', typ='cast', cd=22, dur=2.5, p=1, on=1, t0=0),
           dict(id='FP', typ='periodic', cd=60, dur=1, p=0.1, on=1, t0=3, tick=1.5, win=30)]
    h['pl_stun'] = pst
    h['groups'].append(dict(id='RUSHG', cd=22, on=1, slot=1, fixed=True, t0=0, entries=[dict(row='RUSH', typ='burst', w=1500)]))
    py = h['py']
    py['stun'] = None
    import sys; sys.path.insert(0, '/Users/yaniv/private/MapleStoryIdleOptimizer/src')
    import status_timeline as st
    nb = int(__import__('math').ceil(py['T']))
    py['stun'] = [min(1.0, x) for x in st.pl_stun_vector([dict(r, on=bool(r['on'])) for r in pst], py['T'], nb)]
    py['groups'] = py['groups'] + [dict(id='RUSHG', cd=22, on=True, slot=True, fixed=True, t0=0, entries=[dict(row='RUSH', typ='burst', w=1500)])]
    return h
