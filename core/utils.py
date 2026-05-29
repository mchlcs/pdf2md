"""
Utilitários de segurança e validação para pdf2md.
"""
from pathlib import Path

# Extensões suportadas
EXTENSOES_PDF: frozenset[str] = frozenset({".pdf"})
EXTENSOES_IMAGEM: frozenset[str] = frozenset({
    ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".webp", ".bmp", ".heic"
})
EXTENSOES_DOC: frozenset[str] = frozenset({".doc", ".docx"})
EXTENSOES_PERMITIDAS: frozenset[str] = EXTENSOES_PDF | EXTENSOES_IMAGEM | EXTENSOES_DOC


def validar_path_seguro(path: Path, base_permitida: Path | None = None) -> Path:
    """
    Valida que path não contém path traversal.
    Se base_permitida fornecida, garante que path está dentro dela.

    Args:
        path: Path a ser validado.
        base_permitida: Path base opcional para restrição.

    Returns:
        Path resolvido e validado.

    Raises:
        ValueError: Se path contém '..' ou está fora de base_permitida.
    """
    path_resolvido = path.resolve()
    if ".." in str(path):
        raise ValueError(f"Path contém traversal inválido: {path}")
    if base_permitida:
        base_resolvida = base_permitida.resolve()
        try:
            path_resolvido.relative_to(base_resolvida)
        except ValueError:
            raise ValueError(f"Path fora do diretório permitido: {path}")
    return path_resolvido


def validar_extensao(path: Path) -> None:
    """
    Valida que a extensão do arquivo está na whitelist.

    Args:
        path: Path do arquivo.

    Raises:
        ValueError: Se extensão não está em EXTENSOES_PERMITIDAS.
    """
    if path.suffix.lower() not in EXTENSOES_PERMITIDAS:
        raise ValueError(f"Extensão não suportada: {path.suffix}")
