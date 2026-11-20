"""Nine-month schedule data + dependency check. Weeks 1..36. Owners: A=Arjun, K=Khalid, S=Sumeet."""
import json, re, sys
# task -> (owner, start_week, end_week)
T = {}
def add(owner, wk_start, wk_end, *ids):
    for i in ids: T[i] = (owner, wk_start, wk_end)

# ---- Arjun
add('A',1,1,'A1-03'); add('A',2,2,'A2-01'); add('A',3,3,'A1-04'); add('A',4,4,'A1-05')
add('A',5,5,'A2-02'); add('A',6,6,'A2-03'); add('A',7,7,'A2-05'); add('A',8,8,'A1-16')
add('A',9,9,'A2-06','A2-07'); add('A',10,10,'A2-08','A2-09'); add('A',11,11,'A2-10')
add('A',12,12,'A2-11','A1-29'); add('A',13,13,'A2-13','A1-30'); add('A',14,14,'A2-14')
add('A',14,15,'A1-25'); add('A',15,15,'A2-15')
add('A',24,24,'A2-04','A2-12'); add('A',18,18,'A2-17')
# ---- Khalid
add('K',1,3,'A3-01'); add('K',4,4,'A3-02'); add('K',4,5,'A3-05'); add('K',5,5,'A3-04')
add('K',6,7,'A3-03'); add('K',8,8,'A3-06'); add('K',9,10,'A3-07'); add('K',11,11,'A3-09')
add('K',12,13,'A3-08'); add('K',14,14,'A3-10'); add('K',17,18,'A3-13'); add('K',18,19,'A3-15')
add('K',19,20,'A3-16'); add('K',20,21,'A3-17'); add('K',21,22,'A3-18'); add('K',24,24,'A3-14')
add('K',25,25,'A3-11'); add('K',26,26,'A3-12'); add('K',27,27,'A3-19')
# ---- Sumeet
add('S',1,2,'A1-02'); add('S',1,1,'A1-01'); add('S',2,2,'A1-06'); add('S',3,3,'A1-07')
add('S',4,4,'A1-08','A1-09'); add('S',5,5,'A1-10'); add('S',5,12,'A2-16'); add('S',6,6,'A1-11')
add('S',7,7,'A1-12','A1-13'); add('S',8,8,'A1-14'); add('S',9,9,'A1-15','A1-34')
add('S',10,10,'A1-17','A1-18'); add('S',11,12,'A1-19'); add('S',13,13,'A1-20')
add('S',14,14,'A1-21','A1-22'); add('S',15,15,'A1-23'); add('S',16,16,'A1-24')
add('S',17,17,'A1-26'); add('S',18,18,'A1-27'); add('S',19,19,'A1-28')
add('S',20,20,'A1-31'); add('S',21,21,'A1-32'); add('S',22,22,'A1-33')

DEPS = {  # from planning/IMPLEMENTATION_PLAN.md "Depends on" (B1 tasks only)
 'A1-04':['A1-03'],'A1-05':['A1-03','A2-01'],'A1-06':['A1-02'],'A1-07':['A1-06'],'A1-08':['A1-07'],
 'A1-09':['A1-07'],'A1-10':['A1-08','A1-09'],'A1-11':['A1-07','A1-08','A1-09','A1-10'],
 'A1-12':['A1-11'],'A1-13':['A1-11'],'A1-14':['A1-07','A1-13'],'A1-15':['A1-14'],
 'A1-16':['A1-11','A1-12','A1-13'],'A1-17':['A1-16'],'A1-18':['A1-16'],
 'A1-19':['A1-05','A1-11','A1-13'],'A1-20':['A1-15','A1-19'],'A1-21':['A1-20'],
 'A1-22':['A1-19','A1-20'],'A1-23':['A1-20'],'A1-24':['A1-23','A1-30'],
 'A1-25':['A1-10','A1-13','A1-15','A1-20'],'A1-26':['A1-25'],'A1-27':['A1-15','A1-26'],
 'A1-28':['A1-26','A1-27','A1-29'],'A1-29':['A1-05','A1-14'],'A1-30':['A1-29'],
 'A1-31':['A1-12','A1-13','A1-15'],'A1-32':['A1-26'],'A1-33':['A1-28','A1-29'],'A1-34':['A1-11'],
 'A2-01':['A1-03'],'A2-03':['A2-01','A2-02'],'A2-04':['A2-01'],'A2-05':['A2-01'],'A2-06':['A2-01'],
 'A2-07':['A2-06'],'A2-09':['A2-01','A2-08','A1-05'],'A2-10':['A2-01'],'A2-11':['A2-10','A1-05'],
 'A2-12':['A2-10'],'A2-13':['A2-03','A2-05','A2-06','A2-07','A2-09','A2-10','A2-11'],
 'A2-14':['A2-13','A1-05'],'A2-15':['A2-13','A2-14'],'A2-17':['A2-03','A2-09','A2-16'],
 'A3-01':['A1-04'] ,'A3-02':['A3-01'],'A3-03':['A3-02'],'A3-04':['A3-01'],'A3-05':['A3-01'],
 'A3-06':['A3-02','A3-05'],'A3-07':['A3-06'],'A3-08':['A3-07'],'A3-09':['A3-02'],'A3-10':['A3-05'],
 'A3-11':['A3-04'],'A3-12':['A3-04'],'A3-14':['A3-13'],'A3-15':['A3-13'],'A3-16':['A3-15'],
 'A3-17':['A3-16'],'A3-18':['A3-17'],'A3-19':['A3-03','A3-06','A3-07','A3-08','A3-09','A3-10','A3-11','A3-12','A3-14','A3-15','A3-16','A3-17','A3-18'],
}
# A3-01 scaffolds Vite apps in W1-2 without the client; the client generation needs A1-04 (W3, same week allowed for the last step).
SOFT = {('A3-01','A1-04')}
def check():
    bad=[]
    for t,ds in DEPS.items():
        if t not in T: bad.append(f'{t} not scheduled'); continue
        o,s,e = T[t]
        for d in ds:
            if d not in T: bad.append(f'{t} dep {d} not scheduled'); continue
            do,ds_,de = T[d]
            if (t,d) in SOFT:
                if e < de: bad.append(f'{t}(end {e}) before soft dep {d}(end {de})')
                continue
            ok = (s > de) or (o == do and s >= de)
            if not ok: bad.append(f'{t} starts W{s} but dep {d} ends W{de}')
    return bad
def load():
    L={}
    for t,(o,s,e) in T.items():
        for w in range(s,e+1): L.setdefault((o,w),[]).append(t)
    return L
if __name__=='__main__':
    for b in check(): print('DEP PROBLEM:',b)
    L=load()
    for o in 'AKS':
        print(o,'peak',max(len(v) for (oo,w),v in L.items() if oo==o), 'tasks', sum(1 for t,v in T.items() if v[0]==o))
    allb1=[f'A1-{i:02d}' for i in range(1,35)]+[f'A2-{i:02d}' for i in range(1,18)]+[f'A3-{i:02d}' for i in range(1,20)]
    print('unscheduled B1:',[t for t in allb1 if t not in T])
