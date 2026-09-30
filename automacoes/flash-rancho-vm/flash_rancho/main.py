"""Rotina Flash Rancho (VM).

Ciclo por execução (agendar no cron a cada 15 min):
  1. Procura, na caixa OPS FIN, e-mails de SOLICITAÇÃO DE RECARGA FLASH marcados
     com a categoria de sinal (padrão: "FLASH - PRESTAR CONTAS").
  2. Para cada um: lê viagem, valor e RQA; busca as POs aprovadas no MXM
     (e-mails noreply@mxmwebmanager) vinculadas à RQA; localiza as DANFEs e os
     PDFs das POs nas pastas do OneDrive/SharePoint; confere tudo.
  3. Sem pendências bloqueantes: cria o RASCUNHO do encaminhamento para
     Jessica, Protocolo, Contas a Pagar, Will e Sanchez (Cc OPS FIN), com
     tabela, saldo e todos os anexos. Troca a categoria para "FLASH - RASCUNHO PRONTO".
  4. Com pendências: não cria o rascunho, troca a categoria para
     "FLASH - PENDENCIA" e deixa um rascunho-relatório para você.

Uso:
  python -m flash_rancho.main              # execução normal
  python -m flash_rancho.main --simular    # só lê e mostra a conferência (não grava nada)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List

from .conferencia import Resultado, conferir
from .emails import corpo_prestacao, corpo_relatorio
from .graph import Graph, destinatarios
from .parse import (PoAprovada, brl, parse_aprovacao_mxm, parse_nome_danfe,
                    parse_nome_po, parse_recarga)

RAIZ = Path(__file__).resolve().parent.parent
log = logging.getLogger("flash_rancho")


# ---------------------------------------------------------------- config
def carregar_env(caminho: Path) -> None:
    """Lê um .env simples (CHAVE=valor) sem sobrescrever variáveis já definidas."""
    if not caminho.exists():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#") and "=" in linha:
            k, v = linha.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def carregar_config() -> dict:
    carregar_env(RAIZ / ".env")
    cfg = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))
    for chave in ("TENANT_ID", "CLIENT_ID", "CLIENT_SECRET"):
        if not os.environ.get(chave):
            sys.exit(f"Variável {chave} não definida (.env ou ambiente).")
    return cfg


# ---------------------------------------------------------------- coleta
def pos_aprovadas_da_viagem(g: Graph, cfg: dict, viagem: str) -> List[PoAprovada]:
    """Aprovações do MXM que citam a viagem. Mantém a mais recente de cada PO."""
    remetente = cfg["remetente_mxm"].lower()
    msgs = g.buscar_mensagens(cfg["caixa_mxm"], viagem)
    msgs.sort(key=lambda m: m.get("receivedDateTime", ""))
    por_po: Dict[str, PoAprovada] = {}
    for m in msgs:
        if (m.get("from", {}).get("emailAddress", {}).get("address", "").lower() != remetente):
            continue
        p = parse_aprovacao_mxm(m["body"]["content"])
        if p and p.viagem == viagem:
            por_po[p.po] = p
    return list(por_po.values())


def arquivos(g: Graph, cfg_pasta: dict) -> List[dict]:
    drive_id, item_id = g.pasta(cfg_pasta)
    return g.listar_arquivos(drive_id, item_id, cfg_pasta.get("profundidade", 3))


def danfes_da_viagem(lista: List[dict], viagem: str) -> Dict[str, tuple]:
    out: Dict[str, tuple] = {}
    for it in lista:
        d = parse_nome_danfe(it["name"])
        if d and d.viagem == viagem:
            if d.numero in out:
                log.warning("DANFE %s duplicada na pasta: %s / %s", d.numero, out[d.numero][0].nome, d.nome)
            out[d.numero] = (d, it)
    return out


def pdfs_de_po(lista: List[dict]) -> Dict[str, dict]:
    out: Dict[str, dict] = {}
    for it in lista:
        if it["name"].lower().endswith(".pdf"):
            po = parse_nome_po(it["name"])
            if po:
                out[po] = it
    return out


# ---------------------------------------------------------------- saída
def criar_rascunho_prestacao(g: Graph, cfg: dict, msg_id: str, r: Resultado) -> str:
    caixa = cfg["caixa_opsfin"]
    rascunho = g.criar_encaminhamento(caixa, msg_id)
    rid = rascunho["id"]
    html = g.corpo_html(caixa, rid)
    novo = corpo_prestacao(r)
    i = html.lower().find("<body")
    if i >= 0:
        j = html.find(">", i) + 1
        html = html[:j] + novo + html[j:]
    else:
        html = novo + html
    d = cfg["destinatarios_prestacao"]
    g.atualizar_mensagem(caixa, rid, {
        "body": {"contentType": "HTML", "content": html},
        "toRecipients": destinatarios(d["para"]),
        "ccRecipients": destinatarios(d["cc"]),
    })
    for item in r.itens:
        for ref in (item.ref_danfe, item.ref_po):
            conteudo = g.baixar(ref["driveId"], ref["id"])
            g.anexar(caixa, rid, ref["name"], conteudo)
    return rid


def processar(g: Graph, cfg: dict, msg: dict, cache: dict, simular: bool) -> None:
    rc = parse_recarga(msg["subject"], msg["body"]["content"])
    log.info("Recarga: %s | viagem %s | RQA %s | %s", rc.assunto, rc.viagem, rc.rqa,
             brl(rc.valor) if rc.valor is not None else "-")
    if not rc.viagem:
        log.error("Viagem não identificada no assunto; ignorando.")
        return

    if "danfes" not in cache:
        cache["danfes"] = arquivos(g, cfg["pasta_danfes"])
        cache["pos"] = arquivos(g, cfg["pasta_pos"])
    r = conferir(
        rc,
        pos_aprovadas_da_viagem(g, cfg, rc.viagem),
        danfes_da_viagem(cache["danfes"], rc.viagem),
        pdfs_de_po(cache["pos"]),
    )
    for i in r.itens:
        log.info("  OK  DANFE %-8s %-22s %12s  PO %s", i.danfe.numero, (i.danfe.fornecedor or "")[:22],
                 brl(i.danfe.valor), i.po.po_original)
    for p in r.problemas:
        log.warning("  %s %s", "BLOQ" if p.bloqueante else "AVISO", p.texto)
    log.info("  Total %s | Saldo %s", brl(r.total), brl(r.saldo) if r.saldo is not None else "-")

    if simular:
        return

    cats = cfg["categorias"]
    caixa = cfg["caixa_opsfin"]
    outras = [c for c in msg.get("categories", []) if c not in cats.values()]
    criado = False
    if not r.bloqueado:
        rid = criar_rascunho_prestacao(g, cfg, msg["id"], r)
        criado = True
        log.info("  Rascunho criado: %s", rid)
    if r.problemas:
        g.criar_rascunho(
            cfg["caixa_relatorio"],
            f"[Flash Rancho] {'Avisos' if criado else 'Pendências'} {rc.viagem} · RQA {rc.rqa}",
            corpo_relatorio(r, criado),
            [cfg["caixa_relatorio"]],
        )
    g.definir_categorias(caixa, msg["id"], outras + [cats["pronto" if criado else "pendencia"]])


def main() -> None:
    ap = argparse.ArgumentParser(description="Flash Rancho — prestação de contas das DANFEs")
    ap.add_argument("--simular", action="store_true", help="não cria rascunhos nem muda categorias")
    args = ap.parse_args()

    cfg = carregar_config()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(RAIZ / "flash_rancho.log", encoding="utf-8")],
    )
    g = Graph(os.environ["TENANT_ID"], os.environ["CLIENT_ID"], os.environ["CLIENT_SECRET"])

    sinalizadas = g.mensagens_com_categoria(cfg["caixa_opsfin"], cfg["categorias"]["sinal"])
    # a mesma recarga pode estar em Itens Enviados e na Caixa de Entrada (Cc ops.fin): processa 1 vez por assunto
    vistas = set()
    cache: dict = {}
    for msg in sorted(sinalizadas, key=lambda m: m.get("sentDateTime") or ""):
        chave = msg["subject"].upper().replace("ENC:", "").replace("RE:", "").strip()
        if chave in vistas:
            if not args.simular:
                outras = [c for c in msg.get("categories", []) if c != cfg["categorias"]["sinal"]]
                g.definir_categorias(cfg["caixa_opsfin"], msg["id"], outras)
            continue
        vistas.add(chave)
        try:
            processar(g, cfg, msg, cache, args.simular)
        except Exception:
            log.exception("Falha ao processar: %s", msg.get("subject"))
    if not sinalizadas:
        log.info("Nenhuma recarga sinalizada com '%s'.", cfg["categorias"]["sinal"])


if __name__ == "__main__":
    main()
