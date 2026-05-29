# pdf2md

Converte múltiplos PDFs em Markdowns — app macOS com GUI drag-and-drop.

![CI](https://github.com/mchlcs/pdf2md/actions/workflows/ci.yml/badge.svg)

## Uso rápido (CLI)

```bash
# Instalar
uv pip install .

# Converter um PDF
pdf2md arquivo.pdf saida/

# Converter uma pasta inteira
pdf2md pasta/pdfs/ pasta/markdowns/ --workers 4
```

## Uso (GUI)

1. Abrir `PDF2MD.app`
2. Arrastar PDFs para a janela
3. Escolher pasta de saída
4. Clicar em Converter

> **macOS Gatekeeper:** app não-assinado. Primeira vez: clique direito → Abrir.

## Instalação (desenvolvimento)

```bash
git clone https://github.com/mchlcs/pdf2md
cd pdf2md
uv venv && uv pip install -e ".[dev]"
uv run pytest
```

## Limitações v0.1

- PDFs escaneados (imagens) não suportados — v0.2 adicionará OCR via Apple Vision
- Equações LaTeX preservadas como texto plano

## Stack

- **Engine:** `pymupdf4llm` — conversão PDF→MD
- **CLI:** `typer` + `rich`
- **GUI:** SwiftUI (macOS 13+)
- **CI:** GitHub Actions (gratuito)

## Licença

MIT — ver [LICENSE](LICENSE).
