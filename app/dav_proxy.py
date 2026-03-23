"""Reverse proxy for /dav/ requests to the Radicale CalDAV server.

This lets the Flask app forward all WebDAV traffic to Radicale so that
nginx doesn't need a separate location block — deploy is just
docker compose up.
"""

import os
import requests as req
from flask import Blueprint, request, Response

dav = Blueprint("dav", __name__)

RADICALE_URL = os.environ.get("RADICALE_URL", "http://radicale:5232")

PASSTHROUGH_METHODS = [
    "GET", "HEAD", "POST", "PUT", "DELETE", "OPTIONS",
    "PROPFIND", "PROPPATCH", "MKCOL", "COPY", "MOVE",
    "LOCK", "UNLOCK", "REPORT", "MKCALENDAR",
]

HOP_BY_HOP = frozenset([
    "connection", "keep-alive", "proxy-authenticate",
    "proxy-authorization", "te", "trailers",
    "transfer-encoding", "upgrade", "content-encoding",
    "content-length",
])


@dav.route("/", defaults={"path": ""}, methods=PASSTHROUGH_METHODS)
@dav.route("/<path:path>", methods=PASSTHROUGH_METHODS)
def proxy(path):
    target = f"{RADICALE_URL}/{path}"
    headers = {k: v for k, v in request.headers if k.lower() not in ("host",)}

    resp = req.request(
        method=request.method,
        url=target,
        headers=headers,
        data=request.get_data(),
        allow_redirects=False,
        stream=True,
    )

    out_headers = {
        k: v for k, v in resp.headers.items()
        if k.lower() not in HOP_BY_HOP
    }

    return Response(
        resp.iter_content(chunk_size=4096),
        status=resp.status_code,
        headers=out_headers,
    )
