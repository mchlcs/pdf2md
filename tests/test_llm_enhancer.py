"""
Testes para core/llm_enhancer.py.
Todos os testes são mockados — nenhum requer Ollama ou API key real.
"""
import json
from unittest.mock import MagicMock, patch

from core.llm_enhancer import disponivel, melhorar_markdown, ocr_com_visao

# ── Helper: mock de resposta HTTP ────────────────────────────────────────────

def _mock_response(conteudo: str) -> MagicMock:
    """Cria mock de urllib response que retorna JSON compatível com OpenAI."""
    body = json.dumps({
        "choices": [{"message": {"content": conteudo}}]
    }).encode("utf-8")
    resp = MagicMock()
    resp.read.return_value = body
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


# ── disponivel() ─────────────────────────────────────────────────────────────

def test_disponivel_false_sem_env():
    """Retorna False quando PDF2MD_LLM_URL não está definido (default Ollama)."""
    disponivel.cache_clear()
    with patch.dict("os.environ", {}, clear=False):
        # Remove variável se existir
        import os
        os.environ.pop("PDF2MD_LLM_URL", None)
        assert disponivel() is False
    disponivel.cache_clear()


def test_disponivel_true_quando_endpoint_responde():
    """Retorna True quando endpoint acessível."""
    disponivel.cache_clear()
    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    with (
        patch.dict("os.environ", {"PDF2MD_LLM_URL": "http://localhost:11434/v1"}),
        patch("urllib.request.urlopen", return_value=mock_resp),
    ):
        assert disponivel() is True
    disponivel.cache_clear()


def test_disponivel_false_quando_endpoint_inacessivel():
    """Retorna False quando conexão recusada."""
    disponivel.cache_clear()
    with (
        patch.dict("os.environ", {"PDF2MD_LLM_URL": "http://localhost:19999/v1"}),
        patch("urllib.request.urlopen", side_effect=OSError("Connection refused")),
    ):
        assert disponivel() is False
    disponivel.cache_clear()


# ── melhorar_markdown() ───────────────────────────────────────────────────────

def test_melhorar_markdown_retorna_texto_melhorado(tmp_path):
    """Retorna texto do LLM quando chamada bem-sucedida."""
    f = tmp_path / "doc.pdf"
    f.write_bytes(b"x")
    md_original = "pala­vra quebrada e integraÃ§Ã£o"
    md_esperado = "palavra quebrada e integração"

    with patch("urllib.request.urlopen", return_value=_mock_response(md_esperado)):
        resultado, avisos = melhorar_markdown(md_original, f)

    assert resultado == md_esperado
    assert avisos == []


def test_melhorar_markdown_retorna_original_em_falha(tmp_path):
    """Retorna markdown original + aviso quando LLM falha."""
    f = tmp_path / "doc.pdf"
    f.write_bytes(b"x")
    md_original = "texto com problema"

    with patch("urllib.request.urlopen", side_effect=OSError("Connection refused")):
        resultado, avisos = melhorar_markdown(md_original, f)

    assert resultado == md_original  # original preservado
    assert len(avisos) == 1
    assert "falhou" in avisos[0].lower()


def test_melhorar_markdown_trunca_input_longo(tmp_path):
    """Input longo (>12000 chars) é truncado antes de enviar ao LLM."""
    f = tmp_path / "grande.pdf"
    f.write_bytes(b"x")
    md_longo = "palavra " * 5000  # ~40000 chars

    chamadas = []

    def capturar_urlopen(req, timeout=None):
        chamadas.append(req.data)
        return _mock_response("resultado")

    with patch("urllib.request.urlopen", side_effect=capturar_urlopen):
        melhorar_markdown(md_longo, f)

    # Verifica que o payload enviado é menor que o original
    assert len(chamadas) == 1
    payload_str = chamadas[0].decode("utf-8")
    assert len(payload_str) < len(md_longo)


def test_melhorar_markdown_junta_restante_apos_truncamento(tmp_path):
    """Tail do documento (>12000 chars) é preservada no output."""
    f = tmp_path / "doc.pdf"
    f.write_bytes(b"x")
    cabeca = "início " * 2000    # ~14000 chars (acima do threshold)
    cauda = "\n\nFim importante"
    md_longo = cabeca + cauda

    with patch("urllib.request.urlopen", return_value=_mock_response("cabeça melhorada")):
        resultado, _ = melhorar_markdown(md_longo, f)

    assert "Fim importante" in resultado  # cauda preservada


# ── ocr_com_visao() ───────────────────────────────────────────────────────────

def test_ocr_com_visao_retorna_texto(tmp_path):
    """Retorna transcrição do LLM para imagem válida."""
    img = tmp_path / "scan.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 100)  # PNG fake válido

    with patch("urllib.request.urlopen", return_value=_mock_response("# Título\n\nTexto transcrito.")):
        resultado, avisos = ocr_com_visao(img)

    assert "Título" in resultado
    assert avisos == []


def test_ocr_com_visao_retorna_vazio_em_falha(tmp_path):
    """Retorna string vazia + aviso quando LLM falha."""
    img = tmp_path / "scan.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 100)

    with patch("urllib.request.urlopen", side_effect=OSError("timeout")):
        resultado, avisos = ocr_com_visao(img)

    assert resultado == ""
    assert len(avisos) == 1
    assert "falhou" in avisos[0].lower()


def test_ocr_com_visao_arquivo_inexistente(tmp_path):
    """Retorna vazio + aviso para arquivo inexistente (sem chamar LLM)."""
    resultado, avisos = ocr_com_visao(tmp_path / "nao_existe.png")

    assert resultado == ""
    assert len(avisos) == 1
    assert "não encontrada" in avisos[0].lower()


def test_ocr_com_visao_encoda_imagem_em_base64(tmp_path):
    """Imagem é codificada como base64 no payload."""
    img = tmp_path / "scan.png"
    conteudo = b"\x89PNG\r\n\x1a\n" + b"DADOS_IMAGEM" * 10
    img.write_bytes(conteudo)

    payloads = []

    def capturar(req, timeout=None):
        payloads.append(req.data.decode("utf-8"))
        return _mock_response("texto")

    with patch("urllib.request.urlopen", side_effect=capturar):
        ocr_com_visao(img)

    import base64
    b64_esperado = base64.standard_b64encode(conteudo).decode("ascii")
    assert b64_esperado in payloads[0]
