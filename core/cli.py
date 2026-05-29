"""
Interface de linha de comando para pdf2md.
Uso: pdf2md INPUT OUTPUT [opções]
     pdf2md arquivo.pdf saida/
     pdf2md pasta/pdfs/ pasta/markdowns/ --workers 8
     pdf2md docs/ --vault ~/Obsidian/vault-michel
"""
import sys
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn
from rich.table import Table

from core.utils import validar_path_seguro

app = typer.Typer(
    name="pdf2md",
    help="Converte PDFs e imagens em Markdown. Suporte a batch e Obsidian vault.",
    add_completion=False,
)
console = Console(stderr=True)


def _emitir_json(id_: str, status: str, erro: str | None) -> None:
    """Emite linha JSON no stdout para consumo pelo Swift bridge."""
    linha = json.dumps({"id": id_, "status": status, "erro": erro}, ensure_ascii=False)
    sys.stdout.write(linha + "\n")
    sys.stdout.flush()


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
    from core.batch import batch_convert, StatusArquivo
    from core.image_converter import verificar_tesseract

    # Validação de segurança
    try:
        validar_path_seguro(origem)
        if vault:
            validar_path_seguro(vault)
        validar_path_seguro(destino)
    except ValueError as exc:
        console.print(f"[red]Erro de validação: {exc}[/red]")
        raise typer.Exit(code=1)

    # Verifica Tesseract
    if not verificar_tesseract():
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

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Convertendo...", total=None)
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
        raise typer.Exit(code=1)

    # Progresso / JSON
    if json_output:
        for res in resultados:
            _emitir_json(
                str(res.origem),
                res.status.value,
                res.erro,
            )
    else:
        # Tabela de resultados
        table = Table(title="Resultados da conversão")
        table.add_column("Origem", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Destino", style="magenta")
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
            f"[yellow]Ignorados:[/yellow] {ignorados}"
        )
