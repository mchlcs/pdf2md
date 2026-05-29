"""Testes para core/batch.py."""

import fitz
import pytest
from PIL import Image, ImageDraw

from core.batch import StatusArquivo, batch_convert


def test_batch_arquivo_unico(fixture_texto_simples, tmp_path):
    """Arquivo único → 1 MD."""
    resultados = batch_convert(
        origem=fixture_texto_simples,
        destino=tmp_path / "saida",
        workers=1,
    )
    assert len(resultados) == 1
    assert resultados[0].status == StatusArquivo.CONCLUIDO
    assert resultados[0].destino is not None
    assert resultados[0].destino.exists()


def test_batch_diretorio(tmp_path):
    """Dir com 3 PDFs → 3 MDs."""
    entrada = tmp_path / "entrada"
    entrada.mkdir()
    for i in range(3):
        doc = fitz.open()
        p = doc.new_page(width=595, height=842)
        p.insert_text((50, 50), f"PDF {i}")
        doc.save(str(entrada / f"doc{i}.pdf"))
        doc.close()

    resultados = batch_convert(
        origem=entrada,
        destino=tmp_path / "saida",
        workers=2,
    )
    assert len(resultados) == 3
    assert all(r.status == StatusArquivo.CONCLUIDO for r in resultados)


def test_batch_mix_pdf_imagem(tmp_path, fixture_img_texto, mock_tesseract):
    """2 PDFs + 2 PNGs → 4 MDs."""
    entrada = tmp_path / "entrada"
    entrada.mkdir()
    for i in range(2):
        doc = fitz.open()
        p = doc.new_page(width=595, height=842)
        p.insert_text((50, 50), f"PDF {i}")
        doc.save(str(entrada / f"doc{i}.pdf"))
        doc.close()

    # Copia imagem fixture
    import shutil
    shutil.copy(fixture_img_texto, entrada / "img.png")
    # Cria segunda imagem
    img = Image.new("RGB", (400, 200), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 80), "Segunda imagem", fill="black")
    img.save(entrada / "img2.jpg")

    resultados = batch_convert(
        origem=entrada,
        destino=tmp_path / "saida",
        workers=2,
    )
    assert len(resultados) == 4
    assert all(r.status == StatusArquivo.CONCLUIDO for r in resultados)


def test_batch_nao_sobrescreve(tmp_path):
    """sobrescrever=False → pula existentes."""
    entrada = tmp_path / "entrada"
    entrada.mkdir()
    doc = fitz.open()
    p = doc.new_page(width=595, height=842)
    p.insert_text((50, 50), "Texto")
    doc.save(str(entrada / "doc.pdf"))
    doc.close()

    saida = tmp_path / "saida"
    saida.mkdir()
    (saida / "doc.md").write_text("já existe", encoding="utf-8")

    resultados = batch_convert(
        origem=entrada / "doc.pdf",
        destino=saida,
        workers=1,
        sobrescrever=False,
    )
    assert resultados[0].status == StatusArquivo.CONCLUIDO
    # O worker pula existentes, mas batch_convert retorna CONCLUIDO
    # Verificamos que o conteúdo não foi alterado
    assert (saida / "doc.md").read_text(encoding="utf-8") == "já existe"


def test_batch_vault_cria_inbox(tmp_path):
    """vault definido → cria _inbox/ e salva lá."""
    vault = tmp_path / "vault"
    vault.mkdir()
    entrada = tmp_path / "entrada"
    entrada.mkdir()
    doc = fitz.open()
    p = doc.new_page(width=595, height=842)
    p.insert_text((50, 50), "Vault test")
    doc.save(str(entrada / "doc.pdf"))
    doc.close()

    resultados = batch_convert(
        origem=entrada / "doc.pdf",
        destino=tmp_path / "saida",
        vault=vault,
        workers=1,
    )
    assert resultados[0].status == StatusArquivo.CONCLUIDO
    assert (vault / "_inbox" / "doc.md").exists()


def test_batch_obsidian_frontmatter(tmp_path):
    """obsidian=True → MD tem frontmatter."""
    entrada = tmp_path / "entrada"
    entrada.mkdir()
    doc = fitz.open()
    p = doc.new_page(width=595, height=842)
    p.insert_text((50, 50), "Frontmatter test")
    doc.save(str(entrada / "doc.pdf"))
    doc.close()

    resultados = batch_convert(
        origem=entrada / "doc.pdf",
        destino=tmp_path / "saida",
        obsidian=True,
        workers=1,
    )
    assert resultados[0].status == StatusArquivo.CONCLUIDO
    md = (tmp_path / "saida" / "doc.md").read_text(encoding="utf-8")
    assert "---" in md
    assert "title:" in md
    assert "pdf2md" in md


def test_batch_extensao_ignorada(tmp_path):
    """.txt → StatusArquivo.IGNORADO."""
    entrada = tmp_path / "entrada"
    entrada.mkdir()
    (entrada / "leitura.txt").write_text("não suportado", encoding="utf-8")

    resultados = batch_convert(
        origem=entrada,
        destino=tmp_path / "saida",
        workers=1,
    )
    assert len(resultados) == 1
    assert resultados[0].status == StatusArquivo.IGNORADO


def test_batch_vault_invalido(tmp_path):
    """NotADirectoryError se vault não é diretório."""
    with pytest.raises(NotADirectoryError):
        batch_convert(
            origem=tmp_path,
            destino=tmp_path / "saida",
            vault=tmp_path / "nao_e_dir.txt",
            workers=1,
        )


def test_batch_path_traversal(tmp_path):
    """ValueError para ../../etc/passwd.pdf."""
    with pytest.raises(ValueError, match="traversal"):
        batch_convert(
            origem=tmp_path / ".." / ".." / "etc" / "passwd.pdf",
            destino=tmp_path / "saida",
            workers=1,
        )
