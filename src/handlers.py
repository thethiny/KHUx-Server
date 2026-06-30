"""
KHUx Private Server — Action handlers for v4.3.1.

Based on decompiled libcocos2dcpp.so (arm64-v8a) analysis.
"""

import logging
import time
from typing import Callable, Optional

from sqlalchemy.orm import Session as DBSession

from .models import User

logger = logging.getLogger(__name__)

handlers: dict[int, Callable] = {}


def register(action_id: int):
    def decorator(fn: Callable):
        handlers[action_id] = fn
        return fn
    return decorator


def dispatch(action_id: int, request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    handler = handlers.get(action_id)
    if handler:
        return handler(request_data, user, db_session)
    return default_handler(action_id, request_data, user, db_session)


def build_ret(user: Optional[User] = None) -> dict:
    """
    v4.3.1 Ret::parse (sub_67EB98) — 16 required fields.
    All booleans must be JSON bool, all numbers must be JSON int,
    serverTime is a Unix timestamp STRING.
    """
    return {
        "isMaintenance": False,
        "sessionTO": False,
        "isNewDayPeriod": 0,
        "versionApp": "1.0.1",
        "versionRes": 0,
        "versionDat": 0,
        "functionFlags": 0,
        "serverTime": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
    }


def build_response(user: Optional[User] = None, **extra) -> dict:
    resp = {"ret": build_ret(user)}
    resp.update(extra)
    return resp


# ---------------------------------------------------------------------------
# Login handlers (v4.3.1 uses /system/login and /khux/login)
# ---------------------------------------------------------------------------
@register(59)  # POST /login
def handle_login(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user,
        login={
            "newcomer": True,
            "tutorial": True,
            "acquirableLoginBonus": False,
            "progression": 0,
        },
    )


# ---------------------------------------------------------------------------
# Default handler
# ---------------------------------------------------------------------------
@register(61)  # POST /tutorial/user/create
def handle_tutorial_user_create(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user,
        tutorial={
            "userTutorialId": 1,
            "progression": 0,
            "name": "",
            "inviteCode": "",
        },
    )


def default_handler(action_id: int, request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    logger.warning("Unhandled action_id=%d request_keys=%s", action_id, list(request_data.keys()))
    return build_response(user)
