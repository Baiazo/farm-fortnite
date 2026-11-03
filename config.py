"""Ajustes salvos em disco, caminhos e a lista de botões que o farm reconhece."""
import json
import os
import sys
from dataclasses import asdict, dataclass, fields


def _pasta_do_programa():
    """Onde ficam botoes/, ajustes.json e os registros. Pelo exe é a pasta do Farm.exe (o código
    fica escondido na _internal); rodando o .py é a pasta do código."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


PASTA = _pasta_do_programa()
PASTA_BOTOES = os.path.join(PASTA, "botoes")
PASTA_PRINTS = os.path.join(PASTA, "prints")  # prints salvos quando o farm não reconhece nada
ARQUIVO_AJUSTES = os.path.join(PASTA, "ajustes.json")
ARQUIVO_REGISTRO = os.path.join(PASTA, "registro.log")


@dataclass(frozen=True)
class Botao:
    chave: str  # nome do arquivo em botoes/
    nome: str   # rótulo na interface
    dica: str   # onde o botão aparece no jogo
    # cliques seguidos sem o botão sumir antes de o farm desistir; pop-ups podem vir vários
    # seguidos no mesmo lugar, então têm mais folga
    max_cliques: int = 3


# A ordem é a prioridade: se dois botões aparecem juntos, clica no primeiro da lista.
# Pop-ups vêm antes porque tampam os outros botões.
BOTOES = (
    Botao("resgatar", "Resgatar tudo", "pop-up de recompensas", max_cliques=10),
    Botao("aviso", "Pop-up (OK/Fechar)", "aviso que trava a tela", max_cliques=10),
    Botao("voltar", "Voltar ao saguão", "fim da partida"),
    Botao("pular", "Pular", "tela de resultados"),
    Botao("continuar", "Continuar", "depois de ser eliminado"),
    Botao("jogar", "Jogar", "saguão (obrigatório)"),
)

# Faixa aceita para cada ajuste numérico (usada na interface e ao ler o JSON)
LIMITES = {
    "limiar": (0.50, 0.99),
    "intervalo": (0.5, 30.0),
    "pausa_cliques": (1.0, 30.0),
    "afk_a_cada": (1.0, 600.0),
    "afk_segurar": (0.5, 30.0),
}


def caminho_botao(chave):
    return os.path.join(PASTA_BOTOES, f"{chave}.png")


def limitar(campo, valor):
    menor, maior = LIMITES[campo]
    return min(max(float(valor), menor), maior)


@dataclass
class Ajustes:
    limiar: float = 0.80        # nota mínima (0 a 1) para considerar que achou o botão
    intervalo: float = 2.0      # segundos entre leituras da tela
    pausa_cliques: float = 3.0  # tempo mínimo entre dois cliques
    anti_afk: bool = True       # segurar W/A/S/D durante a partida
    so_com_jogo_em_foco: bool = True  # pausar quando o Fortnite sai do primeiro plano
    afk_a_cada: float = 10.0
    afk_segurar: float = 3.0
    sempre_no_topo: bool = False

    @classmethod
    def carregar(cls, caminho=ARQUIVO_AJUSTES):
        """Lê o JSON; valor ausente, fora da faixa ou com tipo errado volta ao padrão."""
        try:
            with open(caminho, encoding="utf-8") as f:
                dados = json.load(f)
        except (OSError, ValueError):
            return cls()
        if not isinstance(dados, dict):
            return cls()
        valores = {}
        for campo in fields(cls):
            v = dados.get(campo.name)
            if campo.name in LIMITES:
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    valores[campo.name] = limitar(campo.name, v)
            elif isinstance(v, bool):
                valores[campo.name] = v
        return cls(**valores)

    def salvar(self, caminho=ARQUIVO_AJUSTES):
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)
