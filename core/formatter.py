"""
Adiciona frontmatter YAML compatível com Obsidian ao início de um Markdown.
"""
from pathlib import Path
from datetime import date

import yaml


def add_obsidian_frontmatter(
    md: str,
    source: Path,
    tags: list[str] | None = None,
) -> str:
    """
    Adiciona bloco de frontmatter YAML ao início do Markdown.

    Formato gerado:
        ---
        title: nome-do-arquivo-sem-extensao
        source: nome-original-com-extensao.pdf
        converted: 2026-05-22
        tags:
          - pdf2md
          - converted
        ---

        [conteúdo md original]

    Args:
        md: String Markdown a ser decorada.
        source: Path do arquivo original (usado para title e source no frontmatter).
        tags: Lista de tags adicionais. Combinadas com ['pdf2md', 'converted'].

    Returns:
        String com frontmatter YAML + linha em branco + md original.
    """
    tags_finais = ["pdf2md", "converted"]
    if tags:
        tags_finais.extend(tags)

    frontmatter = {
        "title": source.stem,
        "source": source.name,
        "converted": date.today(),  # objeto date → PyYAML serializa sem aspas: "2026-05-29"
        "tags": tags_finais,
    }

    yaml_block = yaml.dump(
        frontmatter,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )

    return f"---\n{yaml_block}---\n\n{md}"
