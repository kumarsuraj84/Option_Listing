import {useState} from 'react';

export const example={
  supply:['A','B','C'].flatMap((option,i)=>['BLACK','WHITE'].map((color,rank)=>({option,color,family:color,demand_group:'G1',phase:'PLANNED',pack_size:12,quantity:[200,180,20][i],rank}))),
  demand:['S1','S2'].map(store=>({store,demand_group:'G1',quantity:36})),
  targets:['S1','S2'].flatMap((store,i)=>['A','B','C'].map(option=>({store,option,grid_sets:1,priority:2-i}))),
  existing_listings:[]
};
type Row={store:string;option:string;color:string;family:string;assigned_quantity:number;initial_dispatch_quantity:number|null;store_reserve_quantity:number|null;stage:string};
type Coverage={store:string;option:string;status:string;reason:string;minimum_quantity:number;family_count:number};
type Result={id:string;result:{allocations:Row[];coverage:Coverage[];summary:{assigned_units:number;covered_targets:number;uncovered_targets:number;existing_targets:number;split_status:string;reconciliation:string}}};

export default function App(){
  const [token,setToken]=useState('');
  const [input,setInput]=useState(JSON.stringify(example,null,2));
  const [holdback,setHoldback]=useState('40');const [readyHoldback,setReadyHoldback]=useState('0');
  const [split,setSplit]=useState('');const [extras,setExtras]=useState(false);const [same,setSame]=useState(false);
  const [busy,setBusy]=useState(false);const [error,setError]=useState('');
  const [result,setResult]=useState<Result|null>(null);const [store,setStore]=useState('');
  const [files,setFiles]=useState<Record<string,File>>({});const [stale,setStale]=useState(false);
  const mark=()=>{if(result)setStale(true)};
  const percent=(value:string,label:string)=>{const n=Number(value);if(value.trim()===''||!Number.isFinite(n)||n<0||n>100)throw Error(label+' must be between 0 and 100');return String(n/100)};
  const policy=()=>({planned_holdback:percent(holdback,'PLANNED holdback'),ready_holdback:percent(readyHoldback,'READY holdback'),initial_dispatch_fraction:split.trim()===''?null:percent(split,'Initial dispatch'),allow_extra_families:extras,allow_extra_colors_same_family:same});
  const call=async(path:string,body:unknown,key?:string)=>{
    if(!token.trim())throw Error('Enter the API access key');
    const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+token,...(key?{'Idempotency-Key':key}:{})},body:JSON.stringify(body)});
    const data=await response.json();
    if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail));
    return data;
  };
  const run=async()=>{setBusy(true);setError('');try{
    const payload=JSON.parse(input);payload.policy=policy();
    const data=await call('/runs',payload,crypto.randomUUID());setResult(data);setStore('');setStale(false);
  }catch(e){setError(e instanceof Error?e.message:String(e))}finally{setBusy(false)}};
  const importFiles=async()=>{setBusy(true);setError('');try{
    for(const name of ['supply','demand','targets'])if(!files[name])throw Error('Select all three CSV files');
    const payload={supply_csv:await files.supply.text(),demand_csv:await files.demand.text(),targets_csv:await files.targets.text(),policy:policy()};
    setInput(JSON.stringify(await call('/imports/validate',payload),null,2));mark();
  }catch(e){setError(e instanceof Error?e.message:String(e))}finally{setBusy(false)}};
  const download=()=>{if(!result)return;const url=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='allocation-preview-'+result.id+'.json';a.click();URL.revokeObjectURL(url)};
  const summary=result?.result.summary;
  const targets=result?.result.coverage.filter(c=>!store||c.store===store)||[];
  return <main>
    <header><div><span className="brand">Option Listing</span><h1>Allocate options before extra colors</h1></div><span className="badge">Preview build</span></header>
    <p className="intro">Cover each selected option with at least one family. Each assigned color must meet its grid and pack minimum.</p>
    <section aria-label="Allocation configuration">
      <h2>Configuration</h2>
      <div className="fields">
        <label>API access key<input type="password" value={token} onChange={e=>setToken(e.target.value)} autoComplete="off"/></label>
        <label>PLANNED holdback (%)<input type="number" min="0" max="100" value={holdback} onChange={e=>{setHoldback(e.target.value);mark()}}/></label>
        <label>READY holdback (%)<input type="number" min="0" max="100" value={readyHoldback} onChange={e=>{setReadyHoldback(e.target.value);mark()}}/></label>
        <label>Initial dispatch (%)<input type="number" min="0" max="100" placeholder="Not yet decided" value={split} onChange={e=>{setSplit(e.target.value);mark()}}/></label>
      </div>
      <div className="checks"><label><input type="checkbox" checked={extras} onChange={e=>{setExtras(e.target.checked);mark()}}/> Allow extra families after coverage</label><label><input type="checkbox" checked={same} onChange={e=>{setSame(e.target.checked);mark()}}/> Allow extra colors in the same family after coverage</label></div>
      <p className="hint">Holdback remains outside the allocation pool. A store reserve is calculated from its assigned quantity only when the dispatch split is specified. Dispatch is rounded down to full packs.</p>
    </section>
    <section><h2>Input snapshot</h2>
      <div className="fields">{['supply','demand','targets'].map(name=><label key={name}>{name[0].toUpperCase()+name.slice(1)} CSV<input type="file" accept=".csv" onChange={e=>{if(e.target.files?.[0])setFiles({...files,[name]:e.target.files[0]})}}/></label>)}</div>
      <div className="actions"><button disabled={busy} onClick={importFiles}>Validate CSV imports</button><button disabled={busy} onClick={()=>{setInput(JSON.stringify(example,null,2));mark()}}>Load scarcity example</button></div>
      <details><summary>Review or edit normalized inputs</summary><label className="editor-label">Input JSON<textarea value={input} onChange={e=>{setInput(e.target.value);mark()}} spellCheck={false}/></label></details>
      <div className="actions"><button className="primary" disabled={busy} onClick={run}>{busy?'Processing…':'Run allocation preview'}</button></div>
      {error&&<p role="alert" className="error">{error}</p>}
    </section>
    {result&&summary&&<section aria-label="Allocation results">
      <div className="result-head"><h2>Allocation preview</h2><button onClick={download}>Download results</button></div>
      {stale&&<p role="status" className="warning">Inputs changed. These results belong to the previous snapshot; run a new preview.</p>}
      <div className="metrics" aria-live="polite"><div><strong>{summary.covered_targets}</strong>Covered store-options</div><div><strong>{summary.uncovered_targets}</strong>Uncovered store-options</div><div><strong>{summary.assigned_units}</strong>Assigned units</div><div><strong>{summary.existing_targets}</strong>Existing YES listings</div></div>
      <div className="result-head"><label>Store<select value={store} onChange={e=>setStore(e.target.value)}><option value="">All stores</option>{[...new Set(result.result.coverage.map(x=>x.store))].sort().map(s=><option key={s}>{s}</option>)}</select></label><span>Quantity reconciliation: {summary.reconciliation}</span></div>
      <div className="table-wrap"><table><thead><tr><th>Store</th><th>Option</th><th>Status</th><th>Color / family</th><th>Minimum</th><th>Assigned</th><th>Initial dispatch</th><th>Store reserve at DC</th></tr></thead><tbody>{targets.map(c=>{
        const rows=result.result.allocations.filter(r=>r.store===c.store&&r.option===c.option);
        return <tr key={c.store+c.option}><td>{c.store}</td><td>{c.option}</td><td><span className={c.status==='UNCOVERED'?'uncovered':'status'}>{c.status.replaceAll('_',' ')}</span><small>{c.reason}</small></td><td>{rows.length?rows.map(r=><div key={r.color}>{r.color} / {r.family}</div>):'—'}</td><td>{c.minimum_quantity}</td><td>{rows.reduce((a,r)=>a+r.assigned_quantity,0)}</td><td>{summary.split_status==='UNSPECIFIED'?'Not set':rows.reduce((a,r)=>a+(r.initial_dispatch_quantity||0),0)}</td><td>{summary.split_status==='UNSPECIFIED'?'Not set':rows.reduce((a,r)=>a+(r.store_reserve_quantity||0),0)}</td></tr>
      })}</tbody></table></div>
      <p className="hint">Existing YES listings receive no new listing allocation. Reserve balances and replenishment transactions will be connected in the next stage. This preview does not dispatch stock.</p>
    </section>}
  </main>;
}
