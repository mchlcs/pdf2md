"""
Testes para core/pdf_images.py (feature --imagens).

Cobrem o gate Sentinel (T6): traversal, symlink e resource bomb são
testados com mitigação provada, não só por convenção.
"""
from pathlib import Path
from unittest.mock import patch

import fitz  # PyMuPDF
import pytest
from PIL import Image

from core.image_assets import ColetorAssets, caminho_seguro, preparar_assets_dir
from core.pdf_images import extrair_imagens


def _imagem_png(tmp_path: Path, nome: str, cor: tuple[int, int, int]) -> Path:
    """Cria PNG de 50x50 na cor dada."""
    img = Image.new("RGB", (50, 50), color=cor)
    caminho = tmp_path / nome
    img.save(caminho)
    return caminho


def _pdf_com_imagens(tmp_path: Path, qtd: int = 2, paginas: int = 1) -> Path:
    """PDF com `qtd` imagens de cores distintas (uma por página se paginas > 1)."""
    path = tmp_path / "imagens.pdf"
    doc = fitz.open()
    for p in range(paginas):
        pagina = doc.new_page(width=595, height=842)
        for i in range(qtd):
            cor = ((p * 90 + i * 40) % 255, (i * 70) % 255, (p * 30) % 255)
            img = _imagem_png(tmp_path, f"img_{p}_{i}.png", cor)
            pagina.insert_image(fitz.Rect(20 + i * 70, 20, 70 + i * 70, 70), filename=str(img))
    doc.save(str(path))
    doc.close()
    return path


# ── Caso 1: extração normal ──────────────────────────────────────────────────

def test_extrai_imagens_normais(tmp_path):
    """2 imagens embutidas → 2 assets gravados com nome gerado."""
    pdf = _pdf_com_imagens(tmp_path, qtd=2)
    assets_dir = tmp_path / "out" / "doc_assets"

    with fitz.open(str(pdf)) as doc:
        assets, avisos = extrair_imagens(doc, 0, assets_dir)

    assert avisos == []
    assert len(assets) == 2
    for asset in assets:
        assert asset.nome.startswith("img_p001_")
        assert asset.nome.endswith(".png")
        assert asset.caminho_disco.exists()
        assert asset.duplicado is False
    assert len(list(assets_dir.iterdir())) == 2


# ── Caso 2: dedup por SHA-256 (D4) ───────────────────────────────────────────

def test_dedup_mesma_imagem_duas_paginas(tmp_path):
    """Mesma imagem (mesmo xref) em 2 páginas → 1 arquivo, 2 links."""
    pdf = tmp_path / "logo.pdf"
    doc = fitz.open()
    logo = _imagem_png(tmp_path, "logo.png", (200, 30, 30))
    for _ in range(2):
        pagina = doc.new_page(width=595, height=842)
        pagina.insert_image(fitz.Rect(20, 20, 120, 120), filename=str(logo))
    doc.save(str(pdf))
    doc.close()

    coletor = ColetorAssets()
    assets_dir = tmp_path / "assets"
    with fitz.open(str(pdf)) as doc_aberto:
        pag1, avisos1 = extrair_imagens(doc_aberto, 0, assets_dir, coletor)
        pag2, avisos2 = extrair_imagens(doc_aberto, 1, assets_dir, coletor)

    assert avisos1 == [] and avisos2 == []
    assert len(pag1) == 1 and len(pag2) == 1
    assert pag2[0].duplicado is True          # segundo uso = dedup
    assert pag1[0].nome == pag2[0].nome       # mesmo arquivo linkado 2x
    assert len(list(assets_dir.iterdir())) == 1  # 1 arquivo no disco


# ── Caso 3: limite anti resource-bomb (documento) ────────────────────────────

def test_limite_imagens_por_documento(tmp_path):
    """Acima do limite por documento → interrompe + aviso, sem crash."""
    pdf = _pdf_com_imagens(tmp_path, qtd=4)
    assets_dir = tmp_path / "assets"

    with (
        fitz.open(str(pdf)) as doc,
        patch("core.image_assets._MAX_IMAGENS_PDF", 2),
    ):
        assets, avisos = extrair_imagens(doc, 0, assets_dir)

    assert len(assets) == 2
    assert any("limite" in a for a in avisos)


# ── Caso 3b: limite por bytes da imagem ──────────────────────────────────────

