"""
Converte arquivos .docx e .doc em Markdown.

Estratégia:
- .docx → mammoth.convert_to_markdown() (estrutura preservada: headers, bold, listas)
- .doc  → antiword via subprocess (texto plano; requer: brew install antiword)
"""
import subprocess
from pathlib import Path

EXTENSOES_DOC: frozenset[str] = frozenset({".doc", ".docx"})


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
        RuntimeError: Se conversão falha (arquivo corrompido, antiword ausente, etc).
    """
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path.name}")

    sufixo = path.suffix.lower()
    if sufixo not in EXTENSOES_DOC:
        raise ValueError(f"Extensão não suportada: {path.suffix}")

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


def _decodificar_antiword(dados: bytes) -> str:
    """
    Decodifica a saída do antiword tolerando seu encoding padrão Latin-1/CP1252.

    antiword emite Latin-1 por padrão; decodificar como UTF-8 levantaria
    UnicodeDecodeError em documentos PT-BR (ç, ã, é) — exatamente o público-alvo.
    Tenta UTF-8, depois CP1252, e por fim Latin-1 (que nunca falha: mapeia os
    256 bytes). Só usa 'replace' como rede de segurança final.
    """
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return dados.decode(enc)
        except UnicodeDecodeError:
            continue
    return dados.decode("utf-8", errors="replace")


def _doc_para_md(path: Path) -> str:
    """Converte .doc via antiword — requer: brew install antiword."""
    try:
        # capture_output sem text=True → bytes, decodificados defensivamente
        # (antiword usa Latin-1; UTF-8 quebraria em acentos PT-BR).
        resultado = subprocess.run(
            ["antiword", str(path)],
            capture_output=True,
            timeout=30,
        )
        if resultado.returncode == 0:
            return _decodificar_antiword(resultado.stdout).strip()
        # antiword retornou erro — arquivo pode estar no formato XML (Word 2003)
        # tenta tratar como .docx
        try:
            return _docx_para_md(path)
        except Exception as exc_inner:
            stderr_txt = _decodificar_antiword(resultado.stderr).strip()
            raise RuntimeError(
                f"Falha ao converter {path.name} — antiword: {stderr_txt}"
            ) from exc_inner
    except FileNotFoundError as exc:
        raise RuntimeError(
            "antiword não encontrado. "
            "Instale com: brew install antiword"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"Timeout ao converter {path.name} — arquivo muito grande ou corrompido"
        ) from exc
