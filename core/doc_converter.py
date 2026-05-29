"""
Converte arquivos .docx e .doc em Markdown.

Estratégia:
- .docx → mammoth.convert_to_markdown() (estrutura preservada: headers, bold, listas)
- .doc  → antiword via subprocess (texto plano; requer: brew install antiword)
"""
from pathlib import Path
import subprocess

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
    except ImportError:
        raise RuntimeError(
            "mammoth não encontrado. Instale com: pip install mammoth"
        )
    except Exception as exc:
        raise RuntimeError(
            f"Falha ao converter {path.name} — arquivo corrompido ou formato inválido"
        ) from exc


def _doc_para_md(path: Path) -> str:
    """Converte .doc via antiword — requer: brew install antiword."""
    try:
        resultado = subprocess.run(
            ["antiword", str(path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if resultado.returncode == 0:
            return resultado.stdout.strip()
        # antiword retornou erro — arquivo pode estar no formato XML (Word 2003)
        # tenta tratar como .docx
        try:
            return _docx_para_md(path)
        except Exception:
            raise RuntimeError(
                f"Falha ao converter {path.name} — "
                f"antiword: {resultado.stderr.strip()}"
            )
    except FileNotFoundError:
        raise RuntimeError(
            "antiword não encontrado. "
            "Instale com: brew install antiword"
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"Timeout ao converter {path.name} — arquivo muito grande ou corrompido"
        )
