"""HTML dos e-mails gerados."""
from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from .conferencia import Resultado
from .parse import brl

FONTE = "font-family:Aptos,Calibri,sans-serif;font-size:11pt;color:#000000"
_B = "border:1px solid #BFBFBF;padding:4px 10px"


def saudacao(agora: datetime | None = None) -> str:
    h = (agora or datetime.now(ZoneInfo("America/Sao_Paulo"))).hour
    return "bom dia" if h < 12 else "boa tarde" if h < 18 else "boa noite"


def _td(s: str, extra: str = "") -> str:
    return f'<td style="{_B};{extra}">{s}</td>'


def corpo_prestacao(r: Resultado, agora: datetime | None = None) -> str:
    rc = r.recarga
    linhas = "".join(
        "<tr>"
        + _td(escape(i.danfe.numero))
        + _td(escape(i.danfe.fornecedor or i.po.fornecedor or ""))
        + _td(escape(i.danfe.data or ""))
        + _td(brl(i.danfe.valor), "text-align:right;white-space:nowrap")
        + _td(escape(i.po.po_original))
        + "</tr>"
        for i in sorted(r.itens, key=lambda i: (i.danfe.data or "", i.danfe.numero))
    )

    def total(rotulo: str, valor: str, cor: str = "") -> str:
        return (f'<tr><td colspan="3" style="{_B};text-align:right"><b>{rotulo}</b></td>'
                f'<td style="{_B};text-align:right;white-space:nowrap;{cor}"><b>{valor}</b></td>'
                f'<td style="{_B}"></td></tr>')

    saldo = r.saldo
    cor_saldo = "color:#C00000;" if saldo is not None and saldo < 0 else ""
    cab = "".join(f'<td style="{_B};background:#F1F5F9"><b>{c}</b></td>'
                  for c in ("DANFE", "Fornecedor", "Data", "Valor", "PO"))
    return (
        f'<div style="{FONTE}">'
        f"<p><b>Protocolo Fiscal</b>, {saudacao(agora)}.</p>"
        f"<p>Seguem em anexo as POs para atendimento.</p>"
        f"<p>----- / -----<br><b>Contas a Pagar</b>, para ciência.</p>"
        f"<p>----- / -----<br><b>Willyanson / Luiz Sanchez</b>, seguem em anexo as DANFEs relacionadas ao "
        f"rancho da viagem <b>{escape(rc.viagem or '')}</b> ({escape(rc.navio or '')}), referentes à "
        f"recarga Flash de <b>{brl(rc.valor) if rc.valor is not None else '-'}</b> (RQA {escape(rc.rqa or '')}).</p>"
        f'<table style="border-collapse:collapse;{FONTE}"><tr>{cab}</tr>{linhas}'
        + total(f"Total das DANFEs ({len(r.itens)})", brl(r.total))
        + (total("Valor da recarga", brl(rc.valor)) if rc.valor is not None else "")
        + (total("Saldo no cartão", brl(saldo), cor_saldo) if saldo is not None else "")
        + "</table><p>Agradeço.</p></div>"
    )


def corpo_relatorio(r: Resultado, rascunho_criado: bool) -> str:
    rc = r.recarga
    status = ("✅ Rascunho de prestação de contas criado em <b>Rascunhos</b> da caixa OPS FIN — confira os avisos antes de enviar."
              if rascunho_criado else
              "⛔ <b>Rascunho NÃO criado.</b> Corrija os itens abaixo e aplique de novo a categoria no e-mail da recarga.")
    itens = "".join(
        f"<li>{'⛔' if p.bloqueante else '⚠️'} {escape(p.texto)}</li>" for p in r.problemas
    )
    return (
        f'<div style="{FONTE}">'
        f"<p><b>Flash Rancho — {escape(rc.viagem or '?')} · RQA {escape(rc.rqa or '?')} · "
        f"{brl(rc.valor) if rc.valor is not None else '-'}</b></p>"
        f"<p>{status}</p><ul>{itens}</ul>"
        f"<p>DANFEs conferidas: {len(r.itens)} · Total: {brl(r.total)}"
        + (f" · Saldo: {brl(r.saldo)}" if r.saldo is not None else "")
        + "</p><p style='color:#666'>Mensagem gerada pela rotina flash_rancho (VM).</p></div>"
    )
