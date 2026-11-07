"""Offline regression tests for Gemini image response extraction."""

import base64
import importlib
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

pytestmark = pytest.mark.base


@pytest.fixture
def google(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[3] / "src"))
    return importlib.import_module("artist.providers.google")


def image_part(data=b"generated-image"):
    return {
        "inlineData": {
            "mimeType": "image/png",
            "data": base64.b64encode(data).decode(),
        }
    }


def generate(google, mode, tmp_path):
    output = tmp_path / "generated.png"
    args = ("https://provider.invalid", "test-key", "draw a sprite")
    if mode == "i2i":
        reference = tmp_path / "reference.png"
        reference.write_bytes(b"reference")
        result = google.i2i(*args, [str(reference)], str(output), "test-model")
    else:
        result = google.t2i(*args, str(output), "test-model")
    return result, output


def respond(monkeypatch, google, body, status=200):
    response = Mock(status_code=status, text=json.dumps(body))
    response.json.return_value = body
    post = Mock(return_value=response)
    monkeypatch.setattr(google.requests, "post", post)
    return post


@pytest.mark.parametrize("mode", ["t2i", "i2i"])
@pytest.mark.parametrize("prefix", [
    [], [{"text": "Here is the sprite."}],
    [{"text": "Style"}, {"text": "Result"}],
])
def test_image_after_text(google, monkeypatch, tmp_path, mode, prefix):
    respond(monkeypatch, google, {
        "candidates": [{"content": {"parts": prefix + [image_part()]}}]
    })
    result, output = generate(google, mode, tmp_path)
    assert result.ok, result.error
    assert output.read_bytes() == b"generated-image"


@pytest.mark.parametrize("mode", ["t2i", "i2i"])
def test_first_image_in_first_candidate(google, monkeypatch, tmp_path, mode):
    respond(monkeypatch, google, {"candidates": [
        {"content": {"parts": [image_part(b"first"), image_part(b"second")]}},
        {"content": {"parts": [image_part(b"other-candidate")]}},
    ]})
    result, output = generate(google, mode, tmp_path)
    assert result.ok, result.error
    assert output.read_bytes() == b"first"


@pytest.mark.parametrize("mode", ["t2i", "i2i"])
@pytest.mark.parametrize("body", [
    None, [], {}, {"candidates": []}, {"candidates": None}, {"candidates": [None]},
    {"candidates": [{}]}, {"candidates": [{"content": None}]},
    {"candidates": [{"content": {"parts": None}}]},
    {"candidates": [{"content": {"parts": [{"text": "No image"}]}}]},
    {"candidates": [{"content": {"parts": [{"inlineData": {}}]}}]},
    {"candidates": [{"content": {"parts": [
        {"inlineData": {"mimeType": "image/png", "data": ""}}
    ]}}]},
])
def test_no_image_fails_without_writing(google, monkeypatch, tmp_path, mode, body):
    respond(monkeypatch, google, body)
    result, output = generate(google, mode, tmp_path)
    assert not result.ok
    assert "No image in response" in result.error
    assert not output.exists()


@pytest.mark.parametrize("mode", ["t2i", "i2i"])
def test_skip_invalid_non_image_and_thought_parts(google, monkeypatch, tmp_path, mode):
    thought = {**image_part(b"thought"), "thought": True}
    parts = [
        None, "invalid", {"inlineData": None},
        {"inlineData": {"mimeType": "audio/wav", "data": "YXVkaW8="}},
        thought, image_part(b"final"),
    ]
    respond(monkeypatch, google, {"candidates": [{"content": {"parts": parts}}]})
    result, output = generate(google, mode, tmp_path)
    assert result.ok, result.error
    assert output.read_bytes() == b"final"


@pytest.mark.parametrize("mode", ["t2i", "i2i"])
def test_http_failure(google, monkeypatch, tmp_path, mode):
    respond(monkeypatch, google, {"error": "unavailable"}, status=503)
    result, output = generate(google, mode, tmp_path)
    assert not result.ok
    assert result.error.startswith("503:")
    assert not output.exists()


@pytest.mark.parametrize("mode", ["t2i", "i2i"])
def test_request_failure(google, monkeypatch, tmp_path, mode):
    monkeypatch.setattr(google.requests, "post", Mock(
        side_effect=requests.Timeout("provider timed out")
    ))
    result, output = generate(google, mode, tmp_path)
    assert not result.ok
    assert "provider timed out" in result.error
    assert not output.exists()
