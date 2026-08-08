from typing import Annotated

from pydantic import BeforeValidator


def _coerce_bool(v):
    if v is None:
        return False
    if isinstance(v, bytes):
        return v == b'\x01'
    return v


BoolField = Annotated[bool, BeforeValidator(_coerce_bool)]
