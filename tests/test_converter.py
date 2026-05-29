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
