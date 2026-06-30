"""Testes para core/converter.py."""
from pathlib import Path

import fitz
import pytest
from PIL import Image, ImageDraw

from core.converter import pdf_to_md


def test_pdf_texto_simples(fixture_texto_simples):
    """PDF com texto → MD com conteúdo."""
    md = pdf_to_md(fixture_texto_simples)
    assert "documento de teste" in md.lower() or len(md) > 20


def test_pdf_escaneado_ocr(fixture_escaneado, mock_tesseract):
    """PDF imagem → MD via OCR (requer Tesseract)."""
    md = pdf_to_md(fixture_escaneado)
    assert "OCR" in md or "escaneado" in md.lower() or len(md) > 10


def test_pdf_nao_existe():
    """FileNotFoundError para PDF inexistente."""
    with pytest.raises(FileNotFoundError):
        pdf_to_md(Path("/caminho/que/nao/existe.pdf"))


def test_pdf_corrompido(tmp_path):
    """RuntimeError para PDF corrompido."""
    path = tmp_path / "corrompido.pdf"
    path.write_text("isto não é um pdf", encoding="utf-8")
    with pytest.raises(RuntimeError):
        pdf_to_md(path)


def test_pdf_vazio(fixture_vazio):
    """Retorna string vazia ou MD mínimo para PDF vazio."""
    md = pdf_to_md(fixture_vazio)
    assert md.strip() == "" or len(md.strip()) < 100


def test_pdf_tabela(fixture_tabela):
    """PDF com tabela → MD com conteúdo."""
    md = pdf_to_md(fixture_tabela)
    assert len(md) > 10


def test_pdf_multi_coluna(fixture_multi_coluna):
    """PDF multi-coluna → MD com conteúdo."""
    md = pdf_to_md(fixture_multi_coluna)
    assert len(md) > 20


def test_pdf_misto_texto_imagem(tmp_path, mock_tesseract):
    """Páginas texto + páginas imagem → MD completo."""
    path = tmp_path / "misto.pdf"
    doc = fitz.open()
    # Página 1: texto
    p1 = doc.new_page(width=595, height=842)
    p1.insert_text((50, 50), "Página com texto normal.")
    # Página 2: imagem (simulada)
    img = Image.new("RGB", (400, 200), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 80), "Página escaneada", fill="black")
    img_path = tmp_path / "misto_img.png"
    img.save(img_path)
    p2 = doc.new_page(width=400, height=200)
    p2.insert_image(fitz.Rect(0, 0, 400, 200), filename=str(img_path))
    doc.save(str(path))
    doc.close()

    md = pdf_to_md(path)
    assert len(md) > 20


# ── Funções extraídas (Ciclo 9) ──────────────────────────────────────────────

def test_extrair_chunks_retorna_lista(fixture_texto_simples):
    """_extrair_chunks_markdown retorna list[dict] para PDF válido."""
    from core.converter import _extrair_chunks_markdown
    chunks = _extrair_chunks_markdown(fixture_texto_simples)
    assert isinstance(chunks, list)
    assert len(chunks) > 0


def test_extrair_chunks_fallback_graceful(tmp_path):
    """_extrair_chunks_markdown retorna [] para arquivo não-PDF sem levantar."""
    from core.converter import _extrair_chunks_markdown
    path = tmp_path / "nao_pdf.pdf"
    path.write_bytes(b"dados invalidos")
    chunks = _extrair_chunks_markdown(path)
    assert chunks == []


def test_converter_arquivo_desconhecido_retorna_none(tmp_path):
    """_converter_arquivo retorna None para extensão não suportada."""
    from core.batch import _converter_arquivo
    path = tmp_path / "arquivo.xyz"
    path.write_text("dados")
    assert _converter_arquivo(path) is None


def test_converter_arquivo_pdf_retorna_str(fixture_texto_simples):
    """_converter_arquivo retorna str (markdown) para PDF válido."""
    from core.batch import _converter_arquivo
    resultado = _converter_arquivo(fixture_texto_simples)
    assert isinstance(resultado, str)
    assert len(resultado) > 0


# ── Ignorar margens (cabeçalho/rodapé) ────────────────────────────────────────

def test_pdf_ignorar_margens_remove_topo_rodape(tmp_path):
    """--ignorar-margens remove texto do cabeçalho e rodapé da página."""
    path = tmp_path / "com_margens.pdf"
    doc = fitz.open()
    p = doc.new_page(width=595, height=842)
    # Cabeçalho no topo (y=20)
    p.insert_text((50, 20), "CABECALHO DO DOCUMENTO")
    # Corpo no meio (y=400)
    p.insert_text((50, 400), "Conteudo principal do documento.")
    # Rodapé embaixo (y=820)
    p.insert_text((50, 820), "RODAPE PAGINA 1")
    doc.save(str(path))
    doc.close()

    # Sem ignorar margens — tudo aparece
    md_completo = pdf_to_md(path)
    assert "CABECALHO" in md_completo.upper()
    assert "RODAPE" in md_completo.upper()

    # Com ignorar_margens=10 — cabeçalho e rodapé removidos
    md_filtrado = pdf_to_md(path, ignorar_margens=10.0)
    assert "CABECALHO" not in md_filtrado.upper()
    assert "RODAPE" not in md_filtrado.upper()
    assert "conteudo principal" in md_filtrado.lower()


def test_pdf_ignorar_margens_zero_nao_filtra(fixture_texto_simples):
    """ignorar_margens=0 (padrão) não filtra nada — igual a sem a opção."""
    md_normal = pdf_to_md(fixture_texto_simples)
    md_sem_margem = pdf_to_md(fixture_texto_simples, ignorar_margens=0.0)
    assert md_normal == md_sem_margem
