"""
Converte arquivos .docx e .doc em Markdown.

Estratégia:
- .docx → mammoth.convert_to_markdown() (estrutura preservada: headers, bold, listas)
- .doc  → textutil via subprocess (texto plano; nativo macOS, sempre em /usr/bin/textutil)

Imagens do .docx (T19 — unificação da política `--imagens` com o PDF):
- Antes: mammoth embutia base64 (data-URI) por padrão — inconsistente com o
  PDF (que descarta) e rejeitado na decisão D2 do ADR-0005.
- Agora: transcrever (default) descarta; extrair salva assets com posição
  preservada (o handler do mammoth insere o link no ponto exato do texto);
  ambos extrai + OCR como alt-text; ignorar descarta. A maquinaria de
  segurança (dedup D4, nomenclatura D5, limites, symlink) é a mesma de
  core/image_assets.py.
"""
import os
import re
import subprocess
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from typing import IO, Protocol

from core.image_assets import (
    ColetorAssets,
    preparar_assets_dir,
    registrar_asset,
)
from core.image_converter import alt_text_enxuto, ocr_bytes
from core.utils import (  # fonte única da verdade (re-exportado)
    _MAX_IMAGENS_PDF,
    EXTENSOES_DOC,
    ModoImagem,
    _validar_existencia,
    _validar_extensao,
    sanitizar_mensagem_erro,
)

# textutil é um utilitário nativo do macOS (parte do CoreServices), presente
# em todo macOS desde versões antigas, sempre em /usr/bin/textutil — diferente
# do antiword (Homebrew), não precisa de resolução de PATH para PyInstaller.
_TEXTUTIL_PATH = "/usr/bin/textutil"

# content-type do docx → extensão segura (allowlist do image_assets).
# Fora deste mapa: imagem descartada com aviso (não há conversor confiável).
_MIME_PARA_EXT = {
    "image/png": ".png",
    "image/x-png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
    "image/webp": ".webp",
    "image/tiff": ".tiff",
    "image/x-tiff": ".tiff",
}


class _ImagemMammoth(Protocol):
    """Forma mínima do objeto Image do mammoth (lib sem stubs de tipos)."""

    alt_text: str | None
    content_type: str | None

    def open(self) -> AbstractContextManager[IO[bytes]]: ...


def doc_to_md(
    path: Path,
    modo_imagem: ModoImagem = ModoImagem.transcrever,
    assets_dir: Path | None = None,
    md_dir: Path | None = None,
    wikilinks: bool = False,
    prefixo_nome: str = "",
    avisos: list[str] | None = None,
) -> str:
    """
    Converte arquivo Word (.doc ou .docx) em string Markdown.

    Args:
        path: Caminho para o arquivo .doc ou .docx.
        modo_imagem: Política de imagens embutidas (ModoImagem). O default
            `transcrever` descarta imagens — o base64 embutido pelo mammoth
            foi removido (T19/ADR-0005 D2).
        assets_dir: Diretório dos assets extraídos (extrair/ambos).
            Default: `md_dir/<stem>_assets`.
        md_dir: Diretório do .md de saída — base dos links relativos.
        wikilinks: True em modo Obsidian → `![[nome]]`.
        prefixo_nome: Prefixo dos nomes de asset (diretórios compartilhados).
        avisos: Lista opcional onde avisos de extração são anexados.

    Returns:
        String Markdown com conteúdo extraído.

    Raises:
        FileNotFoundError: Se path não existe.
        ValueError: Se extensão não está em EXTENSOES_DOC.
        RuntimeError: Se conversão falha (arquivo corrompido, textutil ausente, etc).
    """
    _validar_existencia(path)

    sufixo = path.suffix.lower()
    _validar_extensao(path, EXTENSOES_DOC)

    if sufixo == ".docx":
        return _docx_para_md(
            path, modo_imagem, assets_dir, md_dir, wikilinks, prefixo_nome, avisos
        )
    else:
        # .doc via textutil: só texto — modo de imagem não se aplica
        return _doc_para_md(path)


def _docx_para_md(
    path: Path,
    modo_imagem: ModoImagem,
    assets_dir: Path | None,
    md_dir: Path | None,
    wikilinks: bool,
    prefixo_nome: str,
    avisos: list[str] | None,
) -> str:
    """Converte .docx via mammoth — preserva headers, negrito, listas, tabelas.

    O handler de imagem substitui o base64 padrão do mammoth: descarta
    (transcrever/ignorar) ou grava assets na posição exata do documento.
    """
    try:
        import mammoth
    except ImportError as exc:
        raise RuntimeError(
            "mammoth não encontrado. Instale com: pip install mammoth"
        ) from exc

    try:
        # transcrever/ignorar: descarta imagens — sem base64 (T19, D2).
        # O handler vazio impede o data-URI padrão do mammoth.
        if modo_imagem in (ModoImagem.transcrever, ModoImagem.ignorar):
            with open(path, "rb") as f:
                resultado = mammoth.convert_to_markdown(
                    f, convert_image=mammoth.images.img_element(_descartar_imagem)
                )
            return str(resultado.value).strip()

        coletor = ColetorAssets(prefixo=prefixo_nome)
        dir_assets = assets_dir or (path.parent / f"{path.stem}_assets")
        dir_assets = preparar_assets_dir(dir_assets)
        md_dir_efetivo = (md_dir or dir_assets.parent).resolve()

        handler = mammoth.images.img_element(
            _montar_handler(
                modo_imagem, coletor, dir_assets, md_dir_efetivo,
                wikilinks, avisos if avisos is not None else [],
            )
        )

        with open(path, "rb") as f:
            resultado = mammoth.convert_to_markdown(f, convert_image=handler)
        md = str(resultado.value)

        if wikilinks:
            md = _converter_wikilinks(md, coletor)
        return md.strip()
    except Exception as exc:
        raise RuntimeError(
            f"Falha ao converter {path.name} — arquivo corrompido ou formato inválido"
        ) from exc


