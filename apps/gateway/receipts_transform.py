from fastapi import APIRouter, HTTPException, Response
from typing import Optional
import json
import hashlib
from pathlib import Path
import os
from libs.odin_core.odin.storage import create_storage_from_env, cache_transform_receipt_get
from libs.odin_core.odin.constants import ENV_DATA_DIR, DEFAULT_DATA_DIR

receipts_transform_router = APIRouter()

def _etag_of_bytes(b: bytes) -> str:
	return hashlib.sha256(b).hexdigest()

@receipts_transform_router.get("/v1/receipts/transform/{out_cid}")
async def get_transform_receipt(out_cid: str):
	"""
	Serve a transform-receipt previously persisted at receipts/transform/<out_cid>.json
	"""
	storage = create_storage_from_env()
	key = f"receipts/transform/{out_cid}.json"
	# Prefer storage first (authoritative), then filesystem mirror, then in-process cache
	data: Optional[bytes] = None
	try:
		data = storage.get_bytes(key)
	except Exception:
		data = None
	if data is None:
		try:
			data_root = Path(os.environ.get(ENV_DATA_DIR, DEFAULT_DATA_DIR))
			p = data_root / "receipts" / "transform" / f"{out_cid}.json"
			if p.exists():
				data = p.read_bytes()
		except Exception:
			data = None
	if data is None:
		data = cache_transform_receipt_get(out_cid)
	if not data:
		raise HTTPException(status_code=404, detail="transform receipt not found")

	etag = _etag_of_bytes(data)
	headers = {
		"ETag": f"\"{etag}\"",
		"Cache-Control": "public, max-age=86400, immutable",
		"Content-Type": "application/json",
		"X-ODIN-Transform-Receipt": key,
	}
	return Response(content=data, headers=headers, media_type="application/json")