def test_limite_bytes_por_imagem(tmp_path):
    """Imagem acima do limite de bytes → skip + aviso."""
    pdf = _pdf_com_imagens(tmp_path, qtd=1)
    assets_dir = tmp_path / "assets"

    with (
        fitz.open(str(pdf)) as doc,
        patch("core.image_assets._MAX_BYTES_IMAGEM", 10),
    ):
        assets, avisos = extrair_imagens(doc, 0, assets_dir)

    assert assets == []
    assert any("MB" in a and "ignorada" in a for a in avisos)


# ── Caso 4: nome hostil do documento é neutralizado (D5) ─────────────────────

def test_ext_hostil_documento_normalizada_para_png(tmp_path):
    """Extensão controlada pelo documento fora da allowlist → converte PNG.

    O nome de imagem embutida é metadado do documento (superfície de
    ataque). Nada disso vira path: a extensão passa pela allowlist e a
    nomenclatura é SEMPRE gerada (D5).
    """
    pdf = _pdf_com_imagens(tmp_path, qtd=1)
    assets_dir = tmp_path / "assets"

    with (
        fitz.open(str(pdf)) as doc,
        patch(
            "core.pdf_images._extrair_bruto",
            return_value=(b"dados-brutos", ".php/../../evil"),
        ),
    ):
        assets, _ = extrair_imagens(doc, 0, assets_dir)

    # .php/../../evil não está na allowlist → conversão para PNG real
    assert len(assets) == 1
    assert assets[0].nome == "img_p001_0.png"
    assert assets[0].extensao == ".png"
    # Nenhum diretório "php" ou traversal criado
    assert list(assets_dir.iterdir())[0].name == "img_p001_0.png"


def testcaminho_seguro_rejeita_traversal(tmp_path):
    """Nome com '/' ou '..' é rejeitado por caminho_seguro (CWE-22)."""
    assets_dir = preparar_assets_dir(tmp_path / "assets")
    with pytest.raises(ValueError):
        caminho_seguro(assets_dir, "../escape.png")
    with pytest.raises(ValueError):
        caminho_seguro(assets_dir, "a/b.png")
    with pytest.raises(ValueError):
        caminho_seguro(assets_dir, "..\\evil.png")


# ── Caso 5: assets_dir symlink é recusado ────────────────────────────────────

def test_symlink_assets_dir_recusado(tmp_path):
    """Diretório de assets que é symlink → ValueError (gate Sentinel)."""
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "assets_link"
    link.symlink_to(real, target_is_directory=True)

    pdf = _pdf_com_imagens(tmp_path, qtd=1)
    with (
        fitz.open(str(pdf)) as doc,
        pytest.raises(ValueError, match="symlink"),
    ):
        extrair_imagens(doc, 0, link)


# ── Caso 6: PDF sem imagem ───────────────────────────────────────────────────

def test_pdf_sem_imagem(tmp_path):
    """PDF só com texto → nenhum asset, nenhum aviso, sem crash."""
    pdf = tmp_path / "texto.pdf"
    doc = fitz.open()
    pagina = doc.new_page(width=595, height=842)
    pagina.insert_text((50, 50), "Apenas texto.")
    doc.save(str(pdf))
    doc.close()

    assets_dir = tmp_path / "assets"
    with fitz.open(str(pdf)) as doc_aberto:
        assets, avisos = extrair_imagens(doc_aberto, 0, assets_dir)

    assert assets == []
    assert avisos == []


# ── Correções de review ──────────────────────────────────────────────────────

def test_ambos_gif_nao_crasha(tmp_path):
    """Modo ambos com GIF embutido: normaliza p/ PNG, sem crash (review).

    _EXTENSOES_SEGURAS aceita .gif, mas EXTENSOES_IMAGEM (OCR) não —
    antes, ocr_bytes explodia ValueError e derrubava a conversão.
    """
    from core.converter import pdf_to_md
    from core.utils import ModoImagem as Modo

    # PDF com GIF embutido
    gif_path = tmp_path / "anim.gif"
    frames = [Image.new("RGB", (20, 20), color=cor) for cor in ((255, 0, 0), (0, 255, 0))]
    frames[0].save(gif_path, save_all=True, append_images=frames[1:], duration=100, loop=0)

    pdf = tmp_path / "com_gif.pdf"
    doc = fitz.open()
    pagina = doc.new_page(width=595, height=842)
    pagina.insert_text(
        (50, 150),
        "Pagina com GIF embutido para testar o modo ambos sem crash.",
    )
    pagina.insert_image(fitz.Rect(50, 50, 90, 90), filename=str(gif_path))
    doc.save(str(pdf))
    doc.close()

    md = pdf_to_md(pdf, modo_imagem=Modo.ambos)

    assert "![" in md  # link gerado (asset GIF persistido)
    assets = tmp_path / "com_gif_assets"
    assert len(list(assets.iterdir())) == 1
    assert list(assets.iterdir())[0].suffix in (".gif", ".png")


