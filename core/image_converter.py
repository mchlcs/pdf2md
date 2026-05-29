"""
Converte arquivos de imagem em Markdown via OCR (Tesseract).
Suporta: PNG, JPG, JPEG, TIFF, WEBP, BMP, HEIC.
Pipeline: carrega imagem → pré-processa → OCR → retorna texto como MD.
"""
from pathlib import Path

from PIL import Image
from pillow_heif import register_heif_opener

register_heif_opener()

# Extensões suportadas (usadas também no batch e CLI para whitelist)
EXTENSOES_IMAGEM: frozenset[str] = frozenset({
    ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".webp", ".bmp", ".heic"
})

# Paths comuns do Tesseract no macOS — necessário em apps PyInstaller,
# onde o PATH do processo não inclui /opt/homebrew/bin/
_TESSERACT_PATHS_MACOS = [
    "/opt/homebrew/bin/tesseract",   # Homebrew Apple Silicon (M1/M2/M3)
    "/usr/local/bin/tesseract",      # Homebrew Intel
    "/usr/bin/tesseract",            # instalação manual
]


def _configurar_tesseract_cmd() -> None:
    """
    Configura pytesseract.tesseract_cmd para o path correto no macOS.
    Necessário em binários PyInstaller onde PATH é mínimo (sem /opt/homebrew/bin/).
    Chamado uma vez no início — sem efeito se tesseract já está no PATH.
    """
    import shutil

    import pytesseract

    # Já acessível no PATH atual — não precisa configurar
    if shutil.which("tesseract"):
        return

    # Procura nos paths conhecidos do Homebrew
    for caminho in _TESSERACT_PATHS_MACOS:
        if Path(caminho).exists():
            pytesseract.pytesseract.tesseract_cmd = caminho
            return


def verificar_tesseract() -> bool:
    """
    Verifica se Tesseract está instalado e acessível.
    Configura o path automaticamente para binários PyInstaller no macOS.
    Retorna True se disponível, False caso contrário.
    Não lança exceção.
    """
    try:
        import pytesseract
        _configurar_tesseract_cmd()
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def image_to_md(path: Path) -> str:
    """
    Converte arquivo de imagem em string Markdown via OCR.

    Pipeline de pré-processamento (melhora qualidade OCR):
    1. Carrega imagem (Pillow; HEIC via pillow-heif)
    2. Converte para escala de cinza
    3. Redimensiona se largura < 1000px (scale 2x — melhora OCR em imagens pequenas)
    4. OCR via pytesseract com lang='por+eng'

    Resultado: texto extraído envolto em bloco MD simples (sem formatação especial).

    Args:
        path: Caminho para arquivo de imagem. Extensão deve estar em EXTENSOES_IMAGEM.

    Returns:
        String Markdown com texto extraído. Retorna string vazia se imagem sem texto.

    Raises:
        FileNotFoundError: Se path não existe.
        ValueError: Se extensão não está em EXTENSOES_IMAGEM.
        RuntimeError: Se Tesseract não está instalado.
    """
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path.name}")

    if path.suffix.lower() not in EXTENSOES_IMAGEM:
        raise ValueError(f"Extensão não suportada: {path.suffix}")

    if not verificar_tesseract():
        raise RuntimeError(
            "Tesseract não encontrado. "
            "Instale com: brew install tesseract tesseract-lang"
        )

    import pytesseract

    try:
        with Image.open(path) as img:
            # Converte para escala de cinza
            img_cinza = img.convert("L")

            # Redimensiona se largura < 1000px
            largura, altura = img_cinza.size
            if largura < 1000:
                img_cinza = img_cinza.resize(
                    (largura * 2, altura * 2), Image.Resampling.LANCZOS
                )

            # OCR
            texto = pytesseract.image_to_string(img_cinza, lang="por+eng")
    except Exception as exc:
        raise RuntimeError("Falha no processamento da imagem — verifique se o arquivo está corrompido") from exc

    return texto.strip()
