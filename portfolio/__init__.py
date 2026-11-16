"""Praneeth's portfolio: a small Flask application."""
from __future__ import annotations

from typing import Any

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from .api import bp as api_bp
from .config import load_config
from .database import close_db, init_db
from .services.github import GitHubService
from .services.ratelimit import SlidingWindowLimiter
from .web import bp as web_bp

CSP = "; ".join([
    "default-src 'self'",
    "style-src 'self' https://fonts.googleapis.com",
    "font-src https://fonts.gstatic.com",
    "img-src 'self' data:",
    "script-src 'self'",
    "connect-src 'self'",
    "base-uri 'none'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])


def create_app(overrides: dict[str, Any] | None = None) -> Flask:
    """Application factory: builds and wires up the Flask app."""
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.update(load_config(overrides))

    if app.config.get("TRUST_PROXY"):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)  # type: ignore[method-assign]

    init_db(app)
    app.teardown_appcontext(close_db)

    app.extensions["github"] = GitHubService(
        app.config["GITHUB_USER"],
        ttl=app.config["GITHUB_CACHE_SECONDS"],
        timeout=app.config["GITHUB_TIMEOUT_SECONDS"],
    )
    app.extensions["contact_limiter"] = SlidingWindowLimiter(
        app.config["CONTACT_LIMIT_PER_HOUR"], window=3600.0
    )

    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp)
    _register_hooks(app)
    _register_cli(app)
    return app


def _register_hooks(app: Flask) -> None:
    @app.after_request
    def security_headers(response):
        response.headers.setdefault("Content-Security-Policy", CSP)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        if request.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):
        if request.path.startswith("/api/"):
            return jsonify(error=error.name, message=error.description), error.code
        if error.code == 404:
            return render_template("404.html"), 404
        return error

    @app.errorhandler(Exception)
    def handle_unexpected(error: Exception):
        app.logger.exception("Unhandled error: %s", error)
        if request.path.startswith("/api/"):
            return jsonify(error="Internal Server Error", message="Something went wrong."), 500
        return render_template("404.html", server_error=True), 500


def _register_cli(app: Flask) -> None:
    import click

    from .database import list_messages

    @app.cli.command("messages")
    @click.option("--limit", default=20, show_default=True)
    def show_messages(limit: int) -> None:
        """Print the latest contact messages."""
        rows = list_messages(limit)
        if not rows:
            click.echo("No messages yet.")
        for row in rows:
            click.echo(f"#{row['id']} {row['created_at']}  {row['name']} <{row['email']}>")
            click.echo(f"    {row['message']}\n")
