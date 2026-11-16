"""JSON API: content endpoints, GitHub repos, and the contact form."""
from __future__ import annotations

import hashlib
import hmac

from flask import Blueprint, abort, current_app, jsonify, request

from . import content
from .database import count_messages, list_messages, save_message
from .validators import ValidationError, validate_contact

bp = Blueprint("api", __name__, url_prefix="/api")


def _client_hash() -> str:
    """Salted hash of the client IP: enough to rate-limit, no raw IP stored."""
    secret = current_app.config["SECRET_KEY"]
    raw = f"{secret}:{request.remote_addr or 'unknown'}".encode()
    return hashlib.sha256(raw).hexdigest()[:32]


@bp.get("/health")
def health():
    return jsonify(status="ok", messages=count_messages())


@bp.get("/profile")
def profile():
    return jsonify(content.profile_as_dict())


@bp.get("/projects")
def projects():
    tech = request.args.get("tech", "").strip().lower()
    items = [p for p in content.PROJECTS if not tech or tech in (t.lower() for t in p.tech)]
    return jsonify(count=len(items), projects=[p.to_dict() for p in items])


@bp.get("/projects/<slug>")
def project_detail(slug: str):
    project = content.find_project(slug)
    if project is None:
        abort(404, description=f"No project called '{slug}'.")
    return jsonify(project.to_dict())


@bp.get("/skills")
def skills():
    return jsonify(skills=content.skills_as_dict(), used_in_projects=content.tech_frequency())


@bp.get("/github")
def github():
    return jsonify(current_app.extensions["github"].repos())


@bp.post("/contact")
def contact():
    limiter = current_app.extensions["contact_limiter"]
    client = _client_hash()
    if not limiter.allow(client):
        response = jsonify(error="Too Many Requests",
                           message="You have sent a few messages already. Try again later.")
        response.status_code = 429
        response.headers["Retry-After"] = str(limiter.retry_after(client))
        return response

    try:
        data = validate_contact(request.get_json(silent=True))
    except ValidationError as error:
        return jsonify(error="Validation Failed", fields=error.errors), 422

    message_id = save_message(data["name"], data["email"], data["message"], client)
    return jsonify(ok=True, id=message_id, message="Thanks, your message was received."), 201


@bp.get("/messages")
def messages():
    """Read stored messages. Disabled unless ADMIN_TOKEN is configured."""
    token = current_app.config["ADMIN_TOKEN"]
    if not token:
        abort(404)
    supplied = request.headers.get("X-Admin-Token", "")
    if not hmac.compare_digest(supplied.encode(), token.encode()):
        abort(401, description="Missing or invalid admin token.")
    limit = request.args.get("limit", default=50, type=int)
    return jsonify(messages=list_messages(limit))
