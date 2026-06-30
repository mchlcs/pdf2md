"""
Converte arquivos .docx e .doc em Markdown.

Estratégia:
- .docx → mammoth.convert_to_markdown() (estrutura preservada: headers, bold, listas)
- .doc  → textutil via subprocess (texto plano; nativo macOS, sempre em /usr/bin/textutil)
"""
import subprocess
from pathlib import Path

from core.utils import (  # fonte única da verdade (re-exportado)
    EXTENSOES_DOC,
    _validar_existencia,
    _validar_extensao,
    sanitizar_mensagem_erro,
)

# textutil é um utilitário nativo do macOS (parte do CoreServices), presente
# em todo macOS desde versões antigas, sempre em /usr/bin/textutil — diferente
# do antiword (Homebrew), não precisa de resolução de PATH para PyInstaller.
_TEXTUTIL_PATH = "/usr/bin/textutil"


def doc_to_md(path: Path) -> str:
    """
    Converte arquivo Word (.doc ou .docx) em string Markdown.

    Args:
        path: Caminho para o arquivo .doc ou .docx.

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
        return _docx_para_md(path)
    else:
        return _doc_para_md(path)


def _docx_para_md(path: Path) -> str:
    """Converte .docx via mammoth — preserva headers, negrito, listas, tabelas."""
    try:
        import mammoth
        with open(path, "rb") as f:
            resultado = mammoth.convert_to_markdown(f)
        return resultado.value.strip()
    except ImportError as exc:
        raise RuntimeError(
            "mammoth não encontrado. Instale com: pip install mammoth"
        ) from exc
    except Exception as exc:
        raise RuntimeError(
            f"Falha ao converter {path.name} — arquivo corrompido ou formato inválido"
        ) from exc


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
        return _docx_para_md(path)

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
