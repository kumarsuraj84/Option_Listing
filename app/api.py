import csv
import hashlib
import io
import json
import os
import secrets
from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from sqlalchemy import JSON, Column, DateTime, String, create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Session

from .engine import allocate
from .models import AllocationRequest, Model


class Base(DeclarativeBase):
    pass


class Run(Base):
    __tablename__='allocation_preview_runs'
    id=Column(String(36),primary_key=True)
    key=Column(String(120),nullable=False,unique=True)
    digest=Column(String(64),nullable=False)
    created_at=Column(DateTime(timezone=True),nullable=False)
    request=Column(JSON,nullable=False)
    result=Column(JSON,nullable=False)


class CsvInput(Model):
    supply_csv: str
    demand_csv: str
    targets_csv: str
    policy: dict = {}


def create_app(database_url=None, api_key=None):
    url=database_url or os.getenv('DATABASE_URL','sqlite:///./option_listing_preview.db')
    engine=create_engine(url,connect_args={'check_same_thread':False} if url.startswith('sqlite') else {})
    Base.metadata.create_all(engine)
    expected=api_key if api_key is not None else os.getenv('OPTION_LISTING_API_KEY','')
    app=FastAPI(title='Option Listing Preview API',version='0.1.0')
    app.state.engine=engine

    def auth(authorization: str | None=Header(default=None)):
        if not expected:
            raise HTTPException(503,'Set OPTION_LISTING_API_KEY before using the API')
        if not authorization or not secrets.compare_digest(authorization,'Bearer '+expected):
            raise HTTPException(401,'Invalid bearer token')

    @app.get('/health')
    def health():
        with engine.connect() as conn:
            conn.execute(select(1))
        return {'status':'ok','mode':'preview'}

    @app.post('/imports/validate',dependencies=[Depends(auth)])
    def import_csv(data: CsvInput):
        try:
            payload=AllocationRequest.model_validate(dict(
                supply=list(csv.DictReader(io.StringIO(data.supply_csv))),
                demand=list(csv.DictReader(io.StringIO(data.demand_csv))),
                targets=list(csv.DictReader(io.StringIO(data.targets_csv))),policy=data.policy))
        except (ValidationError,ValueError) as exc:
            raise HTTPException(422,str(exc)) from exc
        return payload.model_dump(mode='json')

    def response(run):
        return dict(id=run.id,created_at=run.created_at.isoformat(),result=run.result)

    @app.post('/runs',dependencies=[Depends(auth)])
    def preview(data: AllocationRequest,idempotency_key: str=Header(min_length=1,max_length=120)):
        body=data.model_dump(mode='json')
        digest=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        with Session(engine) as db:
            previous=db.scalar(select(Run).where(Run.key==idempotency_key))
            if previous:
                if previous.digest!=digest:
                    raise HTTPException(409,'Idempotency key belongs to different inputs')
                return response(previous)
            run=Run(id=str(uuid4()),key=idempotency_key,digest=digest,
                    created_at=datetime.now(timezone.utc),request=body,result=allocate(data))
            db.add(run)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                previous=db.scalar(select(Run).where(Run.key==idempotency_key))
                if previous is None or previous.digest!=digest:
                    raise HTTPException(409,'Idempotency conflict')
                return response(previous)
            return response(run)

    @app.get('/runs/{run_id}',dependencies=[Depends(auth)])
    def get_run(run_id: str):
        with Session(engine) as db:
            run=db.get(Run,run_id)
            if not run:
                raise HTTPException(404,'Run not found')
            return response(run)

    frontend=Path(__file__).resolve().parent.parent/'frontend'/'dist'
    if frontend.is_dir():
        app.mount('/ui',StaticFiles(directory=frontend,html=True),name='ui')
    return app
