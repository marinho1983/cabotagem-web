# Flash Rancho (VM) — prestação de contas das antecipações de rancho

Rotina Python que roda na VM (ao lado do robô `triagem-email`) e **deixa pronto, em Rascunhos da caixa
OPS FIN, o e-mail de envio das DANFEs** que prestam contas de uma recarga Flash.
Nada é enviado automaticamente: você abre o rascunho, confere e clica **Enviar**.

## Como funciona

```
Você (Outlook)                         VM (a cada 15 min)
──────────────                         ─────────────────────────────────────────────────────────
E-mail "SOLICITAÇÃO DE RECARGA FLASH"  1. Acha e-mails com a categoria "FLASH - PRESTAR CONTAS"
 → categoria "FLASH - PRESTAR CONTAS"  2. Lê viagem, valor e RQA do e-mail
                                       3. Busca aprovações do MXM com "ANTECIPAÇÃO: RQA <nº>"
                                       4. Acha as DANFEs (pasta DANFEs) e os PDFs das POs (pasta POs)
                                       5. Confere DANFE × PO × valor
                                       6a. OK  → rascunho pronto + categoria "FLASH - RASCUNHO PRONTO"
                                       6b. Erro → relatório em Rascunhos (sua caixa) + "FLASH - PENDENCIA"
```

**De onde vem cada dado**

| Dado | Origem |
|---|---|
| Viagem, navio, valor da recarga, portador | Assunto do e-mail da recarga |
| Nº da RQA | Corpo do e-mail da recarga (`Segue em anexo RQA110686 ...`) |
| POs da recarga (nº, valor, DANFE) | E-mails de aprovação do MXM (`noreply@mxmwebmanager.com.br`): observação + `ANTECIPAÇÃO: RQA <nº>` |
| PDF e valor da DANFE | Pasta de DANFEs: `ACR26017 - Assai - DANFE 92811 - R$7.242,43 - 04.09.pdf` |
| PDF da PO | Pasta de POs: arquivo começando com `PO035620...` |

**Conferências** (⛔ bloqueia o rascunho · ⚠️ só avisa)

- ⛔ Nenhuma PO aprovada vinculada à RQA
- ⛔ PO sem nº de DANFE na observação do MXM
- ⛔ DANFE com mais de uma PO aprovada (ex.: 93186 com PO 035612 e 035615 no Courage)
- ⛔ PO cita DANFE que não está na pasta
- ⛔ PDF da PO não está na pasta de POs
- ⛔ Valor da DANFE (nome do arquivo) diferente do valor aprovado da PO
- ⚠️ DANFE da viagem na pasta sem PO aprovada (ex.: 51883 Atacadão)
- ⚠️ Total das DANFEs acima da recarga (saldo negativo)

**Rascunho gerado** — encaminhamento da solicitação de recarga:
- **Para:** Jessica, Protocolo Fiscal, Contas a Pagar, Willyanson, Luiz Sanchez · **Cc:** OPS FIN
- Corpo padrão + tabela DANFE · Fornecedor · Data · Valor · PO + Total, Recarga e **Saldo no cartão**
- Anexos: todas as DANFEs e PDFs das POs (arquivos > 3 MB via upload session)

---

## Implantação na VM

### 1. Permissões do app no Azure
Use o mesmo app do robô de triagem (ou crie outro). Em *Azure Portal › App registrations › (app) › API permissions*,
permissões de **Aplicativo** (não delegadas) + **Grant admin consent**:

| Permissão | Para quê |
|---|---|
| `Mail.ReadWrite` | ler e-mails de ops.fin e mlf, criar rascunhos, mudar categorias |
| `Sites.Read.All` (ou `Files.Read.All`) | ler as pastas de DANFEs e POs |

`Mail.Send` **não** é necessário. Recomendado pedir à TI uma *Application Access Policy* limitando o app às caixas
da OPS FIN e a sua.

