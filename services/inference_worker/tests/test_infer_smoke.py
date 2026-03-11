def test_infer_endpoint_exists_and_is_not_404(client):
    resp = client.post(
        "/infer",
        json={"prompt": "hello", "max_tokens": 32, "tenant": "demo"},
    )
    assert resp.status_code != 404
