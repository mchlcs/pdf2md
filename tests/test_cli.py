"""
Testes para core/cli.py — comando converter via CliRunner.
"""

import re

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
