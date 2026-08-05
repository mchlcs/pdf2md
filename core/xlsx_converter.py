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

from core.utils import _sanitizar_celula_md, _validar_existencia, tabela_md

# Encodings tentados em cascade para CSV — latin-1 nunca falha (mapeia 256 bytes).
_CSV_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")


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
    _validar_existencia(path)

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

            headers = [_celula_str(c) for c in rows[0]]
            if not any(headers):
                continue

            linhas = [
                [_celula_str(c) for c in row]
                for row in rows[1:] if any(_celula_str(c) for c in row)
            ]
            partes.append(tabela_md(headers, linhas))
    finally:
        wb.close()

    return "\n\n".join(partes)


def _csv_para_md(path: Path) -> str:
    """Converte .csv em Markdown usando stdlib csv. Lê bytes uma vez, decode in-memory."""
    dados = path.read_bytes()

    rows = None
    for enc in _CSV_ENCODINGS:
        try:
            texto = dados.decode(enc)
            rows = list(csv.reader(texto.splitlines()))
            break
        except UnicodeDecodeError:
            continue

    if not rows:
        return ""

    headers = [_celula_str(c) for c in rows[0]]
    linhas = [[_celula_str(c) for c in row] for row in rows[1:]]
    return tabela_md(headers, linhas)


def _celula_str(valor) -> str:
    """Normaliza valor de célula para string Markdown segura."""
    if valor is None:
        return ""
    return _sanitizar_celula_md(str(valor))