def _descartar_imagem(image: _ImagemMammoth) -> dict[str, str]:
    """Handler do mammoth que descarta a imagem (transcrever/ignorar)."""
    return {}


def _montar_handler(
    modo_imagem: ModoImagem,
    coletor: ColetorAssets,
    assets_dir: Path,
    md_dir: Path,
    wikilinks: bool,
    avisos: list[str],
) -> Callable[[object], dict[str, str]]:
    """Closure do mammoth: recebe a imagem do documento e devolve atributos <img>.

    `src` é o caminho relativo (ou o nome, em wikilinks) do asset gravado.
    `{}` descarta a imagem (transcrever/ignorar/limite excedido).
    """
    limite_avisado = False

    def converter_imagem(image: _ImagemMammoth) -> dict[str, str]:
        nonlocal limite_avisado
        if coletor.total >= _MAX_IMAGENS_PDF:
            if not limite_avisado:
                avisos.append(
                    f"limite de {_MAX_IMAGENS_PDF} imagens por documento excedido — "
                    "imagens restantes descartadas"
                )
                limite_avisado = True
            return {}

        with image.open() as f:
            dados = f.read()

        ext = _MIME_PARA_EXT.get(image.content_type or "")
        if ext is None:
            avisos.append(
                f"imagem {coletor.total + 1} tem formato não suportado "
                f"({image.content_type or 'desconhecido'}) — descartada"
            )
            coletor.total += 1
            return {}

        asset, aviso = registrar_asset(
            assets_dir, coletor,
            f"img_{coletor.total + 1:04d}", ext, dados,
            f"{coletor.total + 1} do documento",
        )
        if aviso:
            avisos.append(aviso)
        if asset is None:
            return {}

        if wikilinks:
            return {"src": asset.nome}
        src = {"src": os.path.relpath(asset.caminho_disco, md_dir)}
        if modo_imagem == ModoImagem.ambos and not asset.duplicado:
            src["alt"] = alt_text_enxuto(ocr_bytes(asset.dados, asset.extensao))
        return src

    return converter_imagem


def _converter_wikilinks(md: str, coletor: ColetorAssets) -> str:
    """![](...) → ![[...]] apenas para links que geramos (D1 — Obsidian)."""
    nomes = {asset.nome for asset in coletor.cache.values()}

    def _sub(m: re.Match[str]) -> str:
        src = m.group(2)
        if src in nomes:
            return f"![[{src}]]"
        return m.group(0)

    return re.sub(r"!\[([^\]]*)\]\(([^)]*)\)", _sub, md)


def _decodificar_textutil(dados: bytes) -> str:
    """
    Decodifica a saída do textutil defensivamente.

    textutil emite UTF-8 nativamente (diferente do antiword que usava
    Latin-1), mas mantemos errors='replace' como rede de segurança caso
    o .doc de origem contenha bytes em outro encoding que o textutil
    repasse sem reconverter.
    """
    return dados.decode("utf-8", errors="replace")


def _doc_para_md(path: Path) -> str:
    """
    Converte .doc despachando pela assinatura do arquivo (magic bytes):
    - "PK" (zip) → na verdade é um .docx/Word-XML renomeado → mammoth
    - OLE binário (D0 CF 11 E0) ou outro → textutil (nativo macOS)

    Despachar pelo conteúdo (e não por "textutil falhou → tenta docx") evita
    tentativas inúteis e preserva o stderr real do textutil na mensagem de erro.
    """
    with open(path, "rb") as f:
        assinatura = f.read(4)

    # .docx (zip) disfarçado de .doc — roteia direto pro mammoth
    if assinatura[:2] == b"PK":
        return _docx_para_md(path, ModoImagem.transcrever, None, None, False, "", None)

    try:
        # capture_output sem text=True → bytes, decodificados defensivamente
        # (textutil normalmente emite UTF-8, mas a cascata cobre exceções).
        resultado = subprocess.run(
            [_TEXTUTIL_PATH, "-convert", "txt", "-stdout", str(path)],
            capture_output=True,
            timeout=30,
        )
        if resultado.returncode == 0:
            return _decodificar_textutil(resultado.stdout).strip()
        # OLE binário mas textutil falhou — erro claro com o stderr real,
        # com o path absoluto redigido (CWE-209).
        stderr_txt = sanitizar_mensagem_erro(
            _decodificar_textutil(resultado.stderr).strip()
        )
        raise RuntimeError(
            f"Falha ao converter {path.name} — textutil: {stderr_txt}"
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"textutil não encontrado em {_TEXTUTIL_PATH}. "
            "pdf2md requer macOS (textutil é nativo do sistema)."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"Timeout ao converter {path.name} — arquivo muito grande ou corrompido"
        ) from exc
