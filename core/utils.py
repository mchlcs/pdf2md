"""
Utilitários de segurança e validação para pdf2md.
"""
import re
from pathlib import Path

# Casa qualquer sequência de segmentos absolutos "/algo/algo/.../arquivo"
# e captura só o último segmento (basename). Cobre Unix e o prefixo POSIX
# usado mesmo em paths do Windows resolvidos internamente pelo Python.
# O grupo opcional "~" no início preserva esse prefixo intacto quando
# presente (path relativo ao home já reduzido por sanitizar_mensagem_erro),
# evitando que a regex comprima também os segmentos intermediários.
_RE_PATH_ABSOLUTO = re.compile(r"(~)?(?:/[^\s:]+)+/([^\s:/]+)")

# Extensões suportadas
EXTENSOES_PDF: frozenset[str] = frozenset({".pdf"})
EXTENSOES_IMAGEM: frozenset[str] = frozenset({
    ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".webp", ".bmp", ".heic"
})
EXTENSOES_DOC: frozenset[str] = frozenset({".doc", ".docx"})
EXTENSOES_PPTX: frozenset[str] = frozenset({".pptx"})
EXTENSOES_PLANILHA: frozenset[str] = frozenset({".xlsx", ".csv"})
EXTENSOES_PERMITIDAS: frozenset[str] = (
    EXTENSOES_PDF | EXTENSOES_IMAGEM | EXTENSOES_DOC | EXTENSOES_PPTX | EXTENSOES_PLANILHA
)


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
    # Detecta traversal por componente (não substring): captura segmentos '..'
    # reais sem falso positivo em nomes como "relatorio..final.pdf".
    if ".." in path.parts:
        raise ValueError(f"Path contém traversal inválido: {path.name}")
    if base_permitida:
        base_resolvida = base_permitida.resolve()
        try:
            path_resolvido.relative_to(base_resolvida)
        except ValueError as exc:
            # Não vaza o path absoluto do usuário na mensagem de erro
            raise ValueError(f"Path fora do diretório permitido: {path.name}") from exc
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


def sanitizar_mensagem_erro(msg: str) -> str:
    """
    Redige qualquer caminho absoluto presente em uma mensagem de erro,
    substituindo-o pelo basename (nome do arquivo/diretório final).

    Mais robusto que `str.replace(str(origem), origem.name)`: aquela
    abordagem falha quando o path na mensagem de exceção não é
    byte-a-byte idêntico ao path original — ex. symlink resolvido
    (`/var/...` → `/private/var/...` no macOS), diferença de
    maiúsculas/minúsculas em filesystems case-insensitive, ou barra
    final. Esta função usa regex sobre QUALQUER path absoluto na
    mensagem, independente de sua origem (CWE-209).

    O prefixo correspondente ao home do usuário (`Path.home()`) é
    reduzido a `~` antes da regex de basename — assim mensagens como
    "/Users/alice/projeto/x.pdf" preservam o contexto relativo ao home
    ("~/projeto/x.pdf") em vez de virarem apenas "x.pdf".

    Args:
        msg: Mensagem de erro potencialmente contendo paths absolutos.

    Returns:
        Mensagem com paths absolutos substituídos pelo basename (ou por
        "~/..." quando o path está dentro do home do usuário).
    """
    home = str(Path.home())
    if home and home in msg:
        msg = msg.replace(home, "~")

    def _substituir(m: re.Match[str]) -> str:
        prefixo_home, basename = m.group(1), m.group(2)
        # Se o match começa com "~", preserva o caminho relativo completo
        # (ex: "~/projeto/sub/x.pdf") em vez de reduzir a só o basename —
        # já não há mais informação sensível de path absoluto do sistema.
        return m.group(0) if prefixo_home else basename

    return _RE_PATH_ABSOLUTO.sub(_substituir, msg)
