// @vitest-environment jsdom
import React from 'react';
import {afterEach,expect,it,vi} from 'vitest';
import {cleanup,render,screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App';

afterEach(()=>{cleanup();vi.unstubAllGlobals()});
it('requires access key before submitting a preview',async()=>{
  const fetch=vi.fn();vi.stubGlobal('fetch',fetch);render(<App/>);
  await userEvent.click(screen.getByRole('button',{name:'Run allocation preview'}));
  expect(screen.getByRole('alert').textContent).toContain('Enter the API access key');
  expect(fetch).not.toHaveBeenCalled();
});
it('submits policies and shows coverage and an unspecified reserve split',async()=>{
  const fetch=vi.fn().mockResolvedValue({ok:true,json:async()=>({id:'run-one',result:{summary:{assigned_units:12,covered_targets:1,uncovered_targets:1,existing_targets:0,split_status:'UNSPECIFIED',reconciliation:'PASS'},allocations:[{store:'S1',option:'A',color:'BLACK',family:'BLACK',assigned_quantity:12,initial_dispatch_quantity:null,store_reserve_quantity:null,stage:'coverage'}],coverage:[{store:'S1',option:'A',status:'COVERED',reason:'Full color',minimum_quantity:12,family_count:1},{store:'S2',option:'A',status:'UNCOVERED',reason:'NO_COLOR_WITH_MINIMUM_AVAILABLE',minimum_quantity:12,family_count:0}]}})});
  vi.stubGlobal('fetch',fetch);render(<App/>);
  await userEvent.type(screen.getByLabelText('API access key'),'test-only');
  await userEvent.click(screen.getByRole('button',{name:'Run allocation preview'}));
  expect(await screen.findByText('BLACK / BLACK')).toBeTruthy();
  expect(screen.getAllByText('Not set').length).toBe(4);
  const [,request]=fetch.mock.calls[0];const body=JSON.parse(request.body);
  expect(body.policy.planned_holdback).toBe('0.4');
  expect(body.policy.initial_dispatch_fraction).toBeNull();
  expect(request.headers['Idempotency-Key']).toBeTruthy();
  await userEvent.selectOptions(screen.getByLabelText('Store'),'S1');
  expect(screen.queryByText('NO_COLOR_WITH_MINIMUM_AVAILABLE')).toBeNull();
  await userEvent.clear(screen.getByLabelText('PLANNED holdback (%)'));
  expect(screen.getByRole('status').textContent).toContain('Inputs changed');
});
it('reports server validation failures',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:false,json:async()=>({detail:'Duplicate target key'})}));
  render(<App/>);await userEvent.type(screen.getByLabelText('API access key'),'test-only');
  await userEvent.click(screen.getByRole('button',{name:'Run allocation preview'}));
  expect((await screen.findByRole('alert')).textContent).toContain('Duplicate target key');
});
