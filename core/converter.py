"""
Converte arquivos PDF em Markdown.
Detecta automaticamente páginas com imagem e aplica OCR.
"""
from pathlib import Path
import tempfile

import fitz  # PyMuPDF
import pymupdf4llm

from core.image_converter import image_to_md
from core.utils import validar_extensao


def pdf_to_md(path: Path) -> str:
    """
    Converte um arquivo PDF em string Markdown.

    Estratégia:
    1. Tenta extrair texto via pymupdf4llm.to_markdown()
    2. Para cada página sem texto (ou texto < 50 chars), aplica OCR via image_converter
    3. Retorna MD concatenado de todas as páginas

    Args:
        path: Caminho absoluto para o arquivo PDF. Deve existir.

    Returns:
        String Markdown com conteúdo extraído.

    Raises:
        FileNotFoundError: Se path não existe.
        ValueError: Se path não é arquivo PDF válido.
        RuntimeError: Se pymupdf falha ao abrir o arquivo.
    """
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path.name}")

    if path.suffix.lower() != ".pdf":
        raise ValueError("Arquivo não é PDF válido")

    try:
        doc = fitz.open(str(path))
    except Exception as exc:
        raise RuntimeError("Falha ao abrir PDF — arquivo corrompido ou formato inválido") from exc

    partes: list[str] = []

    try:
        for num_pagina in range(len(doc)):
            pagina = doc.load_page(num_pagina)

            # Tenta extrair texto nativo
            texto_pagina = pagina.get_text()

            if len(texto_pagina.strip()) >= 50:
                # Página com texto suficiente — usa pymupdf4llm para esta página
                md_pagina = pymupdf4llm.to_markdown(doc, pages=[num_pagina])
                partes.append(md_pagina)
            else:
                # Página sem texto ou pouco texto — renderiza e OCR
                pix = pagina.get_pixmap(dpi=300)
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp_path = Path(tmp.name)
                    pix.save(str(tmp_path))

                try:
                    md_ocr = image_to_md(tmp_path)
                    partes.append(md_ocr)
                finally:
                    tmp_path.unlink(missing_ok=True)
    finally:
        doc.close()

    return "\n\n".join(partes)
