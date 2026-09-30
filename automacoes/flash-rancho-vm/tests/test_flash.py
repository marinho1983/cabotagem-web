"""Testes com textos reais da caixa OPS FIN (set/2026)."""
from datetime import datetime
from decimal import Decimal

from flash_rancho.conferencia import conferir
from flash_rancho.emails import corpo_prestacao, saudacao
from flash_rancho.parse import (brl, extrair_viagem, parse_aprovacao_mxm, parse_nome_danfe,
                                parse_nome_po, parse_recarga, valor_br)

ASSUNTO_RECARGA = ("ENC: OPS SHP- SOLICITAÇÃO DE RECARGA FLASH - FLASH THIAGO- NR 12345678 - "
                   "AMAZON COURAGE - ACR26017 -R$25.000,00")
CORPO_RECARGA = ("Jessica/Amanda, boa tarde!\r\n\r\nSegue em anexo RQA110686 de carga para o cartão FLASH "
                 "nº 12345678.\r\n\r\nPortador do cartão: Thiago\r\nValor de Recarga: R$25.000,00")

MXM = """Status de Aprovação: Aprovado para o pedido no. 033248:

Valor: R$ 9.443,30
Data: 22/07/26 - ACM/GFS - REQUISIÇÃO RANCHO
Fornecedor: SENDAS DISTRIBUIDORA S/A
Comprador: Mario Luiz Filho
Aprovado por: VARIOS
Observação: OPS - SHP - AMAZON COMMANDER - @ALUMAR - ACM26014 - DANFE 88345 - RANCHO MENSAL

ANTECIPAÇÃO: RQA 107066

FLASH THIAGO
"""


def mxm(po, valor, danfe, rqa="110686", viagem="ACR26017"):
    return parse_aprovacao_mxm(
        f"Status de Aprovação: Aprovado para o pedido no. {po}:\n\nValor: R$ {valor}\n"
        f"Fornecedor: X\nObservação: OPS SHP - AMAZON COURAGE - @ALUMAR - {viagem} -DANFE {danfe} - RANCHO\n\n"
        f"ANTECIPAÇÃO: RQA {rqa}\n")


# ------------------------------------------------------------------ parse
def test_valores():
    assert valor_br("7.242,43") == Decimal("7242.43")
    assert valor_br("25000") == Decimal("25000.00")
    assert brl(Decimal("7242.43")) == "R$ 7.242,43"
    assert brl(Decimal("-120.5")) == "-R$ 120,50"
    assert brl(Decimal("144")) == "R$ 144,00"


def test_viagem():
    assert extrair_viagem("rancho da viagem ACR 26017.") == "ACR26017"
    assert extrair_viagem("@MDD - PSV260181-02") is None


def test_recarga():
    r = parse_recarga(ASSUNTO_RECARGA, CORPO_RECARGA)
    assert (r.viagem, r.navio, r.valor, r.rqa, r.portador, r.cartao) == (
        "ACR26017", "AMAZON COURAGE", Decimal("25000.00"), "110686", "THIAGO", "12345678")
    assert r.assunto.startswith("OPS SHP- SOLICITAÇÃO")


def test_recarga_rqa_com_espaco():
    r = parse_recarga("OPS SHP- SOLICITAÇÃO DE RECARGA FLASH - Flash Thiago- NR 12345678 - AMAZON COMMANDER"
                      " - ACM26016 -R$40.950,00", "Segue em anexo RQA 109447 de carga")
    assert (r.viagem, r.rqa, r.valor, r.portador) == ("ACM26016", "109447", Decimal("40950.00"), "THIAGO")


def test_mxm():
    p = parse_aprovacao_mxm(MXM)
    assert (p.po, p.po_original, p.valor, p.rqa, p.viagem, p.danfe) == (
        "33248", "033248", Decimal("9443.30"), "107066", "ACM26014", "88345")
    assert p.fornecedor == "SENDAS DISTRIBUIDORA S/A"


def test_mxm_sem_rqa_formato_antigo():
    p = parse_aprovacao_mxm(MXM.replace("ANTECIPAÇÃO: RQA 107066", "ANTECIPAÇÃO: R$0,00"))
    assert p.rqa is None


def test_mxm_nao_aprovado():
    assert parse_aprovacao_mxm("Status de Aprovação: Reprovado para o pedido no. 1") is None


