"""Authentication and role-based access control helpers for Vayu Drishti.

Pure functions with no Streamlit rendering calls; only session_state helpers.
All passwords stored strictly as SHA-256 hashes.
"""

import hashlib
import hmac

GUEST_ROLE = "viewer"

# Passwords stored ONLY as SHA-256 hashes. No plaintext passwords exist in code.
DEMO_USERS = {
    "viewer": {
        "role": "viewer",
        "sha256": "d49794b817f022646577e843b9c5cf2d057c2581f5559a686ead84c63259b8f0",
        "password_hash": "d49794b817f022646577e843b9c5cf2d057c2581f5559a686ead84c63259b8f0",
    },
    "maintainer": {
        "role": "maintainer",
        "sha256": "c6d7955c96ed22f04b3d531c53266520d200b5e85e63097fa3f2a7f0603c904c",
        "password_hash": "c6d7955c96ed22f04b3d531c53266520d200b5e85e63097fa3f2a7f0603c904c",
    },
    "admin": {
        "role": "admin",
        "sha256": "0e7f048ed12e1706fa627dc50806ee6184f62b670adaf4f13c13cd7b4b84dfcd",
        "password_hash": "0e7f048ed12e1706fa627dc50806ee6184f62b670adaf4f13c13cd7b4b84dfcd",
    },
}

ALL_PAGES = [
    "Fleet Overview",
    "Aircraft Detail",
    "Digital Twin",
    "Planner",
    "Results",
    "Methodology",
]

PAGES_BY_ROLE = {
    "viewer": [
        "Fleet Overview",
        "Aircraft Detail",
        "Results",
        "Methodology",
    ],
    "maintainer": [
        "Fleet Overview",
        "Aircraft Detail",
        "Results",
        "Methodology",
        "Digital Twin",
        "Planner",
    ],
    "admin": list(ALL_PAGES),
}


def verify(username: str | None, password: str | None) -> str | None:
    """Verify username and password against DEMO_USERS using constant-time comparison.

    Returns the user's role if credentials are valid, else None.
    """
    if not username or not password:
        return None
    user_info = DEMO_USERS.get(username)
    if not user_info:
        return None
    pw_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    stored_hash = user_info["sha256"]
    if hmac.compare_digest(pw_hash, stored_hash):
        return user_info["role"]
    return None


def allowed_pages(role: str | None) -> list:
    """Return the list of allowed pages for a given role."""
    if not role or role not in PAGES_BY_ROLE:
        return []
    return list(PAGES_BY_ROLE[role])


def check_access(page_name: str) -> bool:
    """Check whether the current session is authorized to view page_name."""
    try:
        import streamlit as st
        from streamlit.runtime.scriptrunner_utils.script_run_context import get_script_run_ctx

        # When executed offline outside Streamlit runtime (e.g. pure Python module imports), do not block
        if get_script_run_ctx() is None:
            return True

        user = st.session_state.get("auth_user") or st.session_state.get("authenticated_user")
        if not user:
            return False

        role = st.session_state.get("role") or st.session_state.get("authenticated_role") or GUEST_ROLE
        return page_name in allowed_pages(role)
    except Exception:
        return False


def get_current_user() -> str | None:
    """Return the currently authenticated username from session_state, or None."""
    try:
        import streamlit as st

        return st.session_state.get("auth_user") or st.session_state.get("authenticated_user", None)
    except Exception:
        return None


def get_current_role() -> str:
    """Return the currently active role from session_state, defaulting to GUEST_ROLE."""
    try:
        import streamlit as st

        return st.session_state.get("role") or st.session_state.get("authenticated_role", GUEST_ROLE)
    except Exception:
        return GUEST_ROLE


def set_current_user(username: str | None, role: str | None = None, session_state=None) -> None:
    """Set the authenticated user and role in session_state."""
    try:
        import streamlit as st

        resolved_role = role if role is not None else DEMO_USERS.get(username, {}).get("role", GUEST_ROLE)
        target = session_state if session_state is not None else st.session_state
        target["auth_user"] = username
        target["role"] = resolved_role
        target["authenticated_user"] = username
        target["authenticated_role"] = resolved_role
    except Exception:
        pass


def logout() -> None:
    """Clear the authenticated user and role from session_state."""
    try:
        import streamlit as st

        st.session_state.pop("auth_user", None)
        st.session_state.pop("role", None)
        st.session_state.pop("authenticated_user", None)
        st.session_state.pop("authenticated_role", None)
    except Exception:
        pass
