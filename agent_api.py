"""Operator-only write API. Public chat may propose, never persist knowledge."""
import hmac
import sqlite3
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from agent_store import admin_key, get_store
from timo_motion_config import get_shared_map, set_shared_map

router = APIRouter(prefix="/api/agent")


def require_manager(request: Request):
    token = request.headers.get("X-Agent-Key", "")
    if not hmac.compare_digest(token.encode("utf-8"), admin_key().encode("utf-8")):
        raise HTTPException(401, "کلید مدیر صحیح نیست.")
    origin = request.headers.get("Origin")
    if origin and urlsplit(origin).netloc != request.headers.get("host"):
        raise HTTPException(403, "درخواست باید از همین سرور ارسال شود.")


class Record(BaseModel):
    data: dict


class Confirmation(BaseModel):
    proposal_id: str = Field(min_length=10, max_length=128)
    session_id: str = Field(min_length=1, max_length=128)


def apply_write(callback):
    try:
        return {"status": "ok", "id": callback()}
    except (ValueError, sqlite3.IntegrityError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/state", dependencies=[Depends(require_manager)])
def state():
    store = get_store()
    return {**{table: store.rows(table) for table in ("memories", "rooms", "skills")},
            "motion_config": get_shared_map(store)}


@router.get("/motion-config")
def motion_config(response: Response):
    response.headers["Cache-Control"] = "no-store"
    return get_shared_map(get_store())


@router.post("/motion-config", dependencies=[Depends(require_manager)])
def update_motion_config(record: Record):
    try:
        return set_shared_map(get_store(), record.data)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/confirm-memory", dependencies=[Depends(require_manager)])
def confirm(data: Confirmation):
    return apply_write(lambda: get_store().confirm_memory(data.proposal_id, data.session_id))


@router.post("/{table}", dependencies=[Depends(require_manager)])
def create(table: str, record: Record):
    methods = {"memories": "save_memory", "rooms": "save_room", "skills": "save_skill"}
    if table not in methods:
        raise HTTPException(404, "نوع مورد پیدا نشد.")
    return apply_write(lambda: getattr(get_store(), methods[table])(record.data))


@router.put("/{table}/{item_id}", dependencies=[Depends(require_manager)])
def update(table: str, item_id: int, record: Record):
    methods = {"memories": "save_memory", "rooms": "save_room", "skills": "save_skill"}
    if table not in methods:
        raise HTTPException(404, "نوع مورد پیدا نشد.")
    return apply_write(lambda: getattr(get_store(), methods[table])(record.data, item_id))


@router.delete("/{table}/{item_id}", dependencies=[Depends(require_manager)])
def delete(table: str, item_id: int):
    return apply_write(lambda: get_store().delete(table, item_id))
