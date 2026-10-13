from copy import deepcopy
from random import Random
from time import perf_counter

import pytest
from pydantic import ValidationError

from app.engine import allocate
from app.models import AllocationRequest


def scenario(stores=2):
    return dict(supply=[dict(option=o,color=c,family=c,demand_group='G1',
                            phase='PLANNED',pack_size=12,quantity=q,rank=i)
                        for o,q in [('A',200),('B',180),('C',20)]
                        for i,c in enumerate(['BLACK','WHITE'])],
                demand=[dict(store=f'S{i}',demand_group='G1',quantity=36) for i in range(stores)],
                targets=[dict(store=f'S{i}',option=o,grid_sets=1,priority=stores-i)
                         for i in range(stores) for o in ['A','B','C']])


def run(data):
    return allocate(AllocationRequest.model_validate(data))


def test_scarce_option_coverage_regression():
    result=run(scenario())
    assert result['summary']['covered_targets']==6
    for store in ['S0','S1']:
        rows=[r for r in result['allocations'] if r['store']==store]
        assert {r['option'] for r in rows}=={'A','B','C'}
        assert sum(r['assigned_quantity'] for r in rows)==36
    assert {r['color'] for r in result['allocations'] if r['option']=='C'}=={'BLACK','WHITE'}


def test_same_family_selects_only_one_color_first():
    d=scenario()
    for s in d['supply']:
        s['family']='WHITE';s['quantity']=200
    r=run(d)
    assert r['summary']['covered_targets']==6
    assert all(c['family_count']==1 for c in r['coverage'])
    assert len(r['allocations'])==6


def test_cannot_combine_two_partial_colors():
    d=scenario()
    for s in d['supply']:
        s['quantity']=10;s['family']='WHITE'
    r=run(d)
    assert not r['allocations']
    assert r['summary']['uncovered_targets']==6


@pytest.mark.parametrize('phase,sets,minimum',[('PLANNED',1,12),('PLANNED',3,36),('READY',1,24),('READY',2,48)])
def test_grade_grid_and_ready_multiplier(phase,sets,minimum):
    d=scenario()
    for s in d['supply']:s.update(phase=phase,quantity=1000)
    for t in d['targets']:t['grid_sets']=sets
    for x in d['demand']:x['quantity']=3*minimum
    r=run(d)
    assert r['summary']['covered_targets']==6
    assert {x['assigned_quantity'] for x in r['allocations']}=={minimum}


def test_holdback_changes_pool_and_reconciles():
    d=scenario();d['policy']={'planned_holdback':'0.75'}
    r=run(d)
    assert all(p['eligible_pool']==p['received']//4 for p in r['pools'])
    assert all(p['eligible_pool']==p['assigned']+p['unassigned'] for p in r['pools'])
    assert all(p['received']==p['held_back']+p['assigned']+p['unassigned'] for p in r['pools'])


def test_existing_yes_not_allocated_again():
    d=scenario();d['existing_listings']=[{'store':'S0','option':'A'}]
    r=run(d)
    assert not any(x['store']=='S0' and x['option']=='A' for x in r['allocations'])
    assert r['summary']['existing_targets']==1


def test_split_is_unknown_by_default_and_pack_safe_when_set():
    d=scenario()
    assert all(x['store_reserve_quantity'] is None for x in run(d)['allocations'])
    for t in d['targets']:t['grid_sets']=2
    for x in d['demand']:x['quantity']=72
    for s in d['supply']:s['quantity']=200
    d['policy']={'initial_dispatch_fraction':'0.5'}
    r=run(d)
    assert all(x['initial_dispatch_quantity']==12 and x['store_reserve_quantity']==12 for x in r['allocations'])


def test_extras_happen_after_coverage():
    d=scenario()
    for s in d['supply']:s['quantity']=1000
    for x in d['demand']:x['quantity']=72
    d['policy']={'allow_extra_families':True}
    r=run(d)
    assert len(r['allocations'])==12
    assert all(x['stage']=='coverage' for x in r['allocations'][:6])
    assert all(x['stage']=='extra_family' for x in r['allocations'][6:])


def test_extra_same_family_requires_explicit_setting():
    d=scenario()
    for s in d['supply']:s.update(family='WHITE',quantity=1000)
    for x in d['demand']:x['quantity']=72
    d['policy']={'allow_extra_families':True}
    assert len(run(d)['allocations'])==6
    d['policy']['allow_extra_colors_same_family']=True
    assert len(run(d)['allocations'])==12


def test_insufficient_demand_never_creates_partial_yes():
    d=scenario()
    for x in d['demand']:x['quantity']=10
    assert not run(d)['allocations']


@pytest.mark.parametrize('mutation',['duplicate_supply','missing_grid','missing_demand','inconsistent_pack'])
def test_invalid_inputs_are_rejected(mutation):
    d=scenario()
    if mutation=='duplicate_supply':d['supply'].append(deepcopy(d['supply'][0]))
    if mutation=='missing_grid':d['targets'][0]['grid_sets']=0
    if mutation=='missing_demand':d['demand']=d['demand'][1:]
    if mutation=='inconsistent_pack':d['supply'][0]['pack_size']=6
    with pytest.raises(ValidationError):run(d)


def test_repeatability_and_input_order_independence():
    d=scenario();r=run(d)
    assert run(d)==r
    for key in ['supply','demand','targets']:d[key].reverse()
    assert run(d)==r


def test_200_stores():
    d=scenario(stores=200)
    for s in d['supply']:s['quantity']=5000
    start=perf_counter();r=run(d);elapsed=perf_counter()-start
    assert r['summary']['covered_targets']==600
    assert r['summary']['assigned_units']==7200
    print(f'200 stores / 600 targets: {elapsed:.4f}s')


def test_randomized_quantity_conservation():
    rng=Random(31)
    for _ in range(100):
        d=scenario(stores=5)
        for s in d['supply']:s['quantity']=rng.randrange(0,250)
        for x in d['demand']:x['quantity']=rng.randrange(0,100)
        for t in d['targets']:t['grid_sets']=rng.randrange(1,4)
        d['policy']={'planned_holdback':str(rng.choice([0,.15,.4,.8,1])),
                     'allow_extra_families':True,'allow_extra_colors_same_family':True}
        r=run(d)
        for p in r['pools']:
            allocated=sum(x['assigned_quantity'] for x in r['allocations'] if (x['option'],x['color'])==(p['option'],p['color']))
            assert p['assigned']==allocated
            assert allocated<=p['eligible_pool']
        for row in r['demand']:
            assert row['assigned']<=row['opening']
        assert all(x['assigned_quantity']>=x['minimum_quantity'] for x in r['allocations'])
