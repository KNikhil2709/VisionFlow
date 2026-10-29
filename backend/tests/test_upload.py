import io

from fastapi.testclient import TestClient
from PIL import Image

from visionflow import store
from visionflow.api.app import app
from visionflow.config import settings
from visionflow.cv import service
from visionflow.engine import advance


def test_upload_enters_review_and_resumes(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "cv_backend", "local")
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    settings.uploads_dir.mkdir()
    monkeypatch.setattr(service, "inspect_path", lambda src, stem: {
        "score": 0.5, "heatmap": f"heatmaps/{stem}.png", "backend": "local"})
    image = io.BytesIO()
    Image.new("RGB", (32, 32)).save(image, format="PNG")
    # No lifespan: drive the worker explicitly to test durable handoffs.
    client = TestClient(app)
    response = client.post("/api/inspect", files={"file": ("part.png", image.getvalue())})
    assert response.status_code == 202
    rid = response.json()["run_id"]
    assert rid in store.runnable_run_ids()
    assert advance(rid) == "suspended"
    assert str(store.review_queue()[0]["run_id"]) == rid
    assert client.post(f"/api/runs/{rid}/verdict", json={"verdict": "pass"}).status_code == 200
    assert advance(rid) == "completed"
    assert store.count_verdicts(rid) == 1


def test_invalid_upload_creates_no_run(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "cv_backend", "local")
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    settings.uploads_dir.mkdir()
    response = TestClient(app).post("/api/inspect", files={"file": ("fake.png", b"not an image")})
    assert response.status_code == 400
    assert store.all_run_ids() == []
    assert list(settings.uploads_dir.iterdir()) == []
