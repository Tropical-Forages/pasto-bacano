"""Tests of the web chat channel (app/api) with a fake harness (offline)."""

from dataclasses import dataclass, field

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.media import MemoryMediaStore, collect_attachments
from app.api.router import build_router
from semente.tools.types import File, Image, Video


@dataclass
class FakeOutput:
    content: str = ""
    images: list = field(default_factory=list)
    files: list = field(default_factory=list)
    videos: list = field(default_factory=list)


class FakeHarness:
    def __init__(self, output=None, error=None):
        self.output = output or FakeOutput(content="Hola")
        self.error = error
        self.calls = []

    def run(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.output


def _client(harness, api_key="", store=None):
    app = FastAPI()
    app.include_router(build_router(harness, media_store=store or MemoryMediaStore(), api_key=api_key))
    return TestClient(app)


def test_health():
    assert _client(FakeHarness()).get("/api/health").json() == {"status": "ok"}


def test_chat_follows_the_website_contract_and_namespaces_the_session():
    harness = FakeHarness()
    response = _client(harness).post("/api/chat", json={"session_id": "abc-123", "message": "hola", "language": "es"})

    assert response.status_code == 200
    assert response.json() == {"reply": "Hola", "attachments": []}
    call = harness.calls[0]
    assert call["user_id"] == call["session_id"] == "web:abc-123"
    assert call["input"] == "hola"
    assert call["session_state"] == {"preferred_language": "es"}


def test_language_is_optional():
    harness = FakeHarness()
    _client(harness).post("/api/chat", json={"session_id": "s1", "message": "hi"})

    assert harness.calls[0]["session_state"] is None


@pytest.mark.parametrize("body", [
    {"session_id": "", "message": "hola"},
    {"session_id": "bad id with spaces", "message": "hola"},
    {"session_id": "s1", "message": ""},
    {"session_id": "s1", "message": "x" * 4001},
    {"session_id": "s1", "message": "   "},
    {"session_id": "s1", "location": {"latitude": 95, "longitude": -72}},
])
def test_invalid_requests_are_rejected(body):
    assert _client(FakeHarness()).post("/api/chat", json=body).status_code == 422


def test_agent_errors_are_not_leaked():
    response = _client(FakeHarness(error=RuntimeError("secret detail"))).post(
        "/api/chat", json={"session_id": "s1", "message": "hola"}
    )

    assert response.status_code == 500
    assert "secret detail" not in response.text


def test_raw_model_errors_become_503_without_details():
    raw = '{\n  "error": {\n    "code": 503,\n    "message": "This model is currently experiencing high demand.",\n    "status": "UNAVAILABLE"\n  }\n}'
    response = _client(FakeHarness(FakeOutput(content=raw))).post("/api/chat", json={"session_id": "s1", "message": "hola"})

    assert response.status_code == 503
    assert "high demand" not in response.text


def test_json_like_answers_that_are_not_errors_pass_through():
    response = _client(FakeHarness(FakeOutput(content='{"area_ha": 12.5}'))).post(
        "/api/chat", json={"session_id": "s1", "message": "hola"}
    )

    assert response.status_code == 200


def test_channels_are_parsed_and_validated():
    from app.main import enabled_channels

    assert enabled_channels("") == ["web"]
    assert enabled_channels("web, WhatsApp") == ["web", "whatsapp"]
    with pytest.raises(ValueError):
        enabled_channels("web,telegram")


def test_api_key_is_enforced_when_configured():
    client = _client(FakeHarness(), api_key="k1")
    body = {"session_id": "s1", "message": "hola"}

    assert client.post("/api/chat", json=body).status_code == 401
    assert client.post("/api/chat", json=body, headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.post("/api/chat", json=body, headers={"Authorization": "Bearer k1"}).status_code == 200


def test_remediation_pauses_become_paragraphs():
    harness = FakeHarness(FakeOutput(content="Perdón. [PAUSE] Nueva respuesta. [PAUSE] ¿Mejor?"))
    reply = _client(harness).post("/api/chat", json={"session_id": "s1", "message": "hola"}).json()["reply"]

    assert reply == "Perdón.\n\nNueva respuesta.\n\n¿Mejor?"


def test_image_bytes_become_a_served_link():
    image = Image(content=b"\x89PNG fake", mime_type="image/png", alt_text="Mapa de biomasa")
    client = _client(FakeHarness(FakeOutput(content="Mapa", images=[image])))

    attachment = client.post("/api/chat", json={"session_id": "s1", "message": "mapa"}).json()["attachments"][0]

    assert attachment["type"] == "image" and attachment["title"] == "Mapa de biomasa"
    media = client.get(attachment["url"].replace("http://testserver", ""))
    assert media.status_code == 200 and media.content == b"\x89PNG fake"
    assert media.headers["content-type"] == "image/png"


def test_existing_https_links_pass_through_and_broken_items_are_skipped():
    class BrokenStore:
        def save(self, item, base_url):
            raise OSError("upload failed")

    output = FakeOutput(images=[Image(url="https://example.org/map.png"), Image(content=b"x", mime_type="image/png")])
    attachments = collect_attachments(output, BrokenStore(), "http://localhost")

    assert [a.url for a in attachments] == ["https://example.org/map.png"]


def test_unknown_media_id_is_404():
    assert _client(FakeHarness()).get("/api/media/nope.png").status_code == 404


def test_files_and_videos_use_the_website_attachment_types():
    output = FakeOutput(
        files=[File(content=b"%PDF-1.4", mime_type="application/pdf", filename="boletin.pdf")],
        videos=[Video(url="https://example.org/biomasa.mp4")],
    )

    attachments = collect_attachments(output, MemoryMediaStore(), "http://localhost")

    assert [(a.type, a.mime_type) for a in attachments] == [("document", "application/pdf"), ("video", "video/mp4")]
    assert attachments[0].title == "boletin.pdf"


def test_a_shared_location_becomes_the_whatsapp_registration_sentence():
    harness = FakeHarness()
    body = {"session_id": "s1", "location": {"latitude": 8.75, "longitude": -75.88}}

    assert _client(harness).post("/api/chat", json=body).status_code == 200
    assert harness.calls[0]["input"] == "I want to register my property at coordinates Lat: 8.75 Long: -75.88."
