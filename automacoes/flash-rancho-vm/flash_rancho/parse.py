"""Leitura dos textos do processo Flash Rancho.

Tudo aqui é função pura (sem Graph), para poder ser testado com os
e-mails e nomes de arquivo reais.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional

NAVIOS = {
    "APN": "AMAZON PIONEER",
    "APT": "AMAZON PATHFINDER",
    "APF": "AMAZON PATHFINDER",
    "ACM": "AMAZON COMMANDER",
    "ACR": "AMAZON COURAGE",
}

_RE_VIAGEM = re.compile(r"(?<![A-Z])([A-Z]{3}) ?(\d{5})(?!\d)")
_RE_VALOR = re.compile(r"R\$\s*([\d.]+(?:,\d{1,2})?)")
_RE_DANFE = re.compile(r"DANFE\s*(?:N[º°O.]?\s*)?(\d+)", re.I)
_RE_RQA = re.compile(r"RQA\s*(\d+)", re.I)
_PREFIXOS = ("ENC:", "RES:", "RE:", "FW:", "FWD:", "TR:")


def limpar_assunto(assunto: str) -> str:
    s = (assunto or "").strip()
    mudou = True
    while mudou:
        mudou = False
        for p in _PREFIXOS:
            if s.upper().startswith(p):
                s = s[len(p):].strip()
                mudou = True
    return s


def normalizar_numero(txt: Optional[str]) -> Optional[str]:
    """'035620' -> '35620' (para comparar PO/DANFE sem zeros à esquerda)."""
    if not txt:
        return None
    return str(int(txt))


def valor_br(txt: Optional[str]) -> Optional[Decimal]:
    """'7.242,43' -> Decimal('7242.43'); '25000' -> Decimal('25000')."""
    if not txt:
        return None
    t = txt.strip().replace("R$", "").replace(" ", "").rstrip(".,")
    t = t.replace(".", "").replace(",", ".")
    try:
        return Decimal(t).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def brl(v: Decimal) -> str:
    """Decimal('7242.43') -> 'R$ 7.242,43'."""
    sinal = "-" if v < 0 else ""
    inteiro, dec = f"{abs(v):.2f}".split(".")
    grupos = []
    while len(inteiro) > 3:
        grupos.insert(0, inteiro[-3:])
        inteiro = inteiro[:-3]
    grupos.insert(0, inteiro)
    return f"{sinal}R$ {'.'.join(grupos)},{dec}"


def extrair_viagem(texto: str) -> Optional[str]:
    m = _RE_VIAGEM.search((texto or "").upper())
    return m.group(1) + m.group(2) if m else None


def navio_da_viagem(viagem: Optional[str]) -> Optional[str]:
    return NAVIOS.get((viagem or "")[:3])


def primeiro_valor(texto: str) -> Optional[Decimal]:
    m = _RE_VALOR.search(texto or "")
    return valor_br(m.group(1)) if m else None


# --------------------------------------------------------------------------
# E-mail de SOLICITAÇÃO DE RECARGA FLASH
# --------------------------------------------------------------------------
@dataclass
class Recarga:
    assunto: str
    viagem: Optional[str]
    navio: Optional[str]
    valor: Optional[Decimal]
    rqa: Optional[str]
    portador: Optional[str]
    cartao: Optional[str]


def parse_recarga(assunto: str, corpo: str) -> Recarga:
    a = limpar_assunto(assunto)
    au = a.upper()
    viagem = extrair_viagem(au)
    m_navio = re.search(r"AMAZON\s+([A-Z]+)", au)
    navio = f"AMAZON {m_navio.group(1)}" if m_navio else navio_da_viagem(viagem)
    m_port = re.search(r"FLASH\s+([A-ZÀ-Ü]+)\s*-\s*NR", au)
    m_cartao = re.search(r"NR\s*(\d+)", au)
    # RQA: primeiro no corpo da solicitação ("Segue em anexo RQA110686 de carga...")
    m_rqa = _RE_RQA.search(corpo or "") or _RE_RQA.search(a)
    return Recarga(
        assunto=a,
        viagem=viagem,
        navio=navio,
        valor=primeiro_valor(a),
        rqa=m_rqa.group(1) if m_rqa else None,
        portador=m_port.group(1) if m_port else None,
        cartao=m_cartao.group(1) if m_cartao else None,
    )


# --------------------------------------------------------------------------
# E-mail de aprovação do MXM (noreply@mxmwebmanager.com.br)
# --------------------------------------------------------------------------
@dataclass
class PoAprovada:
    po: str               # normalizado, sem zeros à esquerda
    po_original: str      # como veio no e-mail (ex.: 033248)
    valor: Optional[Decimal]
    fornecedor: Optional[str]
    observacao: str
    rqa: Optional[str]
    viagem: Optional[str]
    danfe: Optional[str]  # normalizado


def parse_aprovacao_mxm(corpo: str) -> Optional[PoAprovada]:
    """Lê o corpo (texto) do e-mail 'Status de Aprovação ... Pedido de Compra'."""
    t = corpo or ""
    if not re.search(r"Aprovado para o pedido", t, re.I):
        return None
    m_po = re.search(r"pedido\s+no\.?\s*(\d+)", t, re.I)
    if not m_po:
        return None
    m_valor = re.search(r"Valor:\s*R\$\s*([\d.,]+)", t)
    m_forn = re.search(r"Fornecedor:\s*(.+)", t)
    m_obs = re.search(r"Observa[çc][ãa]o:\s*(.+)", t, re.I)
    obs = m_obs.group(1).strip() if m_obs else ""
    m_rqa = re.search(r"ANTECIPA[ÇC][ÃA]O:\s*RQA\s*(\d+)", t, re.I)
    m_danfe = _RE_DANFE.search(obs)
    return PoAprovada(
        po=normalizar_numero(m_po.group(1)),
        po_original=m_po.group(1),
        valor=valor_br(m_valor.group(1)) if m_valor else None,
        fornecedor=m_forn.group(1).strip() if m_forn else None,
        observacao=obs,
        rqa=m_rqa.group(1) if m_rqa else None,
        viagem=extrair_viagem(obs),
        danfe=normalizar_numero(m_danfe.group(1)) if m_danfe else None,
    )


# --------------------------------------------------------------------------
# Nomes de arquivo nas pastas
# --------------------------------------------------------------------------
@dataclass
class ArquivoDanfe:
    numero: str
    fornecedor: Optional[str]
    data: Optional[str]
    valor: Optional[Decimal]
    viagem: Optional[str]
    nome: str


def parse_nome_danfe(nome: str) -> Optional[ArquivoDanfe]:
    """'ACR26017 - Assai - DANFE 92811 - R$7.242,43 - 04.09.pdf'"""
    base = re.sub(r"\.pdf$", "", nome, flags=re.I)
    if re.match(r"^\s*PO\s*\d", base, re.I):
        return None
    m = _RE_DANFE.search(base)
    if not m:
        return None
    partes = [p.strip() for p in base.split(" - ")]
    fornecedor = None
    if len(partes) > 1 and "DANFE" not in partes[1].upper() and "R$" not in partes[1]:
        fornecedor = partes[1]
    data = None
    if re.fullmatch(r"\d{2}[./]\d{2}(?:[./]\d{2,4})?", partes[-1]):
        data = partes[-1].replace(".", "/")
    return ArquivoDanfe(
        numero=normalizar_numero(m.group(1)),
        fornecedor=fornecedor,
        data=data,
        valor=primeiro_valor(base),
        viagem=extrair_viagem(base),
        nome=nome,
    )


def parse_nome_po(nome: str) -> Optional[str]:
    """'PO035620 - OPS SHP - ...pdf' / 'PO 035618 - ...' -> '35620'"""
    m = re.match(r"^\s*PO\s*(\d+)", nome, re.I)
    return normalizar_numero(m.group(1)) if m else None