### 2. Copiar e instalar
```bash
cd /home/mlf
git clone https://github.com/marinho1983/cabotagem-web.git   # ou git pull, se já existir
cp -r cabotagem-web/automacoes/flash-rancho-vm /home/mlf/flash-rancho
cd /home/mlf/flash-rancho
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env            # preencha TENANT_ID, CLIENT_ID, CLIENT_SECRET (mesmos do triagem-email)
cp config.example.json config.json
chmod 600 .env
```

### 3. Ajustar `config.json`
Preencha as duas pastas:

- **Pasta em SharePoint** (URL `https://posidonia.sharepoint.com/sites/Operacoes/Documentos Compartilhados/FLASH/DANFES`):
  ```json
  "pasta_danfes": {"tipo": "site", "site": "posidonia.sharepoint.com:/sites/Operacoes",
                   "biblioteca": "Documentos", "caminho": "FLASH/DANFES"}
  ```
  `biblioteca` é o nome da biblioteca como aparece no site (em PT costuma ser "Documentos"). O `caminho` é a partir dela.
- **Pasta no OneDrive de alguém**:
  ```json
  "pasta_pos": {"tipo": "usuario", "dono": "SEU-EMAIL", "caminho": "Documentos/POs"}
  ```

Subpastas são lidas até 3 níveis (`profundidade`).

### 4. Testar sem gravar nada
Marque um e-mail de recarga com a categoria e rode:
```bash
.venv/bin/python -m flash_rancho.main --simular
```
A saída mostra cada DANFE conferida, os problemas, o total e o saldo. Nada é criado nem alterado.

### 5. Agendar
```bash
crontab -e
# a cada 15 min, seg-sex, 7h às 20h (horário da VM)
*/15 7-20 * * 1-5 cd /home/mlf/flash-rancho && .venv/bin/python -m flash_rancho.main >> cron.log 2>&1
```

### 6. Criar as categorias no Outlook (uma vez, na caixa OPS FIN)
`Página Inicial › Categorizar › Todas as categorias › Nova`: crie exatamente
**FLASH - PRESTAR CONTAS**, **FLASH - RASCUNHO PRONTO** e **FLASH - PENDENCIA**.

---

## Uso no dia a dia

1. Salve as DANFEs na pasta de DANFEs com o nome padrão e os PDFs das POs na pasta de POs.
2. Quando as compras daquela recarga estiverem concluídas e as POs aprovadas no MXM,
   aplique a categoria **FLASH - PRESTAR CONTAS** no e-mail da **SOLICITAÇÃO DE RECARGA FLASH**.
3. Em até 15 min:
   - **FLASH - RASCUNHO PRONTO** → abra *Rascunhos* da OPS FIN, confira e envie.
   - **FLASH - PENDENCIA** → abra o relatório `[Flash Rancho] Pendências ...` nos seus Rascunhos,
     corrija e aplique de novo **FLASH - PRESTAR CONTAS**.

Envio parcial: se chegar DANFE nova depois, aplique a categoria de novo. **Atenção:** a rotina monta o e-mail
com todas as DANFEs da RQA; retire do rascunho as que já foram enviadas antes (controle de envio parcial é a
próxima melhoria).

## Próximos passos (combinados)

- **Conclusão automática**: dispensar a categoria e gerar o rascunho sozinha quando a RQA estiver fechada
  (todas as DANFEs com PO aprovada e sem arquivo novo há X horas).
- **Etapa 1 — Solicitação de recarga**: gerar o rascunho para a Jessica a partir do e-mail de
  "Solicitação de Depósito" da operação (depende de saber onde fica o PDF da RQA).
- **Controle de envio parcial** e **log de saldo Flash por RQA** (base para o encontro de contas).

## Testes
```bash
pip install pytest && python -m pytest -q
```
Os testes usam textos reais (e-mails de set/2026), inclusive o caso do Courage ACR26017 de 21/09.
