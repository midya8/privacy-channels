import copy
from fractions import Fraction as F
from itertools import product
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from privacylab import audit, postprocess
from privacylab.testing import testing_tradeoff


def channel(rows, edges=None):
    return {'schema_version':1,'secrets':[f's{i}' for i in range(len(rows))],
            'outputs':[f'o{i}' for i in range(len(rows[0]))],
            'neighbors':edges or [[i,i+1]for i in range(len(rows)-1)],
            'probabilities':rows}


def vertex_oracle(p,q,budget):
    """All box-plus-one-constraint LP vertices, no likelihood-ratio ordering."""
    best=F(0)
    n=len(p)
    for bits in product([F(0),F(1)],repeat=n):
        if sum((a*b for a,b in zip(p,bits)),F(0))<=budget:
            best=max(best,sum((a*b for a,b in zip(q,bits)),F(0)))
    for pivot in range(n):
        if p[pivot]==0:continue
        other=[i for i in range(n)if i!=pivot]
        for bits in product([F(0),F(1)],repeat=n-1):
            phi=dict(zip(other,bits))
            f=(budget-sum((p[i]*phi[i]for i in other),F(0)))/p[pivot]
            if 0<=f<=1:best=max(best,q[pivot]*f+sum((q[i]*phi[i]for i in other),F(0)))
    return best


def curve_power(report,alpha):
    for s in report['segments']:
        if F(s['alpha_lower'])<=alpha<=F(s['alpha_upper']):
            return 1-F(s['beta_intercept'])+F(s['slope_magnitude'])*alpha
    raise AssertionError('curve gap')


