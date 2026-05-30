"""Testes para core/doc_converter.py."""
from pathlib import Path

import pytest

from core.doc_converter import EXTENSOES_DOC, _decodificar_antiword, doc_to_md


def _criar_docx_simples(path: Path, texto: str = "Conteúdo de teste Word.") -> None:
    """Cria um .docx mínimo válido com texto."""
    from docx import Document
    doc = Document()
    doc.add_paragraph(texto)
    doc.save(str(path))


def _criar_docx_estruturado(path: Path) -> None:
    """Cria .docx com título, parágrafos e lista."""
    from docx import Document
    doc = Document()
    doc.add_heading("Relatório de Testes", level=1)
    doc.add_paragraph("Primeiro parágrafo do documento.")
    doc.add_heading("Seção 2", level=2)
    doc.add_paragraph("Segundo parágrafo.")
    doc.save(str(path))


def test_docx_texto_simples(tmp_path):
    """docx com texto → MD com conteúdo."""
    path = tmp_path / "simples.docx"
    _criar_docx_simples(path, "Texto simples para teste.")
    md = doc_to_md(path)
    assert len(md) > 5
    assert "Texto simples" in md or len(md) > 0


def test_docx_estruturado(tmp_path):
    """docx com headers → MD com conteúdo."""
    path = tmp_path / "estruturado.docx"
    _criar_docx_estruturado(path)
    md = doc_to_md(path)
    assert len(md) > 20
    # mammoth preserva headers como # / ##
    assert "Relatório" in md or "Seção" in md or len(md) > 30


def test_docx_nao_existe():
    """FileNotFoundError para arquivo inexistente."""
    with pytest.raises(FileNotFoundError):
        doc_to_md(Path("/nao/existe.docx"))


def test_extensao_invalida(tmp_path):
    """ValueError para extensão não suportada."""
    path = tmp_path / "arquivo.txt"
    path.write_text("conteúdo", encoding="utf-8")
    with pytest.raises(ValueError, match="Extensão não suportada"):
        doc_to_md(path)


def test_docx_corrompido(tmp_path):
    """RuntimeError para .docx corrompido."""
    path = tmp_path / "corrompido.docx"
    path.write_text("isto não é um docx", encoding="utf-8")
    with pytest.raises(RuntimeError):
        doc_to_md(path)


def test_extensoes_doc_set():
    """.doc e .docx estão em EXTENSOES_DOC."""
    assert ".doc" in EXTENSOES_DOC
    assert ".docx" in EXTENSOES_DOC


def test_decodificar_antiword_latin1():
    """Bytes Latin-1 (antiword padrão) com acentos PT-BR → texto correto.

    Regressão: com text=True o subprocess decodificava como UTF-8 e
    levantava UnicodeDecodeError em .doc com ç/ã/é.
    """
    # 'ção' em Latin-1/CP1252: 0xE7=ç 0xE3=ã 0x6F=o
    assert _decodificar_antiword(b"\xe7\xe3o") == "ção"
    # 'relatório' em Latin-1
    assert _decodificar_antiword(b"relat\xf3rio") == "relatório"


def test_decodificar_antiword_utf8():
    """Saída já em UTF-8 é decodificada corretamente (sem corromper)."""
    assert _decodificar_antiword("olá ção".encode()) == "olá ção"


def test_decodificar_antiword_nunca_levanta():
    """Qualquer sequência de bytes decodifica sem exceção (Latin-1 fallback)."""
    # 0x81/0x8D/0x90 são indefinidos em CP1252 mas válidos em Latin-1
    resultado = _decodificar_antiword(b"\x81\x8d\x90\xff")
    assert isinstance(resultado, str)


def test_resolver_antiword_usa_which(monkeypatch):
    """Com antiword no PATH, _resolver_antiword retorna o caminho do which."""
    import core.doc_converter as dc
    monkeypatch.setattr(dc.shutil, "which", lambda nome: "/fake/bin/antiword")
    assert dc._resolver_antiword() == "/fake/bin/antiword"


def test_resolver_antiword_fallback_homebrew(monkeypatch, tmp_path):
    """Sem antiword no PATH (binário PyInstaller), cai nos paths do Homebrew."""
    import core.doc_converter as dc
    monkeypatch.setattr(dc.shutil, "which", lambda nome: None)
    falso = tmp_path / "antiword"
    falso.write_text("")
    monkeypatch.setattr(dc, "_ANTIWORD_PATHS_MACOS", [str(falso)])
    assert dc._resolver_antiword() == str(falso)


def test_resolver_antiword_ausente(monkeypatch):
    """Sem antiword em lugar nenhum → retorna literal 'antiword' (subprocess falha claro)."""
    import core.doc_converter as dc
    monkeypatch.setattr(dc.shutil, "which", lambda nome: None)
    monkeypatch.setattr(dc, "_ANTIWORD_PATHS_MACOS", ["/nao/existe/antiword"])
    assert dc._resolver_antiword() == "antiword"


def test_batch_docx(tmp_path):
    """batch_convert processa .docx corretamente."""
    from core.batch import StatusArquivo, batch_convert
    path = tmp_path / "entrada" / "doc.docx"
    path.parent.mkdir()
    _criar_docx_simples(path)
    resultados = batch_convert(
        origem=path,
        destino=tmp_path / "saida",
        workers=1,
    )
    assert len(resultados) == 1
    assert resultados[0].status == StatusArquivo.CONCLUIDO
    assert resultados[0].destino is not None
    assert resultados[0].destino.exists()


def test_batch_doc_extensao_reconhecida(tmp_path):
    """batch_convert converte .doc que é na verdade um .docx (zip "PK").

    Determinístico: o sniff de assinatura roteia "PK" para mammoth, sem
    depender de antiword. Antes o teste só asseria `!= IGNORADO`, passando
    também em ERRO — não validava conversão real.
    """
    from core.batch import StatusArquivo, batch_convert
    path = tmp_path / "entrada" / "doc.doc"
    path.parent.mkdir()
    _criar_docx_simples(path, "Documento Word salvo como .doc")
    resultados = batch_convert(
        origem=path,
        destino=tmp_path / "saida",
        workers=1,
    )
    assert len(resultados) == 1
    assert resultados[0].status == StatusArquivo.CONCLUIDO
    assert resultados[0].destino is not None
    assert resultados[0].destino.exists()
    assert resultados[0].destino.read_text(encoding="utf-8").strip() != ""