def test_nomes_de_arquivo():
    d = parse_nome_danfe("ACR26017 - Atacadão - DANFE 51883 - R$7.148,74 - 09.09.pdf")
    assert (d.numero, d.fornecedor, d.data, d.valor, d.viagem) == (
        "51883", "Atacadão", "09/09", Decimal("7148.74"), "ACR26017")
    d = parse_nome_danfe("ACM26016 - Nacional Aguas - DANFE 10210 - R$272,00.pdf")
    assert (d.numero, d.data, d.valor) == ("10210", None, Decimal("272.00"))
    assert parse_nome_danfe("AC2DF2~1.PDF") is None
    assert parse_nome_danfe("PO035620 - OPS SHP - AMAZON COURAGE - ACR26017 -DANFE 92811 - RANCHO.pdf") is None
    assert parse_nome_po("PO035620 - OPS SHP - AMAZON COURAGE.pdf") == "35620"
    assert parse_nome_po("PO 035618 -  OPS SHP.pdf") == "35618"
    assert parse_nome_po("OPS SHP - RQA 110686.pdf") is None


# ------------------------------------------------------------ conferência
def _danfes(*nomes):
    out = {}
    for n in nomes:
        d = parse_nome_danfe(n)
        out[d.numero] = (d, {"name": n, "id": n, "driveId": "d"})
    return out


def test_conferencia_ok():
    rc = parse_recarga(ASSUNTO_RECARGA, CORPO_RECARGA)
    pos = [mxm("035620", "7.242,43", "92811"), mxm("035618", "624,00", "669"),
           mxm("099999", "100,00", "5555", rqa="110700")]           # outra RQA da viagem: ignorada
    danfes = _danfes("ACR26017 - Assai - DANFE 92811 - R$7.242,43 - 04.09.pdf",
                     "ACR26017 - B F Lemos - DANFE 669 - R$624,00 - 09.09.pdf",
                     "ACR26017 - X - DANFE 5555 - R$100,00 - 10.09.pdf")
    pdfs = {"35620": {"name": "PO035620.pdf"}, "35618": {"name": "PO 035618.pdf"}}
    r = conferir(rc, pos, danfes, pdfs)
    assert not r.problemas
    assert len(r.itens) == 2
    assert r.total == Decimal("7866.43")
    assert r.saldo == Decimal("17133.57")
    html = corpo_prestacao(r, datetime(2026, 9, 21, 15, 0))
    assert "boa tarde" in html and "R$ 17.133,57" in html and "RQA 110686" in html


def test_conferencia_caso_real_courage_21_09():
    """O envio real de 21/09 tinha DANFE sem PO, DANFE com 2 POs e PO sem DANFE."""
    rc = parse_recarga(ASSUNTO_RECARGA, CORPO_RECARGA)
    pos = [mxm("035620", "7.242,43", "92811"), mxm("035615", "1.293,00", "93186"),
           mxm("035612", "1.293,00", "93186"), mxm("035618", "624,00", "669"),
           mxm("035616", "144,00", "10238"), mxm("035617", "500,00", "110330")]
    danfes = _danfes("ACR26017 - Assai - DANFE 92811 - R$7.242,43 - 04.09.pdf",
                     "ACR26017 - Assaí - DANFE 93186 - R$1.293,00 - 09.09.pdf",
                     "ACR26017 - Atacadão - DANFE 51883 - R$7.148,74 - 09.09.pdf",
                     "ACR26017 - B F Lemos - DANFE 669 - R$624,00 - 09.09.pdf",
                     "ACR26017 - Nacional Aguas - DANFE 10238 - R$144,00 - 09.09.pdf")
    pdfs = {n: {"name": n} for n in ("35620", "35615", "35612", "35618", "35616", "35617")}
    r = conferir(rc, pos, danfes, pdfs)
    textos = " | ".join(p.texto for p in r.problemas)
    assert r.bloqueado
    assert "DANFE 93186 tem 2 POs" in textos
    assert "DANFE 110330, que não está na pasta" in textos
    assert "DANFE 51883" in textos            # órfã: aviso
    assert len(r.itens) == 3                  # 92811, 669, 10238


def test_conferencia_valor_divergente():
    rc = parse_recarga(ASSUNTO_RECARGA, CORPO_RECARGA)
    r = conferir(rc, [mxm("035620", "7.000,00", "92811")],
                 _danfes("ACR26017 - Assai - DANFE 92811 - R$7.242,43 - 04.09.pdf"),
                 {"35620": {"name": "p"}})
    assert r.bloqueado and "foi aprovada com R$ 7.000,00" in r.problemas[0].texto


def test_conferencia_sem_pdf_da_po():
    rc = parse_recarga(ASSUNTO_RECARGA, CORPO_RECARGA)
    r = conferir(rc, [mxm("035620", "7.242,43", "92811")],
                 _danfes("ACR26017 - Assai - DANFE 92811 - R$7.242,43 - 04.09.pdf"), {})
    assert r.bloqueado and "PDF da PO 035620" in r.problemas[0].texto


def test_saudacao():
    assert saudacao(datetime(2026, 1, 1, 9)) == "bom dia"
    assert saudacao(datetime(2026, 1, 1, 19)) == "boa noite"