def test_scan_renders_contam_no_limite(tmp_path, mock_tesseract):
    """Renders de página-scan contam no limite anti bomb (review Spec-2)."""
    from unittest.mock import patch

    from core.converter import pdf_to_md
    from core.utils import ModoImagem as Modo

    # PDF com 2 páginas-scan
    pdf = tmp_path / "scan_duplo.pdf"
    img = Image.new("RGB", (300, 100), color="white")
    img_path = tmp_path / "s.png"
    img.save(img_path)
    doc = fitz.open()
    for _ in range(2):
        pagina = doc.new_page(width=300, height=100)
        pagina.insert_image(fitz.Rect(0, 0, 300, 100), filename=str(img_path))
    doc.save(str(pdf))
    doc.close()

    avisos: list[str] = []
    with patch("core.image_assets._MAX_IMAGENS_PDF", 1):
        md = pdf_to_md(pdf, modo_imagem=Modo.extrair, avisos=avisos)

    assets = tmp_path / "scan_duplo_assets"
    assert len(list(assets.iterdir())) == 1  # só o primeiro render
    assert any("limite" in a for a in avisos)
    assert md.count("![[") + md.count("![") == 1


# ── TAREFA 3: imagem danificada, dados vazios, CMYK→RGB, defesas ────────────

def test_extrair_bruto_excecao_imagem_danificada(tmp_path):
    """Imagem danificada (extract_image lança) → None, sem propagar exceção.

    O aviso 'não pôde ser extraída' é emitido pelo chamador; a exceção
    interna é engolida na fronteira da extração.
    """
    pdf = _pdf_com_imagens(tmp_path, qtd=1)
    assets_dir = tmp_path / "assets"

    with (
        fitz.open(str(pdf)) as doc,
        patch("fitz.Document.extract_image", side_effect=RuntimeError("imagem danificada")),
    ):
        assets, avisos = extrair_imagens(doc, 0, assets_dir)

    assert assets == []
    assert len(avisos) == 1
    assert "não pôde ser extraída" in avisos[0]


def test_extrair_bruto_dados_vazios(tmp_path):
    """extract_image sem bytes de imagem (vazio) → None (não é asset)."""
    from core.pdf_images import _extrair_bruto

    pdf = _pdf_com_imagens(tmp_path, qtd=1)
    with (
        fitz.open(str(pdf)) as doc,
        patch("fitz.Document.extract_image", return_value={"image": b"", "ext": "png"}),
    ):
        assert _extrair_bruto(doc, doc[0].get_images(full=True)[0][0]) is None


def test_extrair_bruto_sem_extensao_usa_png(tmp_path):
    """extract_image sem campo 'ext' → extensão padrão .png."""
    from core.pdf_images import _extrair_bruto

    pdf = _pdf_com_imagens(tmp_path, qtd=1)
    with (
        fitz.open(str(pdf)) as doc,
        patch("fitz.Document.extract_image", return_value={"image": b"dados"}),
    ):
        dados, ext = _extrair_bruto(doc, doc[0].get_images(full=True)[0][0])

    assert dados == b"dados"
    assert ext == ".png"


def test_extrair_bruto_ext_fora_allowlist_converte(tmp_path):
    """Extensão controlada pelo documento fora da allowlist → converte PNG."""
    from core.pdf_images import _extrair_bruto

    pdf = _pdf_com_imagens(tmp_path, qtd=1)
    with (
        fitz.open(str(pdf)) as doc,
        patch("fitz.Document.extract_image", return_value={"image": b"x", "ext": "php"}),
    ):
        dados, ext = _extrair_bruto(doc, doc[0].get_images(full=True)[0][0])

    assert ext == ".png"
    assert dados.startswith(b"\x89PNG")


