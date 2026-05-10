from fastapi import Request, HTTPException, status
import db


async def get_current_user(request: Request):
    user_id = request.cookies.get("user_id")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login/"}
        )

    user = await db.get_user_by_id(int(user_id))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login/"}
        )

    return user