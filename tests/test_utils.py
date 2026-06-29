"""
Testes para core/utils.py — foco na função sanitizar_mensagem_erro
(redação de paths absolutos em mensagens de erro, CWE-209).
"""
from pathlib import Path

from core.utils import sanitizar_mensagem_erro


def test_sanitiza_path_simples():
    """Path absoluto simples é reduzido ao basename."""
    msg = "erro ao processar /Users/alice/Documents/segredo.pdf"
    assert sanitizar_mensagem_erro(msg) == "erro ao processar segredo.pdf"


def test_sanitiza_path_resolvido_symlink_macos():
    """
    Path resolvido via symlink (ex: /tmp → /private/var/folders/... no
    macOS) é diferente do path original passado pelo usuário — o antigo
    str.replace(str(origem), ...) falhava aqui porque as strings não
    eram idênticas. A regex captura qualquer path absoluto, então cobre
    este caso independente da origem do path na mensagem.
    """
    msg = (
        "[Errno 2] No such file or directory: "
        "'/private/var/folders/xx/T/tmpdir/segredo.pdf'"
    )
    resultado = sanitizar_mensagem_erro(msg)
    assert "segredo.pdf" in resultado
    assert "/private/var" not in resultado
    assert "/folders/" not in resultado


def test_sanitiza_case_mismatch():
    """
    Filesystems case-insensitive (HFS+/APFS padrão) podem devolver o path
    com capitalização diferente da original — a regex não depende de
    comparação exata, então cobre esse caso também.
    """
    msg = "falha em /Users/Alice/DOCUMENTS/Segredo.PDF"
    resultado = sanitizar_mensagem_erro(msg)
    assert resultado == "falha em Segredo.PDF"


def test_sanitiza_multiplos_paths_na_mesma_mensagem():
    """Mais de um path absoluto na mesma mensagem — ambos são redigidos."""
    msg = "copiando /Users/alice/origem.pdf para /Users/alice/saida/destino.md"
    resultado = sanitizar_mensagem_erro(msg)
    assert resultado == "copiando origem.pdf para destino.md"
    assert "/Users/alice" not in resultado


def test_sanitiza_path_dentro_do_home_preserva_relativo():
    """
    Path dentro do home do usuário é reduzido a "~/..." preservando a
    estrutura relativa, em vez de virar apenas o basename — útil para
    debug sem expor o path absoluto completo do sistema.
    """
    home = str(Path.home())
    msg = f"erro em {home}/projeto/sub/arquivo.pdf"
    resultado = sanitizar_mensagem_erro(msg)
    assert resultado == "erro em ~/projeto/sub/arquivo.pdf"
    assert home not in resultado


def test_sanitiza_path_home_com_trailing_slash():
    """Variante com barra final do diretório não quebra a substituição."""
    home = str(Path.home())
    msg = f"diretório inválido: {home}/"
    resultado = sanitizar_mensagem_erro(msg)
    assert home not in resultado


def test_sanitiza_mensagem_sem_path_fica_inalterada():
    """Mensagens sem path absoluto não são modificadas."""
    msg = "tipo de arquivo não suportado"
    assert sanitizar_mensagem_erro(msg) == msg


def test_sanitiza_preserva_texto_ao_redor_do_path():
    """Texto antes/depois do path é preservado intacto."""
    msg = "ValueError: Path fora do diretório permitido: /etc/passwd (verifique permissões)"
    resultado = sanitizar_mensagem_erro(msg)
    assert resultado == (
        "ValueError: Path fora do diretório permitido: passwd (verifique permissões)"
    )
