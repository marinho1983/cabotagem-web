"""
Robô Qive (antiga Arquivei): cliente da API oficial + leitura dos XMLs.

Credenciais via variáveis de ambiente (painel Qive > Configurações > API):
  QIVE_API_ID, QIVE_API_KEY
  QIVE_BASE_URL (opcional, padrão https://api.arquivei.com.br)
"""
import base64
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal, InvalidOperation

# tipo interno -> endpoint da API
ENDPOINTS = {
    "NFE": "/v1/nfe/received",   # NF-e recebidas (empresa é destinatária)
    "CTE": "/v1/cte/taker",      # CT-e em que a empresa é tomadora (frete)
}

PAGE_LIMIT = 50  # máximo aceito pela API por página


class QiveError(Exception):
    pass


def is_configured():
    return bool(os.getenv("QIVE_API_ID") and os.getenv("QIVE_API_KEY"))


def _base_url():
    return os.getenv("QIVE_BASE_URL", "https://api.arquivei.com.br").rstrip("/")


def _get(path, params):
    if not is_configured():
        raise QiveError("Credenciais do Qive não configuradas (QIVE_API_ID / QIVE_API_KEY).")

    url = f"{_base_url()}{path}?{urllib.parse.urlencode(params, doseq=True)}"
    req = urllib.request.Request(url, headers={
        "X-API-ID": os.getenv("QIVE_API_ID"),
        "X-API-KEY": os.getenv("QIVE_API_KEY"),
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")[:300]
        raise QiveError(f"Qive respondeu HTTP {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise QiveError(f"Falha de conexão com o Qive: {e.reason}") from e


def _decode_items(payload):
    """Retorna lista de (access_key, xml_str) a partir da resposta da API."""
    out = []
    for item in payload.get("data") or []:
        key = item.get("access_key")
        raw = item.get("xml")
        if not key or not raw:
            continue
        try:
            xml_str = base64.b64decode(raw).decode("utf-8", errors="ignore")
        except Exception:
            continue
        out.append((key, xml_str))
    return out


def _cursor_from(next_url):
    if not next_url:
        return None
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(next_url).query)
    vals = qs.get("cursor")
    return vals[0] if vals else None


def fetch_page(doc_type, cursor=None):
    """Busca uma página de documentos. Retorna (itens, próximo_cursor)."""
    params = {"limit": PAGE_LIMIT}
    if cursor:
        params["cursor"] = cursor
    payload = _get(ENDPOINTS[doc_type], params)
    items = _decode_items(payload)
    next_cursor = _cursor_from((payload.get("page") or {}).get("next")) or cursor
    return items, next_cursor


def fetch_by_keys(doc_type, access_keys):
    """Consulta direta por chave de acesso (até 50 por chamada)."""
    keys = [k for k in access_keys if k][:PAGE_LIMIT]
    if not keys:
        return []
    payload = _get(ENDPOINTS[doc_type], {"access_key[]": keys})
    return _decode_items(payload)


def doc_type_from_key(access_key):
    """Modelo do documento fica nas posições 21-22 da chave (55=NF-e, 57=CT-e)."""
    model = access_key[20:22] if len(access_key) == 44 else ""
    return "CTE" if model == "57" else "NFE"


def clean_key(txt):
    return re.sub(r"\D", "", txt or "")


# -----------------------------
# Leitura do XML
# -----------------------------
def _strip_ns(root):
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return root


def _txt(node, path):
    if node is None:
        return None
    el = node.find(path)
    return el.text.strip() if el is not None and el.text else None


def _dec(v):
    try:
        return Decimal(v) if v else None
    except (InvalidOperation, ValueError):
        return None


def _date(v):
    # dhEmi: 2024-05-10T10:30:00-03:00 | dEmi: 2024-05-10
    if not v:
        return None
    try:
        y, m, d = v[:10].split("-")
        return date(int(y), int(m), int(d))
    except Exception:
        return None


def _party(node):
    if node is None:
        return None, None
    return _txt(node, "CNPJ") or _txt(node, "CPF"), _txt(node, "xNome")


def parse_xml(access_key, xml_str):
    """Extrai os campos principais de NF-e ou CT-e. Nunca levanta exceção."""
    data = {
        "access_key": access_key,
        "doc_type": doc_type_from_key(access_key),
        "number": None, "series": None, "issue_date": None,
        "issuer_cnpj": None, "issuer_name": None,
        "recipient_cnpj": None, "recipient_name": None,
        "total_value": None, "summary": None,
    }
    try:
        root = _strip_ns(ET.fromstring(xml_str.encode("utf-8")))
    except ET.ParseError:
        return data

    inf_nfe = root.find(".//infNFe")
    inf_cte = root.find(".//infCte")

    if inf_nfe is not None:
        data["doc_type"] = "NFE"
        ide = inf_nfe.find("ide")
        data["number"] = _txt(ide, "nNF")
        data["series"] = _txt(ide, "serie")
        data["issue_date"] = _date(_txt(ide, "dhEmi") or _txt(ide, "dEmi"))
        data["issuer_cnpj"], data["issuer_name"] = _party(inf_nfe.find("emit"))
        data["recipient_cnpj"], data["recipient_name"] = _party(inf_nfe.find("dest"))
        data["total_value"] = _dec(_txt(inf_nfe, "total/ICMSTot/vNF"))
        prods = [p.text.strip() for p in inf_nfe.findall("det/prod/xProd") if p.text]
        data["summary"] = "; ".join(prods)[:500] or None

    elif inf_cte is not None:
        data["doc_type"] = "CTE"
        ide = inf_cte.find("ide")
        data["number"] = _txt(ide, "nCT")
        data["series"] = _txt(ide, "serie")
        data["issue_date"] = _date(_txt(ide, "dhEmi") or _txt(ide, "dEmi"))
        data["issuer_cnpj"], data["issuer_name"] = _party(inf_cte.find("emit"))
        data["recipient_cnpj"], data["recipient_name"] = _party(inf_cte.find("dest"))
        data["total_value"] = _dec(_txt(inf_cte, "vPrest/vTPrest"))
        origem = _txt(ide, "xMunIni")
        destino = _txt(ide, "xMunFim")
        produto = _txt(inf_cte, "infCTeNorm/infCarga/proPred")
        partes = [f"{origem or '?'} -> {destino or '?'}"] + ([produto] if produto else [])
        data["summary"] = " | ".join(partes)[:500]

    return data
