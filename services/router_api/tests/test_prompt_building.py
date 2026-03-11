from app.main import _build_prompt


def test_build_prompt_without_context():
    prompt = _build_prompt("What is RAG?", [])
    assert "USER: What is RAG?" in prompt
    assert "CONTEXT:" not in prompt


def test_build_prompt_with_context():
    chunks = [{"text": "RAG combines retrieval with generation."}]
    prompt = _build_prompt("Explain it", chunks)
    assert "CONTEXT:" in prompt
    assert "RAG combines retrieval with generation." in prompt
    assert "USER: Explain it" in prompt
