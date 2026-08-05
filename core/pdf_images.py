"""
Extração segura de imagens embutidas de PDFs (feature `--imagens`).

Decisões (ADR-0005):
- D4 — dedup por SHA-256: mesmo conteúdo → 1 arquivo, N links no MD.
- D5 — nomenclatura SEMPRE gerada (`img_p{pagina:03d}_{idx}.{ext}`):
  nomes vindos do documento (metadado da imagem) nunca tocam o filesystem —
  neutraliza path traversal (CWE-22).
- Segurança (gate Sentinel): limites anti resource-bomb por documento
  (total de imagens) e por imagem (bytes); diretório de assets que é
  symlink é recusado; assert de containment no caminho final.
"""
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF

from core.utils import (
    _MAX_BYTES_IMAGEM,
    _MAX_IMAGENS_PDF,
)

# Nome de asset: só ASCII seguro — gerado, nunca derivado de metadado do PDF.
_RE_NOME_SEGURO = re.compile(r"^[A-Za-z0-9._-]+$")

# Extensões aceitas na escrita direta. Extensões exóticas do documento são
# normalizadas para PNG via Pixmap (evita nome/envio controlado pelo PDF).
_EXTENSOES_SEGURAS = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".ppm",
})


@dataclass
class AssetImagem:
    """Imagem extraída — conteúdo + nome gerado + caminho já gravado."""

    nome: str
    extensao: str
    dados: bytes
    caminho_disco: Path
    duplicado: bool = False  # True quando o conteúdo já existia (dedup D4)


@dataclass
class ColetorAssets:
    """
    Estado da extração por documento.

    Vive por chamada de pdf_to_md (thread-safe: o batch cria um por arquivo).
    `total` conta imagens processadas (inclusive duplicatas) — é o limite
    anti resource-bomb do documento.
    """

    prefixo: str = ""
    cache: dict[str, AssetImagem] = field(default_factory=dict)
    total: int = 0


def _nome_imagem(num_pagina: int, idx: int, ext: str, prefixo: str = "") -> str:
    """Gera o nome do asset (D5): posição + índice, nunca metadado do PDF."""
    return f"{prefixo}img_p{num_pagina + 1:03d}_{idx}.{ext.lstrip('.')}"


def _preparar_assets_dir(assets_dir: Path) -> Path:
    """
    Valida/cria o diretório de assets (gate Sentinel).

    Recusa: diretório que é symlink, ou path com componentes '..'.
    """
    if assets_dir.is_symlink():
        raise ValueError("diretório de assets não pode ser um symlink")
    if ".." in assets_dir.parts:
        raise ValueError("diretório de assets inválido")
    resolvido = assets_dir.resolve()
    resolvido.mkdir(parents=True, exist_ok=True)
    return resolvido


def _caminho_seguro(assets_dir: Path, nome: str) -> Path:
    """
    Constrói o caminho do asset com nome gerado + assert de containment.

    O nome passa por regex de caracteres seguros (sem '/' ou '..') e o
    caminho resolvido precisa estar dentro do diretório de assets — mesmo
    que uma futura mudança introduza metadado na nomenclatura, o arquivo
    não consegue escapar (CWE-22).
    """
    if not _RE_NOME_SEGURO.match(nome):
        raise ValueError("nome de asset inválido")
    caminho = (assets_dir / nome).resolve()
    if assets_dir not in caminho.parents:
        raise ValueError("asset fora do diretório de assets")
    return caminho


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
    assets_dir = _preparar_assets_dir(assets_dir)
    pagina = doc.load_page(num_pagina)
    assets: list[AssetImagem] = []
    avisos: list[str] = []

    informacoes = pagina.get_images(full=True)
    for idx, info in enumerate(informacoes):
        if coletor.total >= _MAX_IMAGENS_PDF:
            avisos.append(
                f"limite de {_MAX_IMAGENS_PDF} imagens por documento excedido — "
                "extração interrompida"
            )
            break
        coletor.total += 1

        extraido = _extrair_bruto(doc, info[0])
        if extraido is None:
            avisos.append(f"imagem {idx + 1} da página {num_pagina + 1} não pôde ser extraída")
            continue
        dados, ext = extraido

        # Defesa em profundidade: a extensão vem do documento e a camada de
        # extração não é fronteira confiável — revalida aqui e normaliza PNG.
        if ext not in _EXTENSOES_SEGURAS:
            convertido = _converter_png(doc, info[0])
            if convertido is None:
                avisos.append(
                    f"imagem {idx + 1} da página {num_pagina + 1} não pôde ser extraída"
                )
                continue
            dados, ext = convertido

        if len(dados) > _MAX_BYTES_IMAGEM:
            avisos.append(
                f"imagem {idx + 1} da página {num_pagina + 1} excede "
                f"{_MAX_BYTES_IMAGEM // (1024 * 1024)} MB — ignorada"
            )
            continue

        chave = hashlib.sha256(dados).hexdigest()
        if chave in coletor.cache:
            # D4: mesmo conteúdo → mesmo arquivo, link adicional
            asset = coletor.cache[chave]
            assets.append(AssetImagem(
                nome=asset.nome,
                extensao=asset.extensao,
                dados=asset.dados,
                caminho_disco=asset.caminho_disco,
                duplicado=True,
            ))
            continue

        nome = _nome_imagem(num_pagina, idx, ext, coletor.prefixo)
        caminho = _caminho_seguro(assets_dir, nome)
        caminho.write_bytes(dados)

        asset = AssetImagem(
            nome=nome,
            extensao=ext,
            dados=dados,
            caminho_disco=caminho,
        )
        coletor.cache[chave] = asset
        assets.append(asset)

    return assets, avisos
