"""Conferência de uma recarga Flash: POs aprovadas x DANFEs x PDFs das POs."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional

from .parse import ArquivoDanfe, PoAprovada, Recarga, brl

TOLERANCIA = Decimal("0.01")


@dataclass
class Item:
    danfe: ArquivoDanfe
    po: PoAprovada
    ref_danfe: object   # referência do arquivo no drive (para anexar)
    ref_po: object


@dataclass
class Problema:
    bloqueante: bool
    texto: str


@dataclass
class Resultado:
    recarga: Recarga
    itens: List[Item] = field(default_factory=list)
    problemas: List[Problema] = field(default_factory=list)

    @property
    def total(self) -> Decimal:
        return sum((i.danfe.valor or Decimal("0") for i in self.itens), Decimal("0"))

    @property
    def saldo(self) -> Optional[Decimal]:
        if self.recarga.valor is None:
            return None
        return self.recarga.valor - self.total

    @property
    def bloqueado(self) -> bool:
        return any(p.bloqueante for p in self.problemas)

    def bloqueia(self, texto: str) -> None:
        self.problemas.append(Problema(True, texto))

    def avisa(self, texto: str) -> None:
        self.problemas.append(Problema(False, texto))


def conferir(
    recarga: Recarga,
    pos_viagem: List[PoAprovada],
    danfes_viagem: Dict[str, tuple],   # nº DANFE -> (ArquivoDanfe, ref)
    pdfs_po: Dict[str, object],        # nº PO -> ref
) -> Resultado:
    """
    pos_viagem:    todas as POs aprovadas no MXM que citam a viagem (de qualquer RQA)
    danfes_viagem: arquivos de DANFE da viagem encontrados na pasta
    pdfs_po:       PDFs de PO encontrados na pasta de POs
    """
    r = Resultado(recarga)

    if not recarga.rqa:
        r.bloqueia("Não achei o número da RQA no e-mail da recarga.")
        return r
    if recarga.valor is None:
        r.bloqueia("Não achei o valor da recarga no assunto do e-mail.")

    # POs desta recarga = aprovadas com 'ANTECIPAÇÃO: RQA <nº>'
    pos = [p for p in pos_viagem if p.rqa == recarga.rqa]
    if not pos:
        r.bloqueia(f"Nenhuma PO aprovada no MXM vinculada à RQA {recarga.rqa}.")
        return r

    por_danfe: Dict[str, List[PoAprovada]] = {}
    for p in pos:
        if not p.danfe:
            r.bloqueia(f"PO {p.po_original}: a observação do MXM não cita o nº da DANFE ({p.observacao}).")
            continue
        por_danfe.setdefault(p.danfe, []).append(p)

    for num, lista in sorted(por_danfe.items()):
        if len(lista) > 1:
            r.bloqueia(f"DANFE {num} tem {len(lista)} POs aprovadas: "
                       + ", ".join(p.po_original for p in lista) + ".")
            continue
        po = lista[0]
        if num not in danfes_viagem:
            r.bloqueia(f"PO {po.po_original} cita a DANFE {num}, que não está na pasta de DANFEs.")
            continue
        danfe, ref_danfe = danfes_viagem[num]
        if po.po not in pdfs_po:
            r.bloqueia(f"PDF da PO {po.po_original} (DANFE {num}) não está na pasta de POs.")
            continue
        if danfe.valor is None:
            r.bloqueia(f"DANFE {num}: valor não consta no nome do arquivo ({danfe.nome}).")
            continue
        if po.valor is not None and abs(po.valor - danfe.valor) > TOLERANCIA:
            r.bloqueia(f"DANFE {num} vale {brl(danfe.valor)}, mas a PO {po.po_original} foi aprovada com {brl(po.valor)}.")
            continue
        r.itens.append(Item(danfe, po, ref_danfe, pdfs_po[po.po]))

    # DANFEs da viagem que ainda não têm PO aprovada em nenhuma RQA
    danfes_com_po = {p.danfe for p in pos_viagem if p.danfe}
    orfas = sorted(n for n in danfes_viagem if n not in danfes_com_po)
    for n in orfas:
        d = danfes_viagem[n][0]
        r.avisa(f"DANFE {n} ({d.fornecedor or '?'}, {brl(d.valor) if d.valor else 's/ valor'}) está na pasta "
                f"da viagem mas ainda não tem PO aprovada — pode ser desta recarga.")

    saldo = r.saldo
    if saldo is not None and saldo < 0:
        r.avisa(f"Total das DANFEs ({brl(r.total)}) supera a recarga ({brl(recarga.valor)}).")
    return r
