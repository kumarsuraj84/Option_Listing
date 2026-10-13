import json
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.api import create_app
from test_engine import scenario


def client(tmp_path,key='test-only'):
    return TestClient(create_app('sqlite:///'+str(tmp_path/'test.db'),api_key=key))


def headers(key='one'):
    return {'Authorization':'Bearer test-only','Idempotency-Key':key}


def test_auth_required(tmp_path):
    c=client(tmp_path)
    assert c.get('/health').status_code==200
    assert c.post('/runs',json=scenario(),headers={'Idempotency-Key':'x'}).status_code==401
    assert client(tmp_path,'').post('/runs',json=scenario(),headers=headers()).status_code==503


def test_persisted_run_and_repeat_key(tmp_path):
    c=client(tmp_path)
    first=c.post('/runs',json=scenario(),headers=headers())
    assert first.status_code==200
    second=c.post('/runs',json=scenario(),headers=headers())
    assert second.json()['id']==first.json()['id']
    other=client(tmp_path)
    saved=other.get('/runs/'+first.json()['id'],headers=headers())
    assert saved.json()['result']==first.json()['result']
    altered=scenario();altered['demand'][0]['quantity']=24
    assert c.post('/runs',json=altered,headers=headers()).status_code==409


def test_concurrent_repeat_key(tmp_path):
    c=client(tmp_path)
    with ThreadPoolExecutor(max_workers=8) as workers:
        responses=list(workers.map(lambda _:c.post('/runs',json=scenario(),headers=headers('parallel')),range(8)))
    assert all(r.status_code==200 for r in responses)
    assert len({r.json()['id'] for r in responses})==1


def test_validation_and_not_found(tmp_path):
    c=client(tmp_path);d=scenario();d['targets'][0]['grid_sets']=0
    assert c.post('/runs',json=d,headers=headers()).status_code==422
    assert c.post('/runs',json=scenario(),headers={'Authorization':'Bearer test-only'}).status_code==422
    assert c.get('/runs/missing',headers=headers()).status_code==404


def test_csv_import(tmp_path):
    import csv,io
    d=scenario();payload={}
    for name in ['supply','demand','targets']:
        buf=io.StringIO();writer=csv.DictWriter(buf,fieldnames=d[name][0].keys())
        writer.writeheader();writer.writerows(d[name]);payload[name+'_csv']=buf.getvalue()
    c=client(tmp_path)
    imported=c.post('/imports/validate',json=payload,headers=headers())
    assert imported.status_code==200
    result=c.post('/runs',json=imported.json(),headers=headers())
    assert result.json()['result']['summary']['covered_targets']==6


def test_openapi_contract(tmp_path):
    schema=client(tmp_path).get('/openapi.json').json()
    assert set(schema['paths'])=={'/health','/imports/validate','/runs','/runs/{run_id}'}
