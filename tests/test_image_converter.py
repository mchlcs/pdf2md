"""Testes para core/image_converter.py."""
from pathlib import Path

import pytest

from core.image_converter import image_to_md


def test_png_texto_claro(fixture_img_texto, mock_tesseract):
    """PNG com texto → OCR correto."""
    md = image_to_md(fixture_img_texto)
    assert "OCR" in md or "123" in md or "Documento" in md


def test_jpg_documento(fixture_img_doc, mock_tesseract):
    """JPG documento escaneado → texto extraído."""
    md = image_to_md(fixture_img_doc)
    assert "Contrato" in md or "Empresa" in md or "Cliente" in md or len(md) > 10


def test_heic_captura_tela(tmp_path):
    """HEIC → sem erro (skip se HEIC não suportado)."""
    try:
        from PIL import Image
        from pillow_heif import register_heif_opener
        register_heif_opener()
        img = Image.new("RGB", (400, 400), color="white")
        path = tmp_path / "captura.heic"
        img.save(path)
    except Exception as exc:
        pytest.skip(f"HEIC não suportado neste ambiente: {exc}")

    # Mocka Tesseract para evitar dependência real
    import core.image_converter as ic
    original = ic.verificar_tesseract
    ic.verificar_tesseract = lambda: True
    try:
        import pytesseract
        original_ocr = pytesseract.image_to_string
        pytesseract.image_to_string = lambda image, lang=None, config=None: "HEIC OK"
        try:
            md = image_to_md(path)
            assert md == "HEIC OK"
        finally:
            pytesseract.image_to_string = original_ocr
    finally:
        ic.verificar_tesseract = original


def test_imagem_sem_texto(fixture_img_sem_texto):
    """Imagem branca → string vazia (usa Tesseract real, imagem sem texto)."""
    md = image_to_md(fixture_img_sem_texto)
    assert md.strip() == ""


def test_extensao_invalida(tmp_path):
    """ValueError para extensão não suportada."""
    path = tmp_path / "arquivo.txt"
    path.write_text("conteúdo", encoding="utf-8")
    with pytest.raises(ValueError, match="Extensão não suportada"):
        image_to_md(path)


def test_arquivo_nao_existe():
    """FileNotFoundError para arquivo inexistente."""
    with pytest.raises(FileNotFoundError):
        image_to_md(Path("/nao/existe.png"))


def test_tesseract_ausente(monkeypatch):
    """RuntimeError com mensagem de instalação quando Tesseract ausente."""
    monkeypatch.setattr("core.image_converter.verificar_tesseract", lambda: False)
    from PIL import Image
    img = Image.new("RGB", (100, 100), color="white")
    # Cria arquivo temporário
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        img.save(tmp_path)
    try:
        with pytest.raises(RuntimeError, match="brew install tesseract"):
            image_to_md(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)
