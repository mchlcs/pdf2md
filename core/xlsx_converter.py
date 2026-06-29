"""
Converte planilhas (.xlsx, .csv) em Markdown.

Estratégia:
- .xlsx → openpyxl: cada sheet vira tabela Markdown com nome como heading
- .csv  → stdlib csv: uma tabela Markdown (sem deps extras)

Nota: .xls (formato legado) não suportado — requer xlrd e o formato está
obsoleto desde Excel 2007. Usuários devem converter para .xlsx primeiro.
"""
import csv
from pathlib import Path


def planilha_to_md(path: Path) -> str:
    """
    Converte planilha (.xlsx ou .csv) em Markdown.

    Dispatcha para o conversor correto pela extensão.

    Args:
        path: Caminho para o arquivo de planilha.

    Returns:
        String Markdown com conteúdo tabular extraído.

    Raises:
        FileNotFoundError: Se path não existe.
        ValueError: Se extensão não é suportada.
    """
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path.name}")

    sufixo = path.suffix.lower()
    if sufixo == ".xlsx":
        return _xlsx_para_md(path)
    elif sufixo == ".csv":
        return _csv_para_md(path)
    else:
        raise ValueError(f"Extensão não suportada por planilha_to_md: {sufixo}")


def _xlsx_para_md(path: Path) -> str:
    """Converte .xlsx em Markdown usando openpyxl."""
    import openpyxl  # lazy import — evita custo no startup

    try:
        wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    except Exception as exc:
        raise RuntimeError(
            "Falha ao abrir XLSX — arquivo corrompido ou formato inválido"
        ) from exc

    partes: list[str] = []

    try:
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows = list(ws.iter_rows(values_only=True))

            if not rows:
                continue

            partes.append(f"## {sheet_name}")

            # Linha de headers
            headers = [_celula_str(c) for c in rows[0]]
            if not any(headers):
                continue

            partes.append("| " + " | ".join(headers) + " |")
            partes.append("| " + " | ".join(["---"] * len(headers)) + " |")

            # Linhas de dados
            for row in rows[1:]:
                celulas = [_celula_str(c) for c in row]
                # Pula linhas completamente vazias
                if any(celulas):
                    partes.append("| " + " | ".join(celulas) + " |")
    finally:
        wb.close()

    return "\n\n".join(partes)


def _csv_para_md(path: Path) -> str:
    """Converte .csv em Markdown usando stdlib csv."""
    # utf-8-sig lida com BOM do Excel (arquivos exportados do Windows)
    # Cascata de decode: latin-1 nunca falha (mapeia 256 bytes) — garante
    # que qualquer arquivo é lido, mesmo com encoding exótico.
    rows = None
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            with open(path, newline="", encoding=enc) as f:
                rows = list(csv.reader(f))
            break
        except UnicodeDecodeError:
            continue

    if not rows:
        return ""

    headers = [_celula_str(c) for c in rows[0]]
    linhas: list[str] = []
    linhas.append("| " + " | ".join(headers) + " |")
    linhas.append("| " + " | ".join(["---"] * len(headers)) + " |")

    for row in rows[1:]:
        celulas = [_celula_str(c) for c in row]
        linhas.append("| " + " | ".join(celulas) + " |")

    return "\n".join(linhas)


def _celula_str(valor) -> str:
    """Normaliza valor de célula para string Markdown segura."""
    if valor is None:
        return ""
    # Pipe dentro de célula quebraria a tabela MD
    return str(valor).strip().replace("\n", " ").replace("|", "\\|")
