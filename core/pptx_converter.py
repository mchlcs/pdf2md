"""
Converte arquivos .pptx em Markdown.
Estratégia: python-pptx → extrai título + corpo + tabelas por slide.
"""
from pathlib import Path

# Extensões suportadas (fonte única — re-exportadas para utils.py)
EXTENSOES_PPTX: frozenset[str] = frozenset({".pptx"})


def pptx_to_md(path: Path) -> str:
    """
    Converte arquivo .pptx em Markdown.

    Estratégia:
    - Cada slide → seção (## Slide N)
    - Placeholder título (idx=0) → heading (### texto)
    - Corpo → parágrafos não-vazios preservados
    - Tabelas → tabela Markdown
    - Imagens → omitidas (sem OCR; usar image_converter separadamente se necessário)

    Args:
        path: Caminho absoluto para o arquivo .pptx. Deve existir.

    Returns:
        String Markdown com conteúdo extraído de todos os slides.

    Raises:
        FileNotFoundError: Se path não existe.
        ValueError: Se path não é arquivo .pptx válido.
        RuntimeError: Se python-pptx falha ao abrir o arquivo.
    """
    from pptx import Presentation  # lazy import — evita custo de import no startup

    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path.name}")
    if path.suffix.lower() != ".pptx":
        raise ValueError("Arquivo não é PPTX válido")

    try:
        prs = Presentation(str(path))
    except Exception as exc:
        raise RuntimeError(
            "Falha ao abrir PPTX — arquivo corrompido ou formato inválido"
        ) from exc

    partes: list[str] = []

    for num_slide, slide in enumerate(prs.slides, 1):
        partes.append(f"## Slide {num_slide}")

        for shape in slide.shapes:
            # Tabela — processa antes do text_frame (table shapes têm ambos)
            if shape.has_table:
                md_tabela = _tabela_para_md(shape.table)
                if md_tabela:
                    partes.append(md_tabela)
                continue

            if not shape.has_text_frame:
                continue

            texto_shape = shape.text_frame.text.strip()
            if not texto_shape:
                continue

            # Título: placeholder com idx=0 (OOXML: 0 = título do slide)
            eh_titulo = (
                hasattr(shape, "placeholder_format")
                and shape.placeholder_format is not None
                and shape.placeholder_format.idx == 0
            )

            if eh_titulo:
                partes.append(f"### {texto_shape}")
            else:
                # Corpo: preserva parágrafos não-vazios individualmente
                for para in shape.text_frame.paragraphs:
                    linha = para.text.strip()
                    if linha:
                        partes.append(linha)

    return "\n\n".join(partes)


def _tabela_para_md(table) -> str:
    """Converte python-pptx Table em tabela Markdown."""
    if not table.rows:
        return ""

    linhas: list[str] = []
    for i, row in enumerate(table.rows):
        # Normaliza quebras de linha e pipes dentro de células
        celulas = [
            cell.text.strip().replace("\n", " ").replace("|", "\\|")
            for cell in row.cells
        ]
        linhas.append("| " + " | ".join(celulas) + " |")
        if i == 0:
            # Linha separadora após o header
            linhas.append("| " + " | ".join(["---"] * len(celulas)) + " |")

    return "\n".join(linhas)
