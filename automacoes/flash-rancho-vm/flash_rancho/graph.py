"""Cliente mínimo do Microsoft Graph (app-only / client credentials).

Permissões de APLICATIVO necessárias no app do Azure:
  - Mail.ReadWrite   (ler e-mails, criar rascunhos, mudar categoria)
  - Files.Read.All ou Sites.Read.All  (ler as pastas de DANFEs e POs)
Mail.Send NÃO é necessário: a rotina só cria rascunhos.
"""
from __future__ import annotations

import base64
import time
from typing import Dict, Iterator, List, Optional
from urllib.parse import quote

import requests

GRAPH = "https://graph.microsoft.com/v1.0"
LIMITE_ANEXO_SIMPLES = 3 * 1024 * 1024  # acima disso, upload session
PEDACO_UPLOAD = 3 * 1024 * 1024         # múltiplo de 320 KiB


class Graph:
    def __init__(self, tenant_id: str, client_id: str, client_secret: str):
        self._cred = (tenant_id, client_id, client_secret)
        self._token: Optional[str] = None
        self._expira = 0.0
        self.s = requests.Session()

    # ------------------------------------------------------------------ base
    def _auth(self) -> Dict[str, str]:
        if not self._token or time.time() > self._expira - 60:
            tenant, cid, secret = self._cred
            r = requests.post(
                f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
                data={"client_id": cid, "client_secret": secret,
                      "scope": "https://graph.microsoft.com/.default",
                      "grant_type": "client_credentials"},
                timeout=30,
            )
            r.raise_for_status()
            j = r.json()
            self._token, self._expira = j["access_token"], time.time() + int(j["expires_in"])
        return {"Authorization": f"Bearer {self._token}"}

    def req(self, metodo: str, url: str, **kw) -> requests.Response:
        if not url.startswith("http"):
            url = GRAPH + url
        headers = {**self._auth(), **kw.pop("headers", {})}
        for tentativa in range(5):
            r = self.s.request(metodo, url, headers=headers, timeout=120, **kw)
            if r.status_code in (429, 503, 504):
                time.sleep(int(r.headers.get("Retry-After", 2 ** tentativa)))
                continue
            if r.status_code >= 400:
                raise RuntimeError(f"Graph {metodo} {url} -> {r.status_code}: {r.text[:500]}")
            return r
        r.raise_for_status()
        return r

    def paginar(self, url: str, **kw) -> Iterator[dict]:
        while url:
            j = self.req("GET", url, **kw).json()
            yield from j.get("value", [])
            url = j.get("@odata.nextLink")
            kw.pop("params", None)

    # ---------------------------------------------------------------- e-mail
    _SEL = "id,subject,categories,sentDateTime,receivedDateTime,from,body,hasAttachments"
    _TEXTO = {"Prefer": 'outlook.body-content-type="text"'}

    def mensagens_com_categoria(self, caixa: str, categoria: str) -> List[dict]:
        cat = categoria.replace("'", "''")
        return list(self.paginar(
            f"/users/{caixa}/messages",
            params={"$filter": f"categories/any(c:c eq '{cat}')", "$select": self._SEL, "$top": "50"},
            headers=self._TEXTO,
        ))

    def buscar_mensagens(self, caixa: str, termo: str, limite: int = 500) -> List[dict]:
        out = []
        for m in self.paginar(f"/users/{caixa}/messages",
                              params={"$search": f'"{termo}"', "$select": self._SEL, "$top": "50"},
                              headers=self._TEXTO):
            out.append(m)
            if len(out) >= limite:
                break
        return out

    def definir_categorias(self, caixa: str, msg_id: str, categorias: List[str]) -> None:
        self.req("PATCH", f"/users/{caixa}/messages/{msg_id}", json={"categories": categorias})

    def criar_encaminhamento(self, caixa: str, msg_id: str) -> dict:
        return self.req("POST", f"/users/{caixa}/messages/{msg_id}/createForward", json={}).json()

    def corpo_html(self, caixa: str, msg_id: str) -> str:
        j = self.req("GET", f"/users/{caixa}/messages/{msg_id}", params={"$select": "body"}).json()
        return j["body"]["content"]

    def atualizar_mensagem(self, caixa: str, msg_id: str, dados: dict) -> None:
        self.req("PATCH", f"/users/{caixa}/messages/{msg_id}", json=dados)

    def criar_rascunho(self, caixa: str, assunto: str, html: str, para: List[str]) -> dict:
        return self.req("POST", f"/users/{caixa}/messages", json={
            "subject": assunto,
            "body": {"contentType": "HTML", "content": html},
            "toRecipients": destinatarios(para),
        }).json()

    def anexar(self, caixa: str, msg_id: str, nome: str, conteudo: bytes) -> None:
        if len(conteudo) <= LIMITE_ANEXO_SIMPLES:
            self.req("POST", f"/users/{caixa}/messages/{msg_id}/attachments", json={
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": nome,
                "contentBytes": base64.b64encode(conteudo).decode(),
            })
            return
        sessao = self.req("POST", f"/users/{caixa}/messages/{msg_id}/attachments/createUploadSession", json={
            "AttachmentItem": {"attachmentType": "file", "name": nome, "size": len(conteudo)},
        }).json()
        url, total = sessao["uploadUrl"], len(conteudo)
        for ini in range(0, total, PEDACO_UPLOAD):
            fim = min(ini + PEDACO_UPLOAD, total) - 1
            r = requests.put(url, data=conteudo[ini:fim + 1], timeout=300, headers={
                "Content-Length": str(fim - ini + 1),
                "Content-Range": f"bytes {ini}-{fim}/{total}",
            })
            if r.status_code >= 400:
                raise RuntimeError(f"Upload de anexo {nome} falhou: {r.status_code} {r.text[:300]}")

    # ---------------------------------------------------------------- drive
    def pasta(self, cfg: dict) -> tuple[str, str]:
        """Resolve {'tipo': 'usuario'|'site', ...} -> (drive_id, item_id da pasta)."""
        if cfg["tipo"] == "usuario":
            drive_id = self.req("GET", f"/users/{cfg['dono']}/drive").json()["id"]
        elif cfg["tipo"] == "site":
            site = self.req("GET", f"/sites/{cfg['site']}").json()["id"]
            if cfg.get("biblioteca"):
                drives = self.req("GET", f"/sites/{site}/drives").json()["value"]
                drive_id = next(d["id"] for d in drives if d["name"] == cfg["biblioteca"])
            else:
                drive_id = self.req("GET", f"/sites/{site}/drive").json()["id"]
        else:
            raise ValueError(f"tipo de pasta desconhecido: {cfg['tipo']}")
        caminho = quote(cfg["caminho"].strip("/"))
        item_id = self.req("GET", f"/drives/{drive_id}/root:/{caminho}").json()["id"]
        return drive_id, item_id

    def listar_arquivos(self, drive_id: str, item_id: str, profundidade: int = 3) -> List[dict]:
        """Arquivos da pasta e subpastas (até `profundidade` níveis)."""
        out = []
        for it in self.paginar(f"/drives/{drive_id}/items/{item_id}/children",
                               params={"$select": "id,name,size,folder,file,lastModifiedDateTime", "$top": "200"}):
            if "folder" in it:
                if profundidade > 0:
                    out.extend(self.listar_arquivos(drive_id, it["id"], profundidade - 1))
            else:
                it["driveId"] = drive_id
                out.append(it)
        return out

    def baixar(self, drive_id: str, item_id: str) -> bytes:
        return self.req("GET", f"/drives/{drive_id}/items/{item_id}/content").content


def destinatarios(emails: List[str]) -> List[dict]:
    return [{"emailAddress": {"address": e}} for e in emails if e]
