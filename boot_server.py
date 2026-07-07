# boot_server.py — crash-proof gunicorn entrypoint (Render: gunicorn boot_server:app)
#
# If importing the real application fails for ANY reason, this module still
# provides a WSGI app, so the process stays alive and the deploy goes live.
# The failure traceback is printed to the service logs and served at
# GET /__boot_error so it can be read from a browser instead of dying as an
# opaque "exited with status 1".

import traceback

_BOOT_TRACEBACK = None

try:
    from wsgi import app  # the real Flask application
except BaseException:  # noqa: BLE001 — anything, including SystemExit
    _BOOT_TRACEBACK = traceback.format_exc()
    print("=== APPLICATION FAILED TO BOOT ===", flush=True)
    print(_BOOT_TRACEBACK, flush=True)

    def app(environ, start_response):  # type: ignore[misc]
        path = environ.get("PATH_INFO", "")
        if path == "/__boot_error":
            body = _BOOT_TRACEBACK.encode("utf-8", errors="replace")
            start_response(
                "200 OK",
                [("Content-Type", "text/plain; charset=utf-8"), ("Content-Length", str(len(body)))],
            )
            return [body]
        body = b'{"error":"boot_failure","detail":"application failed to start","hint":"GET /__boot_error for the traceback"}'
        start_response(
            "503 Service Unavailable",
            [("Content-Type", "application/json"), ("Content-Length", str(len(body)))],
        )
        return [body]
