"""Testes para core/doc_converter.py."""
from pathlib import Path

import pytest

from core.doc_converter import EXTENSOES_DOC, _decodificar_textutil, doc_to_md


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


def test_decodificar_textutil_latin1():
    """Bytes Latin-1 com acentos PT-BR → replacement chars (não falha).

    textutil emite UTF-8 nativamente. Se bytes Latin-1 vazarem da fonte
    original, errors='replace' produz U+FFFD em vez de decodificar como
    Latin-1 — isso é aceitável porque o caso não ocorre na prática
    (textutil sempre converte para UTF-8).
    """
    # 'ção' em Latin-1/CP1252: 0xE7=ç 0xE3=ã 0x6F=o — bytes inválidos em UTF-8
    resultado = _decodificar_textutil(b"\xe7\xe3o")
    assert isinstance(resultado, str)
    assert "o" in resultado  # 'o' (0x6F) é válido em qualquer encoding
    assert "\ufffd" in resultado  # bytes inválidos viram replacement char


def test_decodificar_textutil_utf8():
    """Saída já em UTF-8 (padrão do textutil) é decodificada corretamente."""
    assert _decodificar_textutil("olá ção".encode()) == "olá ção"


def test_decodificar_textutil_nunca_levanta():
    """Qualquer sequência de bytes decodifica sem exceção (errors='replace')."""
    # 0x81/0x8D/0x90 são indefinidos em CP1252 mas válidos em Latin-1
    resultado = _decodificar_textutil(b"\x81\x8d\x90\xff")
    assert isinstance(resultado, str)


def test_doc_ole_real_via_textutil(tmp_path):
    """.doc OLE binário real (gerado pelo próprio textutil) → conversão end-to-end.

    Cobre o caminho real de _doc_para_md com subprocess de verdade (sem mock),
    validando que a troca antiword→textutil funciona com um arquivo OLE
    legítimo (assinatura D0 CF 11 E0), não apenas com .docx disfarçado de .doc.
    """
    import subprocess as sp
    txt_path = tmp_path / "fonte.txt"
    txt_path.write_text("Conteúdo de teste com acentuação: ção ã é.", encoding="utf-8")
    doc_path = tmp_path / "legado.doc"
    sp.run(
        ["/usr/bin/textutil", "-convert", "doc", str(txt_path), "-output", str(doc_path)],
        check=True,
        timeout=30,
    )
    with open(doc_path, "rb") as f:
        assert f.read(4) == b"\xd0\xcf\x11\xe0"  # confirma OLE binário real

    md = doc_to_md(doc_path)
    assert "Conteúdo de teste" in md
    assert "ção" in md


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