class TestingTradeoffTests(unittest.TestCase):
    def check(self,r):
        c=r['channel'];p=list(map(F,c['probabilities'][r['null_index']]));q=list(map(F,c['probabilities'][r['alternative_index']]))
        a=F(r['alpha_budget']);phi=list(map(F,r['test']));power=F(r['power'])
        self.assertTrue(all(0<=v<=1 for v in phi));self.assertEqual(sum((v*w for v,w in zip(p,phi)),F(0)),a)
        self.assertEqual(sum((v*w for v,w in zip(q,phi)),F(0)),power);self.assertEqual(F(r['beta']),1-power)
        self.assertEqual(power,vertex_oracle(p,q,a));self.assertEqual(curve_power(r,a),power)
        dual=r['dual'];t=F(dual['threshold']);self.assertGreaterEqual(t,0)
        self.assertEqual(power,t*a+sum((max(b-t*a,F(0))for a,b in zip(p,q)),F(0)))
        self.assertEqual(dual['gap'],'0');self.assertEqual(dual['budget_slack'],'0')
        for i,term in enumerate(dual['terms']):
            self.assertEqual(F(term['dual_coefficient']),q[i]-t*p[i]);self.assertEqual(F(term['dual_positive_part']),max(q[i]-t*p[i],F(0)))
            self.assertEqual(F(term['complementarity_slack']),max(q[i]-t*p[i],F(0))-(q[i]-t*p[i])*phi[i])
            self.assertEqual(term['reject_probability'],str(phi[i]))
        self.assertEqual(r['segments'][0]['alpha_lower'],'0');self.assertEqual(r['segments'][-1]['alpha_upper'],'1')
        prev=None
        for s in r['segments']:
            lo,hi=F(s['alpha_lower']),F(s['alpha_upper']);slope=F(s['slope_magnitude']);intercept=F(s['beta_intercept'])
            self.assertLess(lo,hi)
            for alpha in [lo,(3*lo+hi)/4,(lo+hi)/2,(lo+3*hi)/4,hi]:
                self.assertEqual(1-intercept+slope*alpha,vertex_oracle(p,q,alpha))
            if prev:
                self.assertEqual(prev['alpha_upper'],s['alpha_lower']);self.assertGreaterEqual(F(prev['slope_magnitude']),slope)
            prev=s

    def test_seeded_all_box_constraint_vertices_and_full_curves(self):
        rng=random.Random(491)
        for case in range(24):
            rows=[]
            for _ in range(3):
                values=[rng.randrange(6)for _ in range(4)]
                if not sum(values):values[0]=1
                rows.append([str(F(v,sum(values)))for v in values])
            c=channel(rows)
            for i,j in [(0,1),(1,0),(1,2),(2,1)]:
                self.check(testing_tradeoff(c,i,j,F(case%9,8)))

    def test_randomization_strictly_beats_deterministic_events(self):
        c=channel([['3/4','1/4'],['1/4','3/4']]);r=testing_tradeoff(c,0,1,'1/8');self.check(r)
        self.assertEqual(r['test'],['0','1/2']);self.assertEqual(r['power'],'3/8');self.assertEqual(r['beta'],'5/8')
        p,q=[list(map(F,row))for row in c['probabilities']]
        deterministic=max(sum((q[i]*bits[i]for i in range(2)),F(0))for bits in product([0,1],repeat=2)if sum(p[i]*bits[i]for i in range(2))<=F(1,8))
        self.assertEqual(deterministic,0);self.assertEqual(F(r['power'])-deterministic,F(3,8))

    def test_support_singularities_zero_outputs_and_free_power(self):
        c=channel([['1/2','1/2',0,0],[0,'1/2','1/2',0]])
        for a in [0,'1/8','1/2',1]:self.check(testing_tradeoff(c,0,1,a))
        r=testing_tradeoff(c,0,1,0);self.assertEqual(r['beta'],'1/2');self.assertEqual(r['free_power_outputs'],[2]);self.assertEqual(r['both_zero_outputs'],[3])
        c=channel([[1,0,0],[0,1,0]])
        for a in [0,'1/2',1]:
            r=testing_tradeoff(c,0,1,a);self.check(r);self.assertEqual(r['beta'],'0')

    def test_tie_groups_and_identical_laws(self):
        c=channel([['1/4','1/4','1/2'],['1/8','1/8','3/4']])
        r=testing_tradeoff(c,0,1,'3/4');self.check(r);self.assertEqual(r['test'],['1/2','1/2','1'])
        c=channel([['1/3','2/3',0],['1/3','2/3',0]])
        for a in [0,'1/7',1]:
            r=testing_tradeoff(c,0,1,a);self.check(r);self.assertEqual(r['beta'],str(1-F(a)))

    def test_hockey_stick_duality_at_all_supplied_factors(self):
        c=channel([['1/16','5/16','1/8','1/2'],['5/16','3/8','1/16','1/4']])
        for i,j in [(0,1),(1,0)]:
            r=testing_tradeoff(c,i,j,'1/3')
            for t in [F(1),F(5,4),F(2),F(5),F(100)]:
                dual=max(F(v['power'])-t*F(v['alpha'])for v in r['vertices'])
                reverse=next(p for p in audit(c,t)['pairs']if p['from_index']==j and p['to_index']==i)
                self.assertEqual(dual,F(reverse['delta']))

    def test_stochastic_postprocessing_cannot_increase_testing_power(self):
        rng=random.Random(908)
        for case in range(20):
            rows=[]
            for _ in range(2):
                v=[rng.randrange(1,8)for _ in range(4)];rows.append([str(F(a,sum(v)))for a in v])
            c=channel(rows);kernel=[]
            for _ in range(4):
                a=rng.randrange(9);kernel.append([str(F(a,8)),str(F(8-a,8))])
            transformed=postprocess(c,{'schema_version':1,'input_outputs':c['outputs'],'outputs':['yes','no'],'probabilities':kernel})
            for budget in [F(0),F(1,8),F(1,2),F(7,8),F(1)]:
                original=testing_tradeoff(c,0,1,budget);after=testing_tradeoff(transformed,0,1,budget)
                self.assertLessEqual(F(after['power']),F(original['power']))
                # Pull the postprocessed test back through the supplied kernel.
                phi=[sum(F(k)*F(v)for k,v in zip(row,after['test']))for row in kernel]
                self.assertEqual(sum(F(p)*f for p,f in zip(rows[0],phi)),budget)
                self.assertEqual(sum(F(q)*f for q,f in zip(rows[1],phi)),F(after['power']))

    def test_permutations_reverse_pair_and_omitted_edges(self):
        c=channel([['1/2','1/3','1/6'],['1/4','1/4','1/2'],['1/3','1/3','1/3']])
        r=testing_tradeoff(c,0,1,'1/3');permutation=[2,0,1]
        p=copy.deepcopy(c);p['outputs']=[c['outputs'][i]for i in permutation];p['probabilities']=[[row[i]for i in permutation]for row in c['probabilities']]
        s=testing_tradeoff(p,0,1,'1/3');self.assertEqual(s['power'],r['power']);self.assertEqual(s['test'],[r['test'][i]for i in permutation])
        self.check(testing_tradeoff(c,1,0,'1/3'))
        with self.assertRaises(ValueError):testing_tradeoff(c,0,2,'1/3')

    def test_maximum_domain_tiny_mass_and_large_ratio(self):
        rows=[['1/8']*8,['1/16']*7+['9/16'],['1/4']*4+[0]*4,[0]*4+['1/4']*4]
        c=channel(rows,[[i,j]for i in range(4)for j in range(i+1,4)])
        for a in [0,'1/13',1]:self.check(testing_tradeoff(c,0,1,a))
        tiny=F(1,10**100);c=channel([[tiny,1-tiny],[F(1,2),F(1,2)]])
        r=testing_tradeoff(c,0,1,tiny/2);self.check(r);self.assertEqual(r['power'],'1/4');self.assertEqual(F(r['dual']['threshold']),F(1,2)/tiny)

    def test_strict_inputs_and_isolation(self):
        c=channel([['3/4','1/4'],['1/4','3/4']]);before=copy.deepcopy(c);state=random.getstate();r=testing_tradeoff(c,0,1,'1/8')
        self.assertEqual(c,before);self.assertEqual(random.getstate(),state);r['channel']['probabilities'][0][0]='0';self.assertEqual(c,before)
        for bad in [True,False,-1,'-1','2',.2,'1e-3',' 1/2',F(1,2**513),None]:
            with self.assertRaises(ValueError):testing_tradeoff(c,0,1,bad)
        for i,j in [(True,1),(0,False),(0,0),(-1,1),(0,9),('0',1)]:
            with self.assertRaises(ValueError):testing_tradeoff(c,i,j,0)
        with self.assertRaises(ValueError):testing_tradeoff(channel([['1/9']*9,['1/9']*9]),0,1,0)
        with self.assertRaises(ValueError):testing_tradeoff(channel([[1]]*5),0,1,0)

    def test_cli_full_report_and_malformed_inputs(self):
        c=channel([['3/4','1/4'],['1/4','3/4']]);request={'schema_version':1,'channel':c,'null_index':0,'alternative_index':1,'alpha':'1/8'}
        with tempfile.TemporaryDirectory()as directory:
            path=Path(directory)/'input.json'
            def run(raw):
                path.write_text(raw)
                return subprocess.run([sys.executable,'-m','privacylab','testing',str(path)],capture_output=True,text=True)
            p=run(json.dumps(request));self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(json.loads(p.stdout),testing_tradeoff(c,0,1,'1/8'))
            for raw in [json.dumps({**request,'extra':1}),json.dumps({**request,'null_index':True}),json.dumps({**request,'alpha':.5}),json.dumps(request)[:-1]+',"schema_version":1}','{"x":NaN}','['*2000,' '*100001]:
                p=run(raw);self.assertEqual(p.returncode,2,p.stderr);self.assertEqual(p.stdout,'')

    def test_all_three_output_denominator_three_laws(self):
        laws=[[F(a,3),F(b,3),F(3-a-b,3)]for a in range(4)for b in range(4-a)]
        for p in laws:
            for q in laws:
                c=channel([p,q])
                for alpha in [F(0),F(1,3),F(2,3),F(1)]:
                    r=testing_tradeoff(c,0,1,alpha)
                    self.assertEqual(F(r['power']),vertex_oracle(p,q,alpha))
                    dual=r['dual'];t=F(dual['threshold'])
                    self.assertEqual(F(dual['upper_power']),t*alpha+sum(max(b-t*a,F(0))for a,b in zip(p,q)))
                    self.assertEqual(dual['gap'],'0')

    def test_every_reported_group_vertex_and_term_from_original_laws(self):
        c=channel([['1/4','1/4','1/2',0],['1/8','1/8','1/2','1/4']])
        r=testing_tradeoff(c,0,1,'1/3');p,q=[list(map(F,row))for row in c['probabilities']]
        alpha=F(0);power=sum(q[i]for i in r['free_power_outputs']);self.assertEqual(r['vertices'][0],dict(alpha='0',power=str(power),beta=str(1-power)))
        seen=[]
        for segment,vertex in zip(r['segments'],r['vertices'][1:]):
            group=segment['tie_outputs'];seen+=group;slope=F(segment['slope_magnitude'])
            self.assertTrue(all(p[i]>0 and q[i]/p[i]==slope for i in group))
            mass_p=sum(p[i]for i in group);mass_q=sum(q[i]for i in group)
            self.assertEqual(F(segment['null_mass']),mass_p);self.assertEqual(F(segment['alternative_mass']),mass_q)
            self.assertEqual(F(segment['alpha_lower']),alpha);self.assertEqual(F(segment['beta_intercept']),1-power+slope*alpha)
            alpha+=mass_p;power+=mass_q;self.assertEqual(vertex,dict(alpha=str(alpha),power=str(power),beta=str(1-power)))
        self.assertEqual(sorted(seen),[i for i,a in enumerate(p)if a]);self.assertEqual((alpha,power),(1,1))
        for i,term in enumerate(r['dual']['terms']):
            self.assertEqual(term['output_index'],i);self.assertEqual(F(term['null_probability']),p[i]);self.assertEqual(F(term['alternative_probability']),q[i])
