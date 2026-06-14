from fastapi import FastAPI

app = FastAPI(title="运营商统一智能体平台")


def create_app() -> FastAPI:
    from app.api.chat import router
    app.include_router(router)
    return app


create_app()
