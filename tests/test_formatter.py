"""Testes para core/formatter.py."""
from datetime import date
from pathlib import Path

import yaml

from core.formatter import add_obsidian_frontmatter


def test_frontmatter_campos_obrigatorios():
    """title, source, converted, tags presentes."""
    md = add_obsidian_frontmatter("conteúdo", Path("/tmp/arquivo.pdf"))
    assert "title:" in md
    assert "source:" in md
    assert "converted:" in md
    assert "tags:" in md


def test_frontmatter_yaml_valido():
    """yaml.safe_load() sem exceção."""
    md = add_obsidian_frontmatter("conteúdo", Path("/tmp/arquivo.pdf"))
    # Extrai bloco YAML entre ---
    linhas = md.split("\n")
    assert linhas[0] == "---"
    fim = linhas.index("---", 1)
    yaml_block = "\n".join(linhas[1:fim])
    parsed = yaml.safe_load(yaml_block)
    assert isinstance(parsed, dict)
    assert "title" in parsed
    assert "source" in parsed
    assert "converted" in parsed
    assert "tags" in parsed


def test_title_sem_extensao():
    """"arquivo.pdf" -> title: "arquivo"."""
    md = add_obsidian_frontmatter("conteúdo", Path("/tmp/arquivo.pdf"))
    assert "title: arquivo" in md
    assert "title: arquivo.pdf" not in md


def test_converted_formato_iso():
    """Formato YYYY-MM-DD."""
    md = add_obsidian_frontmatter("conteúdo", Path("/tmp/x.pdf"))
    hoje = date.today().isoformat()
    assert f"converted: {hoje}" in md


def test_tags_padrao():
    """['pdf2md', 'converted'] sempre presentes."""
    md = add_obsidian_frontmatter("conteúdo", Path("/tmp/x.pdf"))
    assert "- pdf2md" in md
    assert "- converted" in md


def test_tags_extras():
    """Tags adicionais aparecem no YAML."""
    md = add_obsidian_frontmatter("conteúdo", Path("/tmp/x.pdf"), tags=["fiap", "trabalho"])
    assert "- fiap" in md
    assert "- trabalho" in md
    assert "- pdf2md" in md
    assert "- converted" in md


def test_md_original_preservado():
    """Conteúdo original intacto após frontmatter."""
    original = "# Título\n\nParágrafo de teste."
    md = add_obsidian_frontmatter(original, Path("/tmp/x.pdf"))
    assert original in md
    assert md.endswith(original)
