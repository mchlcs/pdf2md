"""
Máquina genérica de extração de assets de imagem (feature `--imagens`).

Compartilhada por `core/pdf_images.py` (PDF) e `core/doc_converter.py`
(DOCX) — T19 do plano unificou a política de imagens entre formatos:

- D4 — dedup por SHA-256: mesmo conteúdo → 1 arquivo, N links.
- D5 — nomenclatura SEMPRE gerada (nunca derivada de metadado do
  documento) — neutraliza path traversal (CWE-22).
- Segurança: limites anti resource-bomb, recusa de symlink no diretório
  de assets, assert de containment no caminho final.
"""
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from core.utils import (
    _MAX_BYTES_IMAGEM,
    _MAX_IMAGENS_PDF,
    ModoImagem,
)

# Nome de asset: só ASCII seguro — gerado, nunca derivado de metadado.
_RE_NOME_SEGURO = re.compile(r"^[A-Za-z0-9._-]+$")

# Extensões aceitas na escrita direta; fora disso o conversor normaliza
# (PDF → PNG via Pixmap; DOCX → PNG via Pillow) ou descarta com aviso.
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

    Vive por chamada de conversão (thread-safe: o batch cria um por
    arquivo). `total` conta assets gravados/processados (inclusive
    duplicatas e renders de página-scan) — é o limite anti resource-bomb
    do documento.
    """

    prefixo: str = ""
    cache: dict[str, AssetImagem] = field(default_factory=dict)
    total: int = 0

    def atingiu_limite(self) -> bool:
        """True quando o documento atingiu _MAX_IMAGENS_PDF assets."""
        return self.total >= _MAX_IMAGENS_PDF


@dataclass
class ContextoAssets:
    """
    Estado da extração de assets por documento — forma única compartilhada
    por pdf_to_md (converter.py) e doc_to_md (doc_converter.py).

    Um por chamada de conversão → seguro sob ThreadPoolExecutor.
    """

    modo: ModoImagem
    coletor: ColetorAssets
    assets_dir: Path      # onde os assets são gravados (D1)
    md_dir: Path          # diretório do .md — base do link relativo
    wikilinks: bool       # modo Obsidian: ![[nome]] em vez de ![](relativo)
    avisos: list[str]     # avisos de extração (limites, falhas)


def gerar_nome(prefixo: str, base: str, extensao: str) -> str:
    """Gera o nome do asset (D5): base posicional + extensão segura."""
    return f"{prefixo}{base}.{extensao.lstrip('.')}"


def preparar_assets_dir(assets_dir: Path) -> Path:
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


def caminho_seguro(assets_dir: Path, nome: str) -> Path:
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


def registrar_asset(
    assets_dir: Path,
    coletor: ColetorAssets,
    base_nome: str,
    extensao: str,
    dados: bytes,
    origem_descricao: str,
) -> tuple[AssetImagem | None, str | None]:
    """
    Registra um asset no coletor: dedup (D4) + limites + escrita.

    O limite de imagens POR DOCUMENTO é responsabilidade do chamador
    (via `ColetorAssets.atingiu_limite()` — tem controle de loop; aqui só
    o limite por bytes é aplicado).

    A referência no cache NÃO retém os bytes (memória limitada a nomes e
    paths, mesmo com 500 assets de 50 MB) — `dados` só interessa a quem
    acaba de extrair (OCR do alt-text), nunca a duplicatas.

    Args:
        assets_dir: Diretório de destino (validado pelo chamador).
        coletor: Estado compartilhado do documento.
        base_nome: Nome base posicional (ex: "img_p001_0").
        extensao: Extensão já saneada (".png", ".jpg", ...).
        dados: Bytes da imagem.
        origem_descricao: Descrição segura para avisos (ex: "1 da página 2").

    Returns:
        (asset, aviso) — asset None + aviso quando a imagem foi skippada
        (limite de bytes). Duplicatas retornam o asset com `duplicado=True`.
    """
    if len(dados) > _MAX_BYTES_IMAGEM:
        aviso = (
            f"imagem {origem_descricao} excede "
            f"{_MAX_BYTES_IMAGEM // (1024 * 1024)} MB — ignorada"
        )
        return None, aviso

    chave = hashlib.sha256(dados).hexdigest()
    if chave in coletor.cache:
        # D4: mesmo conteúdo → mesmo arquivo, link adicional (sem bytes)
        ref = coletor.cache[chave]
        return AssetImagem(
            nome=ref.nome,
            extensao=ref.extensao,
            dados=b"",
            caminho_disco=ref.caminho_disco,
            duplicado=True,
        ), None

    nome = gerar_nome(coletor.prefixo, base_nome, extensao)
    caminho = caminho_seguro(assets_dir, nome)
    caminho.write_bytes(dados)

    # Cache sem bytes — referência leve para futuras duplicatas
    coletor.cache[chave] = AssetImagem(
        nome=nome,
        extensao=extensao,
        dados=b"",
        caminho_disco=caminho,
    )
    coletor.total += 1
    return AssetImagem(
        nome=nome,
        extensao=extensao,
        dados=dados,
        caminho_disco=caminho,
    ), None
