from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.main import app


def test_db_exception_handler_returns_500():
    test_app = FastAPI()
    test_app.router.routes = app.router.routes
    test_app.exception_handlers = app.exception_handlers

    @test_app.get("/_test/db_error")
    async def _db_error():
        raise SQLAlchemyError("db boom")

    client = TestClient(test_app, raise_server_exceptions=False)
    response = client.get("/_test/db_error")
    assert response.status_code == 500
    assert "DBエラーが発生しました" in response.text


def test_unexpected_exception_handler_returns_500():
    test_app = FastAPI()
    test_app.router.routes = app.router.routes
    test_app.exception_handlers = app.exception_handlers

    @test_app.get("/_test/unexpected_error")
    async def _unexpected_error():
        raise RuntimeError("boom")

    client = TestClient(test_app, raise_server_exceptions=False)
    response = client.get("/_test/unexpected_error")
    assert response.status_code == 500
    assert "予期しないエラーが発生しました" in response.text
