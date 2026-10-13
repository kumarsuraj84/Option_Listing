from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Supply(Model):
    option: str = Field(min_length=1)
    color: str = Field(min_length=1)
    family: str = Field(min_length=1)
    demand_group: str = Field(min_length=1)
    phase: Literal['PLANNED', 'READY']
    pack_size: int = Field(gt=0)
    quantity: int = Field(ge=0)
    rank: int = Field(ge=0, default=0)


class Demand(Model):
    store: str = Field(min_length=1)
    demand_group: str = Field(min_length=1)
    quantity: int = Field(ge=0)


class Target(Model):
    store: str = Field(min_length=1)
    option: str = Field(min_length=1)
    grid_sets: int = Field(gt=0)
    priority: int = Field(ge=0, default=0)


class ExistingListing(Model):
    store: str = Field(min_length=1)
    option: str = Field(min_length=1)


class Policy(Model):
    planned_holdback: Decimal = Field(default=Decimal('0.40'), ge=0, le=1)
    ready_holdback: Decimal = Field(default=Decimal('0'), ge=0, le=1)
    initial_dispatch_fraction: Decimal | None = Field(default=None, ge=0, le=1)
    allow_extra_families: bool = False
    allow_extra_colors_same_family: bool = False


class AllocationRequest(Model):
    supply: list[Supply] = Field(min_length=1)
    demand: list[Demand] = Field(min_length=1)
    targets: list[Target] = Field(min_length=1)
    existing_listings: list[ExistingListing] = Field(default_factory=list)
    policy: Policy = Field(default_factory=Policy)

    @model_validator(mode='after')
    def check_keys(self):
        for items, key, label in [
            (self.supply, lambda x:(x.option,x.color), 'supply'),
            (self.demand, lambda x:(x.store,x.demand_group), 'demand'),
            (self.targets, lambda x:(x.store,x.option), 'target'),
            (self.existing_listings, lambda x:(x.store,x.option), 'existing listing'),
        ]:
            keys=[key(x) for x in items]
            if len(keys)!=len(set(keys)):
                raise ValueError(f'Duplicate {label} key; aggregate source rows explicitly')
        options={}
        for s in self.supply:
            identity=(s.demand_group,s.phase,s.pack_size)
            if s.option in options and options[s.option]!=identity:
                raise ValueError('An option must have one demand group, phase and pack size')
            options[s.option]=identity
        demand_keys={(d.store,d.demand_group) for d in self.demand}
        for t in self.targets:
            if t.option not in options:
                raise ValueError(f'Target option has no supply: {t.option}')
            if (t.store,options[t.option][0]) not in demand_keys:
                raise ValueError(f'Target has no demand: {t.store}/{t.option}')
        return self
