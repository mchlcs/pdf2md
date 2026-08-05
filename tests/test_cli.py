"""
Testes para core/cli.py — comando converter via CliRunner.
"""

import json
import re
from unittest.mock import patch

from typer.testing import CliRunner

from core.cli import app

runner = CliRunner()

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _sem_ansi(texto: str) -> str:
    """Remove códigos ANSI do output do Rich para asserções de substring."""
    return _ANSI_RE.sub("", texto)


def test_cli_help():
    """--help mostra usage e opções."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "pdf2md" in result.stdout.lower() or "convert" in result.stdout.lower()


def test_cli_converter_ajuda():
    """converter --help mostra opções do comando."""
    result = runner.invoke(app, ["converter", "--help"])
    assert result.exit_code == 0
    assert "--ignorar-margens" in _sem_ansi(result.stdout)


def test_cli_path_traversal_rejeitado(tmp_path):
    """Path traversal no argumento de origem é rejeitado."""
    result = runner.invoke(app, ["converter", "../../etc/passwd", str(tmp_path)])
    assert result.exit_code != 0


def test_cli_origem_inexistente(tmp_path):
    """Origem não existente retorna erro."""
    result = runner.invoke(app, ["converter", str(tmp_path / "nao_existe.pdf"), str(tmp_path)])
    assert result.exit_code != 0


# ── _requer_ocr ──────────────────────────────────────────────────────────────

def test_requer_ocr_arquivo_pdf(tmp_path):
    """PDF requer OCR (potencialmente escaneado)."""
    from core.cli import _requer_ocr
    arq = tmp_path / "documento.pdf"
    arq.write_bytes(b"%PDF dummy")
    assert _requer_ocr(arq) is True


def test_requer_ocr_arquivo_docx(tmp_path):
    """DOCX não requer OCR."""
    from core.cli import _requer_ocr
    arq = tmp_path / "documento.docx"
    arq.write_text("dummy")
    assert _requer_ocr(arq) is False


def test_requer_ocr_diretorio_com_pdf(tmp_path):
    """Diretório com PDF requer OCR."""
    from core.cli import _requer_ocr
    (tmp_path / "arquivo.pdf").write_bytes(b"%PDF dummy")
    assert _requer_ocr(tmp_path) is True


def test_requer_ocr_diretorio_somente_docx(tmp_path):
    """Diretório só com DOCX não requer OCR."""
    from core.cli import _requer_ocr
    (tmp_path / "arquivo.docx").write_text("dummy")
    assert _requer_ocr(tmp_path) is False


# ── Flags LLM (T8): propagação flag > env > default ─────────────────────────

def test_cli_converter_flags_llm_propagadas(tmp_path):
    """--llm-url e --llm-modelo chegam ao batch_convert."""
    origem = tmp_path / "documento.docx"
    origem.write_text("dummy")  # docx → sem checagem de Tesseract

    with (
        patch("core.batch.batch_convert", return_value=[]) as batch_mock,
        patch("core.cli.Progress"),
    ):
        result = runner.invoke(app, [
            "converter", str(origem), str(tmp_path),
            "--llm-url", "http://localhost:11434/v1",
            "--llm-modelo", "llama3.2-vision",
        ])

    assert result.exit_code == 0
    chamada = batch_mock.call_args
    assert chamada.kwargs["llm_url"] == "http://localhost:11434/v1"
    assert chamada.kwargs["llm_modelo"] == "llama3.2-vision"


def test_cli_converter_sem_flags_llm_passa_none(tmp_path):
    """Sem flags → batch_convert recebe None (env-only preservado)."""
    origem = tmp_path / "documento.docx"
    origem.write_text("dummy")

    with (
        patch("core.batch.batch_convert", return_value=[]) as batch_mock,
        patch("core.cli.Progress"),
    ):
        result = runner.invoke(app, ["converter", str(origem), str(tmp_path)])

    assert result.exit_code == 0
    chamada = batch_mock.call_args
    assert chamada.kwargs["llm_url"] is None
    assert chamada.kwargs["llm_modelo"] is None


def test_cli_converter_ajuda_mostra_flags_llm():
    """--help do converter lista as flags LLM."""
    result = runner.invoke(app, ["converter", "--help"])
    assert result.exit_code == 0
    assert "--llm-url" in _sem_ansi(result.stdout)
    assert "--llm-modelo" in _sem_ansi(result.stdout)


# ── Subcomandos llm (T9) ─────────────────────────────────────────────────────

def test_cli_llm_help():
    """llm --help lista modelos e testar."""
    result = runner.invoke(app, ["llm", "--help"])
    assert result.exit_code == 0
    assert "modelos" in _sem_ansi(result.stdout)
    assert "testar" in _sem_ansi(result.stdout)


def test_cli_llm_modelos_json_ok():
    """llm modelos --json emite lista de modelos no stdout."""
    modelos = [{"id": "llama3.2-vision", "visao": True}, {"id": "llama3.1", "visao": None}]
    with patch("core.llm_enhancer.listar_modelos", return_value=(modelos, None)):
        result = runner.invoke(app, ["llm", "modelos", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert [m["id"] for m in payload["modelos"]] == ["llama3.2-vision", "llama3.1"]


def test_cli_llm_modelos_json_falha_sem_traceback():
    """Falha → exit 0 com {"ok": false} — o JSON é o contrato com a GUI."""
    with patch("core.llm_enhancer.listar_modelos", return_value=(None, "servidor inacessível")):
        result = runner.invoke(app, ["llm", "modelos", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["modelos"] == []
    assert "Traceback" not in result.output


def test_cli_llm_testar_json_ok():
    """llm testar --json emite ok + latência."""
    with patch("core.llm_enhancer.testar", return_value={"ok": True, "latencia_ms": 42, "erro": None}):
        result = runner.invoke(app, ["llm", "testar", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["latencia_ms"] == 42


def test_cli_llm_testar_json_falha_sem_traceback():
    """Falha → exit 0 com {"ok": false}, sem traceback no output."""
    with patch("core.llm_enhancer.testar", return_value={"ok": False, "latencia_ms": None, "erro": "HTTP 401"}):
        result = runner.invoke(app, ["llm", "testar", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["erro"] == "HTTP 401"
    assert "Traceback" not in result.output
