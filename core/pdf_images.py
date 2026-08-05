"""
Extração de imagens embutidas de PDFs (feature `--imagens`).

A maquinaria genérica de assets (dedup D4, nomenclatura D5, limites e
segurança) vive em `core/image_assets.py` — compartilhada com o DOCX
(T19). Aqui ficam só as partes específicas de PDF: leitura de xrefs via
PyMuPDF e normalização de formatos exóticos para PNG.

Segurança (gate Sentinel):
- Path traversal (CWE-22): nomes sempre gerados — metadado do documento
  nunca vira path; extensão passa por allowlist + revalidação na fronteira.
- Resource bomb: limites por documento (chamador) e por imagem (registrar_asset).
- Symlink: diretório de assets que é symlink é recusado.
"""
from pathlib import Path

import fitz  # PyMuPDF

from core.image_assets import (
    _EXTENSOES_SEGURAS,
    AssetImagem,
    ColetorAssets,
    caminho_seguro,
    preparar_assets_dir,
    registrar_asset,
)

__all__ = [
    "AssetImagem",
    "ColetorAssets",
    "extrair_imagens",
    "preparar_assets_dir",
    "caminho_seguro",
]


def _converter_png(doc: fitz.Document, xref: int) -> tuple[bytes, str] | None:
    """
    Normaliza imagem de formato exótico para PNG via Pixmap.

    CMYK/alpha são convertidos para RGB antes da serialização — o PNG
    resultante é sempre legível por qualquer visualizador.
    """
    try:
        pix = fitz.Pixmap(doc, xref)
        if pix.n - pix.alpha > 3:  # CMYK ou paleta estranha → RGB
            pix = fitz.Pixmap(fitz.csRGB, pix)
        dados = pix.tobytes("png")
    except Exception:
        return None
    return dados, ".png"


def _extrair_bruto(doc: fitz.Document, xref: int) -> tuple[bytes, str] | None:
    """
    Extrai (bytes, extensão) da imagem embutida.

    Extensão fora da allowlist → converte para PNG (a extensão e o conteúdo
    são controlados pelo documento — nada disso vira path).
    """
    try:
        extraido = doc.extract_image(xref)
    except Exception:
        return None
    dados = extraido.get("image") or b""
    if not dados:
        return None
    ext = f".{extraido.get('ext')}" if extraido.get("ext") else ".png"
    if ext not in _EXTENSOES_SEGURAS:
        return _converter_png(doc, xref)
    return dados, ext


def extrair_imagens(
    doc: fitz.Document,
    num_pagina: int,
    assets_dir: Path,
    coletor: ColetorAssets | None = None,
) -> tuple[list[AssetImagem], list[str]]:
    """
    Extrai as imagens embutidas de uma página para assets_dir.

    Dedup por SHA-256 (D4): o primeiro conteúdo grava o arquivo; usos
    seguintes devolvem o mesmo AssetImagem (sem regravar) — logo de
    rodapé em 200 páginas vira 1 arquivo, 200 links.

    Limites (gate Sentinel): total por documento e bytes por imagem.
    Excedeu → skip + aviso, nunca exceção.

    Args:
        doc: Documento PyMuPDF aberto.
        num_pagina: Índice zero-based da página.
        assets_dir: Diretório de destino (criado se necessário).
        coletor: Estado compartilhado entre páginas do mesmo documento.

    Returns:
        (assets, avisos) — assets com arquivo já gravado em disco.
    """
    coletor = coletor or ColetorAssets()
    assets_dir = preparar_assets_dir(assets_dir)
    pagina = doc.load_page(num_pagina)
    assets: list[AssetImagem] = []
    avisos: list[str] = []

    informacoes = pagina.get_images(full=True)
    for idx, info in enumerate(informacoes):
        if coletor.atingiu_limite():
            avisos.append(
                "limite de imagens por documento excedido — extração interrompida"
            )
            break

        extraido = _extrair_bruto(doc, info[0])
        if extraido is None:
            avisos.append(_aviso_nao_extraida(idx, num_pagina))
            continue
        dados, ext = extraido

        # Defesa em profundidade: a extensão vem do documento e a camada de
        # extração não é fronteira confiável — revalida aqui e normaliza PNG.
        if ext not in _EXTENSOES_SEGURAS:
            convertido = _converter_png(doc, info[0])
            if convertido is None:
                avisos.append(_aviso_nao_extraida(idx, num_pagina))
                continue
            dados, ext = convertido

        origem_descricao = f"{idx + 1} da página {num_pagina + 1}"
        asset, aviso = registrar_asset(
            assets_dir, coletor,
            f"img_p{num_pagina + 1:03d}_{idx}", ext, dados, origem_descricao,
        )
        if aviso:
            avisos.append(aviso)
        if asset:
            assets.append(asset)

    return assets, avisos


def _aviso_nao_extraida(idx: int, num_pagina: int) -> str:
    """Aviso único de falha de extração (CWE-209: sem paths do documento)."""
    return f"imagem {idx + 1} da página {num_pagina + 1} não pôde ser extraída"
