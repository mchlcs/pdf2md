"""
Fixtures e utilitários para testes do pdf2md.
"""

import fitz  # PyMuPDF
import pytest
from PIL import Image, ImageDraw


@pytest.fixture(scope="session")
def fixture_texto_simples(tmp_path_factory):
    """Cria PDF com 1 página, texto em PT-BR."""
    path = tmp_path_factory.mktemp("fixtures") / "texto_simples.pdf"
    doc = fitz.open()
    pagina = doc.new_page(width=595, height=842)
    pagina.insert_text((50, 50), "Este é um documento de teste em português.")
    pagina.insert_text((50, 80), "Conteúdo simples para validação do pdf2md.")
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture(scope="session")
def fixture_tabela(tmp_path_factory):
    """Cria PDF com tabela simples."""
    path = tmp_path_factory.mktemp("fixtures") / "tabela.pdf"
    doc = fitz.open()
    pagina = doc.new_page(width=595, height=842)
    # Desenha uma tabela simples com retângulos e texto
    for i in range(3):
        for j in range(3):
            x, y = 50 + j * 150, 50 + i * 50
            rect = fitz.Rect(x, y, x + 140, y + 40)
            pagina.draw_rect(rect, color=(0, 0, 0), width=1)
            pagina.insert_text((x + 5, y + 25), f"Célula {i},{j}")
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture(scope="session")
def fixture_multi_coluna(tmp_path_factory):
    """Cria PDF com 2 colunas de texto."""
    path = tmp_path_factory.mktemp("fixtures") / "multi_coluna.pdf"
    doc = fitz.open()
    pagina = doc.new_page(width=595, height=842)
    texto = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 10
    pagina.insert_text((50, 50), texto, fontsize=10)
    pagina.insert_text((300, 50), texto, fontsize=10)
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture(scope="session")
def fixture_escaneado(tmp_path_factory):
    """Cria PDF como imagem (sem texto extraível, só OCR)."""
    path = tmp_path_factory.mktemp("fixtures") / "escaneado.pdf"
    # Cria imagem com texto
    img = Image.new("RGB", (800, 200), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 80), "Documento escaneado — OCR necessário", fill="black")
    img_path = tmp_path_factory.mktemp("fixtures") / "escaneado_temp.png"
    img.save(img_path)

    doc = fitz.open()
    pagina = doc.new_page(width=800, height=200)
    pagina.insert_image(fitz.Rect(0, 0, 800, 200), filename=str(img_path))
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture(scope="session")
def fixture_vazio(tmp_path_factory):
    """Cria PDF válido sem conteúdo."""
    path = tmp_path_factory.mktemp("fixtures") / "vazio.pdf"
    doc = fitz.open()
    doc.new_page(width=595, height=842)
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture(scope="session")
def fixture_img_texto(tmp_path_factory):
    """Cria PNG com texto legível para OCR."""
    img = Image.new("RGB", (800, 200), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 80), "Teste OCR 123 — Documento", fill="black")
    path = tmp_path_factory.mktemp("fixtures") / "img_texto.png"
    img.save(path)
    return path


@pytest.fixture(scope="session")
def fixture_img_doc(tmp_path_factory):
    """Cria JPG simulando documento escaneado."""
    img = Image.new("RGB", (800, 600), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((20, 50), "Contrato de Prestação de Serviços", fill="black")
    draw.text((20, 100), "Parte A: Empresa XYZ Ltda", fill="black")
    draw.text((20, 150), "Parte B: Cliente ABC", fill="black")
    path = tmp_path_factory.mktemp("fixtures") / "img_doc.jpg"
    img.save(path, quality=95)
    return path


@pytest.fixture(scope="session")
def fixture_img_sem_texto(tmp_path_factory):
    """Cria PNG branco."""
    img = Image.new("RGB", (400, 400), color="white")
    path = tmp_path_factory.mktemp("fixtures") / "img_sem_texto.png"
    img.save(path)
    return path


@pytest.fixture
def mock_tesseract(monkeypatch):
    """Mocka pytesseract para testes sem Tesseract instalado."""
    def mock_image_to_string(image, lang=None, config=None):
        return "Texto OCR mockado"
    monkeypatch.setattr("pytesseract.image_to_string", mock_image_to_string)
    monkeypatch.setattr("core.image_converter.verificar_tesseract", lambda: True)
    return mock_image_to_string
