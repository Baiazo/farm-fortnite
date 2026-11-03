"""Gera dist\\Farm\\Farm.exe a partir deste código com o PyInstaller.

O exe roda sem Python e sem instalar biblioteca nenhuma. Gerar de novo troca só o programa:
os botões capturados, os ajustes e os registros que ficam ao lado do Farm.exe continuam lá.
"""
import os
import shutil
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
TRABALHO = os.path.join(AQUI, "build")       # arquivos temporários do PyInstaller
SAIDA = os.path.join(AQUI, "dist", "Farm")   # pasta final, com o Farm.exe
NOME = "Farm"
VERSAO = (1, 0, 0)
# Peças do programa dentro da SAIDA. O resto dela (botoes/, ajustes.json, prints/...) é dado do
# usuário e nunca é apagado.
PROGRAMA = (f"{NOME}.exe", "_internal")
# Copiados do projeto na primeira vez, para não precisar capturar os botões de novo
DADOS_INICIAIS = ("botoes", "ajustes.json")

INFO_VERSAO = """\
VSVersionInfo(
  ffi=FixedFileInfo(filevers={v4}, prodvers={v4}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('041604B0', [
      StringStruct('FileDescription', 'Farm Automático para Fortnite'),
      StringStruct('FileVersion', '{texto}'),
      StringStruct('InternalName', '{nome}'),
      StringStruct('OriginalFilename', '{nome}.exe'),
      StringStruct('ProductName', 'Farm Automático'),
      StringStruct('ProductVersion', '{texto}')])]),
    VarFileInfo([VarStruct('Translation', [0x0416, 1200])])
  ]
)
"""


def _icone(caminho):
    from farm import desenhar_icone

    lados = (16, 24, 32, 48, 64, 128, 256)
    desenhar_icone(256).save(caminho, sizes=[(n, n) for n in lados])


def _info_versao(caminho):
    texto = ".".join(map(str, VERSAO))
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(INFO_VERSAO.format(v4=VERSAO + (0,), texto=texto, nome=NOME))


def _trocar_programa(novo):
    """Põe o exe recém-gerado na SAIDA sem tocar nos dados do usuário que estão lá."""
    os.makedirs(SAIDA, exist_ok=True)
    for peca in PROGRAMA:
        antigo = os.path.join(SAIDA, peca)
        try:
            if os.path.isdir(antigo):
                shutil.rmtree(antigo)
            elif os.path.exists(antigo):
                os.remove(antigo)
        except PermissionError:
            sys.exit(f"Não consegui trocar {antigo}: feche o Farm e gere de novo.")
        shutil.move(os.path.join(novo, peca), antigo)
    for dado in DADOS_INICIAIS:
        origem, destino = os.path.join(AQUI, dado), os.path.join(SAIDA, dado)
        if os.path.exists(origem) and not os.path.exists(destino):
            (shutil.copytree if os.path.isdir(origem) else shutil.copy2)(origem, destino)
            print(f"Copiei {dado} do projeto para a pasta do exe.")


def main():
    try:
        import PyInstaller.__main__
    except ImportError:
        sys.exit("Falta o PyInstaller. Rode: python -m pip install pyinstaller")

    os.makedirs(TRABALHO, exist_ok=True)
    icone = os.path.join(TRABALHO, "icone.ico")
    versao = os.path.join(TRABALHO, "versao.txt")
    _icone(icone)
    _info_versao(versao)

    pronto = os.path.join(TRABALHO, "dist")
    PyInstaller.__main__.run([
        os.path.join(AQUI, "farm.py"),
        "--name", NOME,
        "--onedir",
        "--windowed",  # sem janela de console, como o pythonw
        "--icon", icone,
        "--version-file", versao,
        "--distpath", pronto,
        "--workpath", TRABALHO,
        "--specpath", TRABALHO,
        "--noconfirm",
        "--clean",
        "--log-level", "WARN",
    ])
    _trocar_programa(os.path.join(pronto, NOME))
    print(f"\nPronto: {os.path.join(SAIDA, NOME)}.exe")
    print("Pode mover a pasta Farm para onde quiser; os botões e ajustes ficam dentro dela.")


if __name__ == "__main__":
    main()
