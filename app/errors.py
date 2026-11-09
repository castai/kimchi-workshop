"""JSON error handlers for the API.

This module is the single source of truth for HTTP error response
shapes. Routes raise via ``flask.abort``; we respond here. Any path that
builds a response directly (e.g. ``before_request`` short-circuits) is a
contract violation.
"""
from flask import g, jsonify


def register_error_handlers(app):
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "bad_request", "message": str(e)}), 400

    @app.errorhandler(429)
    def too_many(e):
        response = jsonify({"error": "rate_limited", "message": str(e)})
        # The limiter stashes the ceil'd Retry-After value on ``g`` so
        # this handler stays the only place that formats the envelope.
        # ``g`` exposes attributes, not keys, so use ``getattr`` with a
        # default — other 429 paths (e.g. ``abort(429)`` from a route)
        # leave it unset.
        retry_after = getattr(g, "retry_after", None)
        if retry_after is not None:
            response.headers["Retry-After"] = str(retry_after)
        return response, 429

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "not_found", "message": str(e)}), 404

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({"error": "internal_error", "message": str(e)}), 500
