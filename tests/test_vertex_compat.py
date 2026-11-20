"""Tests of the Vertex AI compatibility patch for Agno's Gemini model (offline)."""

from google.genai import types

from domain.vertex_compat import reorder_function_responses, retype_json_files


def _kinds(content):
    return ["fr" if p.function_response else "txt" if p.text else "bin" for p in content.parts]


def test_function_responses_move_after_images_and_text():
    turn = types.Content(role="user", parts=[
        types.Part.from_function_response(name="register", response={"result": "ok"}),
        types.Part.from_text(text="Take note of the following content"),
        types.Part.from_bytes(data=b"png", mime_type="image/png"),
    ])

    reorder_function_responses([turn])

    assert _kinds(turn) == ["txt", "bin", "fr"]


def test_other_turns_are_unchanged():
    only_results = types.Content(role="user", parts=[
        types.Part.from_function_response(name="a", response={"result": 1}),
        types.Part.from_function_response(name="b", response={"result": 2}),
    ])
    text = types.Content(role="user", parts=[types.Part.from_text(text="hola")])

    reorder_function_responses([only_results, text])

    assert [p.function_response.name for p in only_results.parts] == ["a", "b"]
    assert _kinds(text) == ["txt"]


def test_json_file_parts_are_sent_as_plain_text():
    turn = types.Content(role="user", parts=[
        types.Part.from_text(text="my farm"),
        types.Part.from_bytes(data=b'{"type": "FeatureCollection"}', mime_type="application/json"),
        types.Part.from_bytes(data=b"png", mime_type="image/png"),
    ])

    retype_json_files([turn])

    assert [p.inline_data.mime_type for p in turn.parts[1:]] == ["text/plain", "image/png"]
