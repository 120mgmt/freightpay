# extensions/jwt.py — not used by default startup; app.py uses jwt_config.init_jwt(app)

from flask_jwt_extended import JWTManager

jwt = JWTManager()


def init_jwt(app):
    """
    Attach JWTManager to Flask app.
    Required for @jwt_required(), create_access_token, etc.
    """
    jwt.init_app(app)

    # Optional hardening hooks (safe defaults)
    @jwt.unauthorized_loader
    def unauthorized_callback(reason):
        return {"error": "AUTH_REQUIRED", "reason": reason}, 401

    @jwt.invalid_token_loader
    def invalid_token_callback(reason):
        return {"error": "INVALID_TOKEN", "reason": reason}, 401

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return {"error": "TOKEN_EXPIRED"}, 401
