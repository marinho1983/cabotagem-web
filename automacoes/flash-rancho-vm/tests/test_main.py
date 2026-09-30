"""Orquestração com um Graph falso (sem rede)."""
import json
from pathlib import Path

from flash_rancho import main as M

CFG = json.loads((Path(__file__).parent.parent / "config.example.json").read_text(encoding="utf-8"))

MXM = ("Status de Aprovação: Aprovado para o pedido no. {po}:\n\nValor: R$ {v}\nFornecedor: X\n"
       "Observação: OPS SHP - AMAZON COURAGE - @ALUMAR - ACR26017 -DANFE {d} - RANCHO\n\nANTECIPAÇÃO: RQA 110686\n")


class FakeGraph:
    def __init__(self, pos, danfes, pdfs):
        self.pos, self.danfes, self.pdfs, self.chamadas = pos, danfes, pdfs, []

    def buscar_mensagens(self, caixa, termo):
        return [{"from": {"emailAddress": {"address": "noreply@mxmwebmanager.com.br"}},
                 "receivedDateTime": "2026-09-20", "body": {"content": MXM.format(po=p, v=v, d=d)}}
                for p, v, d in self.pos]

    def pasta(self, cfg):
        return ("drv", cfg["caminho"])

    def listar_arquivos(self, drive, item, prof):
        nomes = self.danfes if "DANFES" in item else self.pdfs
        return [{"name": n, "id": n, "driveId": drive} for n in nomes]

    def criar_encaminhamento(self, caixa, mid):
        self.chamadas.append(("forward", mid)); return {"id": "RASC"}

    def corpo_html(self, caixa, mid):
        return "<html><body><p>original</p></body></html>"

    def atualizar_mensagem(self, caixa, mid, dados):
        self.chamadas.append(("patch", mid, dados))

    def baixar(self, drive, item):
        return b"%PDF"

    def anexar(self, caixa, mid, nome, conteudo):
        self.chamadas.append(("anexo", nome))

    def criar_rascunho(self, caixa, assunto, html, para):
        self.chamadas.append(("relatorio", assunto))

    def definir_categorias(self, caixa, mid, cats):
        self.chamadas.append(("categorias", cats))


MSG = {"id": "M1", "categories": ["FLASH - PRESTAR CONTAS", "Acao"],
       "subject": "OPS SHP- SOLICITAÇÃO DE RECARGA FLASH - FLASH THIAGO- NR 12345678 - AMAZON COURAGE - ACR26017 -R$25.000,00",
       "body": {"content": "Segue em anexo RQA110686 de carga"}}


def test_fluxo_ok_cria_rascunho():
    g = FakeGraph([("035620", "7.242,43", "92811")],
                  ["ACR26017 - Assai - DANFE 92811 - R$7.242,43 - 04.09.pdf"],
                  ["PO035620 - OPS SHP - AMAZON COURAGE - ACR26017 -DANFE 92811 - RANCHO.pdf"])
    M.processar(g, CFG, MSG, {}, simular=False)
    tipos = [c[0] for c in g.chamadas]
    assert tipos == ["forward", "patch", "anexo", "anexo", "categorias"]
    patch = g.chamadas[1][2]
    assert "R$ 17.757,57" in patch["body"]["content"]
    assert patch["body"]["content"].index("Protocolo Fiscal") < patch["body"]["content"].index("original")
    assert len(patch["toRecipients"]) == 5
    assert g.chamadas[-1][1] == ["Acao", "FLASH - RASCUNHO PRONTO"]


def test_fluxo_bloqueado_gera_relatorio():
    g = FakeGraph([("035620", "7.242,43", "92811")], [], [])
    M.processar(g, CFG, MSG, {}, simular=False)
    tipos = [c[0] for c in g.chamadas]
    assert tipos == ["relatorio", "categorias"]
    assert g.chamadas[-1][1] == ["Acao", "FLASH - PENDENCIA"]


def test_simular_nao_grava():
    g = FakeGraph([("035620", "7.242,43", "92811")], [], [])
    M.processar(g, CFG, MSG, {}, simular=True)
    assert g.chamadas == []
