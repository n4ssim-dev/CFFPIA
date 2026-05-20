from app.routes import bp


@bp.get("/")
def index():
    return {"status": "ok", "service": "FranceFPIA"}


@bp.get("/health")
def health():
    return {"status": "healthy"}
