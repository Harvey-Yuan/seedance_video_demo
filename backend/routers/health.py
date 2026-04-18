from fastapi import APIRouter

from ..settings import get_settings

router = APIRouter(tags=["Health"])


@router.get("/health")
def health():
    return {"ok": True, "product_note": get_settings().product_note}
