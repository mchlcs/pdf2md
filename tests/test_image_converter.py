"""Testes para core/image_converter.py."""
from pathlib import Path

import pytest
from PIL import Image

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


# ── TAREFA 2: normalização, corrupção, fallback OCR→LLM, Tesseract real ─────

def test_normalizar_png_gif_extraido_de_pdf():
    """GIF (formato fora de EXTENSOES_IMAGEM) → PNG válido via Pillow."""
    from io import BytesIO

    from core.image_converter import _normalizar_png

    gif = BytesIO()
    frames = [
        Image.new("RGB", (20, 20), color=cor)
        for cor in ((255, 0, 0), (0, 255, 0))
    ]
    frames[0].save(gif, format="GIF", save_all=True, append_images=frames[1:], duration=100, loop=0)
    dados_gif = gif.getvalue()

    assert not dados_gif.startswith(b"\x89PNG")
    normalizado = _normalizar_png(dados_gif)
    assert normalizado.startswith(b"\x89PNG")
    with Image.open(BytesIO(normalizado)) as img:
        assert img.format == "PNG"


def test_normalizar_png_ppm_extraido_de_pdf():
    """PPM (formato fora de EXTENSOES_IMAGEM) → PNG válido via Pillow."""
    from io import BytesIO

    from core.image_converter import _normalizar_png

    ppm = BytesIO()
    Image.new("RGB", (10, 10), color=(10, 200, 30)).save(ppm, format="PPM")

    normalizado = _normalizar_png(ppm.getvalue())
    assert normalizado.startswith(b"\x89PNG")
    with Image.open(BytesIO(normalizado)) as img:
        assert img.format == "PNG"


def test_imagem_corrompida_erro_controlado(tmp_path, mock_tesseract):
    """Arquivo .png corrompido → RuntimeError com mensagem de corrupção."""
    path = tmp_path / "corrompida.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"lixo" * 50)

    with pytest.raises(RuntimeError, match="corrompido"):
        image_to_md(path)


def test_fallback_ocr_curto_usa_llm_vision(tmp_path, monkeypatch):
    """OCR curto (<10 chars) + LLM disponível → texto do LLM vence."""
    img = tmp_path / "scan.png"
    Image.new("RGB", (100, 100), color="white").save(img)

    monkeypatch.setattr("pytesseract.image_to_string", lambda image, lang=None, config=None: "curto")
    monkeypatch.setattr("core.image_converter.verificar_tesseract", lambda: True)
    monkeypatch.setattr("core.llm_enhancer.disponivel", lambda *a, **k: True)
    monkeypatch.setattr(
        "core.llm_enhancer.ocr_com_visao",
        lambda path, config=None: ("# Texto completo do LLM vision", []),
    )

    assert image_to_md(img) == "# Texto completo do LLM vision"


def test_fallback_llm_mais_curto_mantem_ocr(tmp_path, monkeypatch):
    """LLM devolve texto NÃO mais longo que o OCR → mantém o OCR."""
    img = tmp_path / "scan.png"
    Image.new("RGB", (100, 100), color="white").save(img)

    monkeypatch.setattr("pytesseract.image_to_string", lambda image, lang=None, config=None: "abc")
    monkeypatch.setattr("core.image_converter.verificar_tesseract", lambda: True)
    monkeypatch.setattr("core.llm_enhancer.disponivel", lambda *a, **k: True)
    monkeypatch.setattr("core.llm_enhancer.ocr_com_visao", lambda path, config=None: ("xy", []))

    assert image_to_md(img) == "abc"


def test_ocr_razoavel_nao_chama_llm(tmp_path, monkeypatch):
    """OCR com >= 10 chars → LLM nem é consultado."""
    img = tmp_path / "scan.png"
    Image.new("RGB", (100, 100), color="white").save(img)

    monkeypatch.setattr("pytesseract.image_to_string", lambda image, lang=None, config=None: "texto razoável do OCR")
    monkeypatch.setattr("core.image_converter.verificar_tesseract", lambda: True)

    def nao_deve_chamar(*args, **kwargs):
        raise AssertionError("LLM não deveria ser consultado com OCR >= 10 chars")

    monkeypatch.setattr("core.llm_enhancer.disponivel", nao_deve_chamar)

    assert image_to_md(img) == "texto razoável do OCR"


def test_verificar_tesseract_falha_de_verdade(monkeypatch):
    """Failure path REAL: binário inacessível → False (sem mock da função).

    O caminho interno é exercitado de ponta a ponta: shutil.which não acha
    o binário, os paths conhecidos do macOS não existem e o tesseract_cmd
    aponta para um binário inexistente — get_tesseract_version() falha de
    verdade e verificar_tesseract() devolve False.
    """
    import shutil

    import pytesseract

    import core.image_converter as ic

    ic.verificar_tesseract.cache_clear()
    ic._configurar_tesseract_cmd.cache_clear()
    try:
        monkeypatch.setattr(shutil, "which", lambda cmd: None)
        monkeypatch.setattr(ic, "_TESSERACT_PATHS_MACOS", [])
        monkeypatch.setattr(
            pytesseract.pytesseract, "tesseract_cmd", "/opt/nao_existe/tesseract"
        )
        assert ic.verificar_tesseract() is False
    finally:
        ic.verificar_tesseract.cache_clear()
        ic._configurar_tesseract_cmd.cache_clear()


def test_verificar_tesseract_true_quando_instalado():
    """Caminho feliz real: binário acessível → True (sem mock)."""
    import shutil

    if shutil.which("tesseract") is None:
        pytest.skip("Tesseract não instalado neste ambiente")

    import core.image_converter as ic

    ic.verificar_tesseract.cache_clear()
    ic._configurar_tesseract_cmd.cache_clear()
    try:
        assert ic.verificar_tesseract() is True
    finally:
        ic.verificar_tesseract.cache_clear()
        ic._configurar_tesseract_cmd.cache_clear()


# ── ocr_bytes / alt_text_enxuto (modo `ambos`) ──────────────────────────────

def test_ocr_bytes_gif_normaliza_para_png(tmp_path, mock_tesseract):
    """ocr_bytes com GIF (fora de EXTENSOES_IMAGEM) → normaliza e faz OCR."""
    from io import BytesIO

    from core.image_converter import ocr_bytes

    gif = BytesIO()
    Image.new("RGB", (20, 20), color=(255, 0, 0)).save(gif, format="GIF")

    assert ocr_bytes(gif.getvalue(), ".gif") == "Texto OCR mockado"


def test_ocr_bytes_corrompido_retorna_vazio(mock_tesseract):
    """Bytes corrompidos → '' — alt-text degrada sem derrubar a conversão."""
    from core.image_converter import ocr_bytes

    assert ocr_bytes(b"dados corrompidos nao sao imagem", ".png") == ""


def test_alt_text_enxuto_pega_primeira_linha():
    from core.image_converter import alt_text_enxuto

    assert alt_text_enxuto("Primeira linha\nSegunda linha") == "Primeira linha"


def test_alt_text_enxuto_trunca_com_reticencias():
    from core.image_converter import alt_text_enxuto

    longo = "x" * 200
    resultado = alt_text_enxuto(longo, max_chars=120)
    assert len(resultado) == 121  # 120 chars + "…"
    assert resultado.endswith("…")


def test_alt_text_enxuto_vazio_vira_imagem():
    from core.image_converter import alt_text_enxuto

    assert alt_text_enxuto("  \n\n  ") == "imagem"
