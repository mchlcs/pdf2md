"""
Interface de linha de comando para pdf2md.
Uso: pdf2md INPUT OUTPUT [opções]
     pdf2md arquivo.pdf saida/
     pdf2md pasta/pdfs/ pasta/markdowns/ --workers 8
     pdf2md docs/ --vault ~/Obsidian/vault-michel
"""
import json
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from core.utils import EXTENSOES_IMAGEM, EXTENSOES_PDF, validar_path_seguro

app = typer.Typer(
    name="pdf2md",
    help="Converte PDFs, imagens e documentos Word em Markdown. Suporte a batch e Obsidian vault.",
    add_completion=False,
)
console = Console(stderr=True)


def _emitir_json(id_: str, status: str, erro: str | None, duracao: float = 0.0) -> None:
    """Emite linha JSON no stdout para consumo pelo Swift bridge."""
    linha = json.dumps(
        {"id": id_, "status": status, "erro": erro, "duracao": duracao},
        ensure_ascii=False,
    )
    sys.stdout.write(linha + "\n")
    sys.stdout.flush()


def _fmt_duracao(seg: float) -> str:
    """Formata segundos legível: '1.2s' (<1min) ou '1m02s' (>=1min)."""
    if seg < 60:
        return f"{seg:.1f}s"
    minutos, segundos = divmod(int(round(seg)), 60)
    return f"{minutos}m{segundos:02d}s"


@contextmanager
def _silenciar_stdout_nativo():
    """
    Redireciona o fd 1 (stdout) para o fd 2 (stderr) no nível do OS.

    Bibliotecas C (MuPDF, via pymupdf4llm) escrevem mensagens direto no fd 1
    — `contextlib.redirect_stdout` não as captura, pois trocam só `sys.stdout`.
    Sem isto, o ruído ("Using Tesseract for OCR processing") contamina o
    protocolo JSON consumido pelo bridge Swift. Usado só ao redor da conversão;
    thread-safe na fronteira (as threads do batch são unidas antes de restaurar).
    """
    fd_salvo = os.dup(1)
    try:
        os.dup2(2, 1)
        yield
    finally:
        os.dup2(fd_salvo, 1)
        os.close(fd_salvo)


def _requer_ocr(origem: Path) -> bool:
    """
    True se a entrada pode exigir OCR (imagens ou PDFs).
    Documentos Word (.doc/.docx) usam mammoth/antiword e dispensam Tesseract,
    então uma conversão só de Word não deve ser bloqueada por Tesseract ausente.
    """
    ocr_exts = EXTENSOES_IMAGEM | EXTENSOES_PDF
    if origem.is_file():
        return origem.suffix.lower() in ocr_exts
    if origem.is_dir():
        return any(p.suffix.lower() in ocr_exts for p in origem.iterdir())
    return False


@app.command()
def converter(
    origem: Path = typer.Argument(..., help="Arquivo ou diretório de entrada"),
    destino: Path = typer.Argument(
        Path("."), help="Diretório de saída (padrão: diretório atual)"
    ),
    workers: int = typer.Option(4, "--workers", "-w", help="Processos paralelos"),
    sobrescrever: bool = typer.Option(False, "--sobrescrever", help="Sobrescreve MDs existentes"),
    vault: Path | None = typer.Option(None, "--vault", help="Path do Obsidian vault. Output vai para vault/_inbox/"),
    obsidian: bool = typer.Option(False, "--obsidian", help="Adiciona frontmatter Obsidian ao MD"),
    json_output: bool = typer.Option(False, "--json", hidden=True, help="Output em JSON por linha"),
) -> None:
    """
    Converte PDFs e imagens em Markdown.
    --vault implica --obsidian automaticamente.
    """
    # Lazy imports: só carrega deps pesadas quando o comando é executado
    from core.batch import StatusArquivo, batch_convert
    from core.image_converter import verificar_tesseract

    # Validação de segurança
    try:
        validar_path_seguro(origem)
        if vault:
            validar_path_seguro(vault)
        validar_path_seguro(destino)
    except ValueError as exc:
        console.print(f"[red]Erro de validação: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    # Verifica Tesseract apenas se a entrada puder exigir OCR.
    # (.docx/.doc usam mammoth/antiword e não dependem de Tesseract.)
    if _requer_ocr(origem) and not verificar_tesseract():
        msg = (
            "[red]Tesseract não encontrado. "
            "Instale: brew install tesseract tesseract-lang[/red]"
        )
        console.print(msg)
        if json_output:
            _emitir_json(str(origem), StatusArquivo.ERRO.value, msg)
        raise typer.Exit(code=1)

    # Vault implica obsidian
    if vault is not None:
        obsidian = True

    inicio = time.perf_counter()
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Convertendo...", total=None)
            # Silencia o ruído nativo do MuPDF no stdout durante a conversão,
            # preservando o stdout puro para o JSON emitido depois.
            with _silenciar_stdout_nativo():
                resultados = batch_convert(
                    origem=origem,
                    destino=destino,
                    workers=workers,
                    sobrescrever=sobrescrever,
                    vault=vault,
                    obsidian=obsidian,
                )
            progress.update(task, total=len(resultados), completed=len(resultados))
    except (FileNotFoundError, NotADirectoryError) as exc:
        console.print(f"[red]Erro: {exc}[/red]")
        raise typer.Exit(code=1) from exc
    tempo_total = time.perf_counter() - inicio

    # Progresso / JSON
    if json_output:
        for res in resultados:
            _emitir_json(
                str(res.origem),
                res.status.value,
                res.erro,
                res.duracao,
            )
    else:
        # Tabela de resultados
        table = Table(title="Resultados da conversão")
        table.add_column("Origem", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Destino", style="magenta")
        table.add_column("Tempo", style="blue", justify="right")
        table.add_column("Erro", style="red")

        for res in resultados:
            status_color = {
                StatusArquivo.CONCLUIDO: "green",
                StatusArquivo.ERRO: "red",
                StatusArquivo.IGNORADO: "yellow",
                StatusArquivo.AGUARDANDO: "dim",
                StatusArquivo.PROCESSANDO: "blue",
            }.get(res.status, "white")

            table.add_row(
                res.origem.name,
                f"[{status_color}]{res.status.value}[/{status_color}]",
                res.destino.name if res.destino else "—",
                _fmt_duracao(res.duracao) if res.duracao > 0 else "—",
                res.erro or "—",
            )

        console.print(table)

        total = len(resultados)
        sucessos = sum(1 for r in resultados if r.status == StatusArquivo.CONCLUIDO)
        erros = sum(1 for r in resultados if r.status == StatusArquivo.ERRO)
        ignorados = sum(1 for r in resultados if r.status == StatusArquivo.IGNORADO)

        console.print(
            f"\n[bold]Total:[/bold] {total} | "
            f"[green]Sucessos:[/green] {sucessos} | "
            f"[red]Erros:[/red] {erros} | "
            f"[yellow]Ignorados:[/yellow] {ignorados} | "
            f"[blue]Tempo:[/blue] {_fmt_duracao(tempo_total)}"
        )


if __name__ == "__main__":
    app()
