# ---------------------------------------------------------------------------
# Status / shape
# ---------------------------------------------------------------------------


def test_infer_returns_200(client):
    resp = client.post(
        "/infer", json={"prompt": "What is RAG?", "max_tokens": 32, "tenant": "demo"}
    )
    assert resp.status_code == 200


def test_infer_response_fields_present(client):
    resp = client.post("/infer", json={"prompt": "Hello world"})
    body = resp.json()
    assert set(body.keys()) >= {"text", "tokens", "batch_size", "served_ms", "source"}


def test_source_is_always_inference(client):
    resp = client.post("/infer", json={"prompt": "test"})
    assert resp.json()["source"] == "inference"


def test_infer_defaults_are_accepted(client):
    # Minimal payload — tenant and max_tokens use server defaults.
    resp = client.post("/infer", json={"prompt": "test"})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Token count — formula: min(max_tokens, max(1, len(prompt.split()) * 2))
# ---------------------------------------------------------------------------


def test_token_count_follows_word_formula(client):
    # "hello world foo bar" → 4 words → min(256, max(1, 4*2)) = 8
    resp = client.post("/infer", json={"prompt": "hello world foo bar", "max_tokens": 256})
    assert resp.json()["tokens"] == 8


def test_token_count_capped_by_max_tokens(client):
    # 20 words → formula gives 40; max_tokens=10 caps it
    prompt = " ".join(["word"] * 20)
    resp = client.post("/infer", json={"prompt": prompt, "max_tokens": 10})
    assert resp.json()["tokens"] == 10


def test_token_count_floor_is_one_for_empty_prompt(client):
    # Empty string splits to 0 words → max(1, 0) = 1
    resp = client.post("/infer", json={"prompt": ""})
    assert resp.json()["tokens"] == 1


# ---------------------------------------------------------------------------
# Text — formula: f"[simulated] {prompt[:80]}"
# ---------------------------------------------------------------------------


def test_text_has_simulated_prefix(client):
    resp = client.post("/infer", json={"prompt": "hello"})
    assert resp.json()["text"].startswith("[simulated] ")


def test_text_truncated_at_80_chars(client):
    long_prompt = "a" * 120
    resp = client.post("/infer", json={"prompt": long_prompt})
    assert resp.json()["text"] == f"[simulated] {'a' * 80}"


def test_text_not_truncated_when_prompt_under_80_chars(client):
    short_prompt = "short"
    resp = client.post("/infer", json={"prompt": short_prompt})
    assert resp.json()["text"] == f"[simulated] {short_prompt}"


# ---------------------------------------------------------------------------
# Batch size and latency
# ---------------------------------------------------------------------------


def test_batch_size_is_one_for_sequential_requests(client):
    # Sequential TestClient calls arrive one at a time; the batch window
    # (BATCH_TIMEOUT_MS) expires before a second item joins, so batch_size == 1.
    resp = client.post("/infer", json={"prompt": "test"})
    assert resp.json()["batch_size"] == 1


def test_served_ms_is_non_negative_float(client):
    resp = client.post("/infer", json={"prompt": "test"})
    body = resp.json()
    assert isinstance(body["served_ms"], float)
    assert body["served_ms"] >= 0.0


def test_served_ms_is_rounded_to_two_decimal_places(client):
    resp = client.post("/infer", json={"prompt": "test"})
    served = resp.json()["served_ms"]
    assert served == round(served, 2)
