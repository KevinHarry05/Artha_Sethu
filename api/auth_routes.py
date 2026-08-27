"""
Auth HTTP layer -- POST /auth/signup, POST /auth/login.

Field names, the /auth prefix, and the {access_token, user} response shape
all match FronteEnd's actual built request exactly (app/page.tsx's Auth
component: `fetch(`${API}/auth/${mode}`, ...)`, `onAuth(data.access_token,
data.user)`). Kept as its own APIRouter, included into the app in
api/main.py.
"""

from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse

from modules.auth import (
    AuthValidationError,
    InvalidCredentialsError,
    UsernameTakenError,
    login as run_login,
    signup as run_signup,
)

router = APIRouter(prefix="/auth")


def _auth_result_to_json(result) -> dict:
    return {
        "access_token": result.access_token,
        "user": {
            "user_id": result.user.user_id,
            "name": result.user.name,
            "age": result.user.age,
            "business_category": result.user.business_category,
            "company_size": result.user.company_size,
        },
    }


@router.post("/signup")
def signup(
    name: str = Form(...),
    age: int = Form(...),
    business_category: str = Form(...),
    company_size: str = Form(...),
    password: str = Form(...),
):
    try:
        result = run_signup(name, age, business_category, company_size, password)
    except AuthValidationError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    except UsernameTakenError as e:
        return JSONResponse(status_code=409, content={"error": str(e)})
    except Exception as e:  # noqa: BLE001 -- e.g. DB unreachable -- clean 400, not a stack trace
        return JSONResponse(status_code=400, content={"error": f"{type(e).__name__}: {e}"})

    return _auth_result_to_json(result)


@router.post("/login")
def login(
    name: str = Form(...),
    password: str = Form(...),
):
    try:
        result = run_login(name, password)
    except InvalidCredentialsError as e:
        return JSONResponse(status_code=401, content={"error": str(e)})
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=400, content={"error": f"{type(e).__name__}: {e}"})

    return _auth_result_to_json(result)
