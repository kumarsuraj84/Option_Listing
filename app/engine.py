"""Pure preview engine. Inputs are snapshots; no dispatch or ERP writes."""
from collections import defaultdict
from decimal import ROUND_FLOOR

from .models import AllocationRequest


def allocate(request: AllocationRequest) -> dict:
    by_option=defaultdict(list)
    pools={}
    for s in request.supply:
        by_option[s.option].append(s)
        holdback=(request.policy.ready_holdback if s.phase=='READY'
                  else request.policy.planned_holdback)
        pools[s.option,s.color]=int((s.quantity*(1-holdback)).to_integral_value(rounding=ROUND_FLOOR))
    opening=pools.copy()
    demand={(d.store,d.demand_group):d.quantity for d in request.demand}
    remaining=demand.copy()
    existing={(x.store,x.option) for x in request.existing_listings}
    rows=[]
    selected=defaultdict(list)

    def minimum(t):
        s=by_option[t.option][0]
        return t.grid_sets*s.pack_size*(2 if s.phase=='READY' else 1)

    # Scarce options first reduces the chance that flexible options consume
    # demand before a scarce option can obtain its first full color allocation.
    # This is a deterministic heuristic, not a global optimization guarantee.
    targets=sorted(request.targets,key=lambda t:(
        0 if by_option[t.option][0].phase=='PLANNED' else 1,
        sum(pools[s.option,s.color]//minimum(t) for s in by_option[t.option]),
        -t.priority,t.option,t.store))

    def give(t, stage):
        need=minimum(t)
        group=by_option[t.option][0].demand_group
        dk=(t.store,group)
        if remaining[dk]<need:
            return False
        used=selected[t.store,t.option]
        colors={x.color for x in used}
        families={x.family for x in used}
        candidates=[]
        for s in by_option[t.option]:
            if s.color in colors or pools[s.option,s.color]<need:
                continue
            if stage=='extra_family' and s.family in families:
                continue
            if stage=='extra_color' and s.family not in families:
                continue
            candidates.append(s)
        if not candidates:
            return False
        s=min(candidates,key=lambda x:(x.rank,-pools[x.option,x.color],x.family,x.color))
        pools[s.option,s.color]-=need
        remaining[dk]-=need
        selected[t.store,t.option].append(s)
        fraction=request.policy.initial_dispatch_fraction
        dispatch=None if fraction is None else int(need*fraction)//s.pack_size*s.pack_size
        rows.append(dict(store=t.store,option=t.option,color=s.color,family=s.family,
                         demand_group=group,phase=s.phase,minimum_quantity=need,
                         assigned_quantity=need,list_tag='YES',stage=stage,
                         initial_dispatch_quantity=dispatch,
                         store_reserve_quantity=None if dispatch is None else need-dispatch))
        return True

    # Complete first-family coverage attempts before allocating any extras.
    for t in targets:
        if (t.store,t.option) not in existing:
            give(t,'coverage')
    for stage, enabled in [('extra_family',request.policy.allow_extra_families),
                            ('extra_color',request.policy.allow_extra_colors_same_family)]:
        if enabled:
            for t in targets:
                if selected[t.store,t.option]:
                    while give(t,stage):
                        pass

    coverage=[]
    for t in sorted(request.targets,key=lambda x:(x.store,x.option)):
        key=(t.store,t.option)
        dk=(t.store,by_option[t.option][0].demand_group)
        if key in existing:
            status='EXISTING_YES';reason='Keep active; replenish through the store reserve ledger'
        elif selected[key]:
            status='COVERED';reason='At least one full color allocation in one family'
        else:
            status='UNCOVERED'
            reason=('INSUFFICIENT_DEMAND' if remaining[dk]<minimum(t)
                    else 'NO_COLOR_WITH_MINIMUM_AVAILABLE')
        coverage.append(dict(store=t.store,option=t.option,status=status,reason=reason,
                             minimum_quantity=minimum(t),
                             family_count=len({s.family for s in selected[key]})))
    # Independent reconciliation against original inputs and emitted rows.
    used=defaultdict(int);used_demand=defaultdict(int)
    for r in rows:
        used[r['option'],r['color']]+=r['assigned_quantity']
        used_demand[r['store'],r['demand_group']]+=r['assigned_quantity']
        assert r['assigned_quantity']>=r['minimum_quantity']
        assert (r['store'],r['option']) not in existing
    for k,v in opening.items():
        assert used[k]+pools[k]==v and used[k]<=v
    for k,v in demand.items():
        assert used_demand[k]+remaining[k]==v and used_demand[k]<=v
    return dict(allocations=rows,coverage=coverage,
                pools=[dict(option=s.option,color=s.color,received=s.quantity,
                            eligible_pool=opening[s.option,s.color],
                            held_back=s.quantity-opening[s.option,s.color],
                            assigned=used[s.option,s.color],unassigned=pools[s.option,s.color])
                       for s in sorted(request.supply,key=lambda x:(x.option,x.color))],
                demand=[dict(store=k[0],demand_group=k[1],opening=v,
                             assigned=used_demand[k],remaining=remaining[k])
                        for k,v in sorted(demand.items())],
                summary=dict(assigned_units=sum(r['assigned_quantity'] for r in rows),
                             covered_targets=sum(c['status']=='COVERED' for c in coverage),
                             uncovered_targets=sum(c['status']=='UNCOVERED' for c in coverage),
                             existing_targets=sum(c['status']=='EXISTING_YES' for c in coverage),
                             split_status='UNSPECIFIED' if request.policy.initial_dispatch_fraction is None else 'PREVIEW',
                             reconciliation='PASS'))