def test_extrair_bruto_conversao_falha_retorna_none(tmp_path):
    """Conversão para PNG falha → _extrair_bruto devolve None."""
    from core.pdf_images import _extrair_bruto

    pdf = _pdf_com_imagens(tmp_path, qtd=1)
    with (
        fitz.open(str(pdf)) as doc,
        patch("fitz.Document.extract_image", return_value={"image": b"x", "ext": "php"}),
        patch("core.pdf_images._converter_png", return_value=None),
    ):
        assert _extrair_bruto(doc, doc[0].get_images(full=True)[0][0]) is None


def _pdf_com_imagem_cmyk(tmp_path: Path, rgba: bool = False) -> Path:
    """PDF com 1 imagem CMYK (JPEG) ou RGBA (PNG) embutida."""
    if rgba:
        img = Image.new("RGBA", (40, 40), color=(10, 200, 30, 128))
        img_path = tmp_path / "rgba.png"
        img.save(img_path, format="PNG")
    else:
        img = Image.new("CMYK", (40, 40), color=(10, 200, 30, 0))
        img_path = tmp_path / "cmyk.jpg"
        img.save(img_path, format="JPEG")

    pdf = tmp_path / ("rgba.pdf" if rgba else "cmyk.pdf")
    doc = fitz.open()
    pagina = doc.new_page(width=595, height=842)
    pagina.insert_image(fitz.Rect(20, 20, 100, 100), filename=str(img_path))
    doc.save(str(pdf))
    doc.close()
    return pdf


def test_converter_png_cmyk_para_rgb(tmp_path):
    """CMYK (4 canais) → Pixmap convertido para RGB antes do PNG."""
    from io import BytesIO

    from core.pdf_images import _converter_png

    pdf = _pdf_com_imagem_cmyk(tmp_path)
    with fitz.open(str(pdf)) as doc:
        xref = doc[0].get_images(full=True)[0][0]
        dados, ext = _converter_png(doc, xref)

    assert ext == ".png"
    assert dados.startswith(b"\x89PNG")
    with Image.open(BytesIO(dados)) as img:
        assert img.mode == "RGB"


def test_converter_png_rgba_mantem_alpha(tmp_path):
    """PNG com canal alpha embutido → serialização sem crash, PNG legível.

    O Pixmap de xref é construído sem alpha (default do PyMuPDF), então o
    resultado pode sair RGB — o contrato é: PNG válido, sem exceção.
    """
    from io import BytesIO

    from core.pdf_images import _converter_png

    pdf = _pdf_com_imagem_cmyk(tmp_path, rgba=True)
    with fitz.open(str(pdf)) as doc:
        xref = doc[0].get_images(full=True)[0][0]
        dados, ext = _converter_png(doc, xref)

    assert ext == ".png"
    assert dados.startswith(b"\x89PNG")
    with Image.open(BytesIO(dados)) as img:
        assert img.mode in ("RGB", "RGBA")


def test_converter_png_falha_retorna_none(tmp_path):
    """Pixmap lança (imagem corrompida) → _converter_png devolve None."""
    from core.pdf_images import _converter_png

    pdf = _pdf_com_imagens(tmp_path, qtd=1)
    with fitz.open(str(pdf)) as doc:
        xref = doc[0].get_images(full=True)[0][0]
        with patch("core.pdf_images.fitz.Pixmap", side_effect=RuntimeError("pixmap falhou")):
            assert _converter_png(doc, xref) is None


def test_extrair_imagens_revalidacao_defesa_conversao_falha(tmp_path):
    """Defesa em profundidade: revalidação falha → aviso, sem crash.

    _extrair_bruto devolve extensão hostil; a revalidação na fronteira
    tenta converter e, com a conversão falhando, emite o aviso padrão.
    """
    pdf = _pdf_com_imagens(tmp_path, qtd=1)
    assets_dir = tmp_path / "assets"

    with (
        fitz.open(str(pdf)) as doc,
        patch("core.pdf_images._extrair_bruto", return_value=(b"dados-brutos", ".php/../../evil")),
        patch("core.pdf_images._converter_png", return_value=None),
    ):
        assets, avisos = extrair_imagens(doc, 0, assets_dir)

    assert assets == []
    assert len(avisos) == 1
    assert "não pôde ser extraída" in avisos[0]


def test_aviso_nao_extraida_formato():
    """Aviso padrão de extração falha: posição + página, sem paths (CWE-209)."""
    from core.pdf_images import _aviso_nao_extraida

    assert _aviso_nao_extraida(0, 0) == "imagem 1 da página 1 não pôde ser extraída"
    assert _aviso_nao_extraida(3, 4) == "imagem 4 da página 5 não pôde ser extraída"
