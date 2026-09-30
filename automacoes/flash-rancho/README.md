# Flash Rancho — da solicitação da recarga à prestação de contas

Macro do Outlook (desktop, Windows) para o ciclo de **antecipação de rancho via cartão Flash**:

```
Operação (Ana)                OPS FIN                              OPS FIN
"Solicitação de Depósito" ──► ETAPA 1: Solicitação de Recarga ──► ETAPA 2: Prestação de contas
 planilha + valor + ETB        Jessica + RQA anexada                DANFEs + POs → Protocolo,
                                                                    Contas a Pagar, Will, Sanchez
```

Cada **recarga (RQA)** tem sua própria prestação de contas. A mesma viagem pode ter várias recargas
(ex.: ACR26017 teve R$ 25.000,00 de rancho, R$ 460,00 e R$ 1.400,00 de material de limpeza).

---

## 1. Instalação (uma vez)

1. **Liberar macros no Outlook**
   `Arquivo > Opções > Central de Confiabilidade > Configurações da Central de Confiabilidade > Configurações de Macro`
   → marque **"Notificações para todas as macros"** → OK → **feche e abra o Outlook**.
   *Se a opção estiver bloqueada (cinza), a política da empresa impede macros: é preciso pedir à TI.*

2. **Importar o módulo**
   - No Outlook, pressione **Alt + F11** (abre o editor VBA).
   - `Arquivo > Importar arquivo...` → escolha **`ModFlashRancho.bas`**.
   - No painel da esquerda aparece `Módulos > ModFlashRancho`. Dê dois cliques.

3. **Ajustar a CONFIGURAÇÃO** (topo do módulo)

   | Constante | O que é | Padrão |
   |---|---|---|
   | `PASTA_RAIZ` | Pasta base das recargas e do log | `C:\FLASH` |
   | `NOME_REMETENTE` | Seu nome na saudação "Jessica/**Mario**" | `Mario` |
   | `PORTADOR_PADRAO` / `CARTAO_PADRAO` | Portador e cartão sugeridos | `THIAGO` / `85866820` |
   | `DIAS_LIBERACAO` | Dias de liberação a partir do dia seguinte ao ETB | `7` |
   | `ENVIAR_COMO_OPSFIN` | Envia em nome de ops.fin@ | `True` |
   | `EMAIL_...` | Destinatários fixos | Jessica, Protocolo, Contas a Pagar, Will, Sanchez, OPS FIN |

4. **Salvar**: `Ctrl + S` no editor VBA. Feche o editor.

5. **Criar os botões na faixa de opções**
   `Arquivo > Opções > Personalizar Faixa de Opções`
   - À direita, selecione a guia **Página Inicial** → **Novo Grupo** → Renomear para **Flash**.
   - À esquerda, em "Escolher comandos em", selecione **Macros**.
   - Adicione `Project1.Flash1_SolicitarRecarga` e `Project1.Flash2_PrestarContasDanfes` ao grupo **Flash**.
   - Renomeie para **"1 · Solicitar Recarga"** e **"2 · Prestar Contas"** e escolha um ícone → OK.

6. **Criar a pasta** `C:\FLASH` (ou a que você definiu em `PASTA_RAIZ`).

---

## 2. Organização das pastas e nomes dos arquivos

Uma pasta por recarga:

```
C:\FLASH\
  FLASH_LOG.csv                      ← criado automaticamente
  ACR26017\
    RQA110686\                       ← recarga de R$ 25.000,00
      OPS SHP - RQA 110686 - AMAZON COURAGE - @ALU - ACR26017 - RANCHO COMPLEMENTAR SETEMBRO.pdf
      ACR26017 - Assai - DANFE 92811 - R$7.242,43 - 04.09.pdf
      PO035620 - OPS SHP - AMAZON COURAGE - @ALUMAR - ACR26017 - DANFE 92811 - RANCHO.pdf
      ...
    RQA110700\                       ← outra recarga da mesma viagem
```

**Padrão obrigatório dos nomes** (é o que permite a conferência automática):

| Arquivo | Padrão | Exemplo |
|---|---|---|
| DANFE | `VIAGEM - Fornecedor - DANFE nº - R$valor - dd.mm.pdf` | `ACR26017 - Assai - DANFE 92811 - R$7.242,43 - 04.09.pdf` |
| PO | começa com `PO` + nº e contém `DANFE nº` | `PO035620 - OPS SHP - AMAZON COURAGE - @ALUMAR - ACR26017 - DANFE 92811 - RANCHO.pdf` |
| RQA | contém `RQA nº` | `OPS SHP - RQA 110686 - ....pdf` |

Arquivos fora do padrão (ex.: `AC2DF2~1.PDF`) **não são anexados** e aparecem no aviso — renomeie e rode de novo.
Se a DANFE não tiver o valor no nome, a macro pergunta o valor.

---

## 3. Uso

### Etapa 1 — Solicitar Recarga
1. Salve o PDF da RQA (gerada no MXM) na pasta da recarga.
2. No Outlook, **selecione o e-mail "Solicitação de Depósito"** enviado pela operação.
3. Clique em **"1 · Solicitar Recarga"** e confirme cada campo (já vêm preenchidos):
   viagem → navio → referência (RANCHO MENSAL/COMPLEMENTAR + mês) → **valor da recarga** → **nº da RQA** →
   portador → cartão → período (dia seguinte ao ETB, por 7 dias) → pasta da RQA.
4. O e-mail abre pronto (encaminhando o pedido da operação, com a planilha dela):
   - **Para:** Jessica · **Cc:** OPS FIN, Contas a Pagar
   - **Assunto:** `OPS SHP - SOLICITAÇÃO DE RECARGA FLASH - FLASH THIAGO - NR 85866820 - AMAZON COURAGE - ACR26017 - R$ 25.000,00`
   - Corpo com portador, cartão, valor e período + RQA anexada.
5. Confira e clique **Enviar**.

### Etapa 2 — Prestar Contas (DANFEs)
1. Salve na pasta da recarga todas as **DANFEs** e as **POs** geradas no MXM (uma PO por DANFE).
2. **Selecione o e-mail da "SOLICITAÇÃO DE RECARGA FLASH"** daquela recarga.
3. Clique em **"2 · Prestar Contas"**, confirme viagem e valor e escolha a pasta da recarga.
4. A macro faz a **conferência** e mostra o resumo:
   - DANFE **sem PO**
   - DANFE com **mais de uma PO**
   - PO que cita uma DANFE que **não está na pasta**
   - DANFE de **outra viagem**
   - DANFE **já prestada** antes (pelo log)
   - arquivos **fora do padrão**
   - **Recarga × Total das DANFEs × Saldo no cartão**
5. O e-mail abre pronto (encaminhando a solicitação de recarga):
   - **Para:** Jessica, Protocolo Fiscal, Contas a Pagar, Willyanson, Luiz Sanchez · **Cc:** OPS FIN
   - Corpo padrão (Protocolo: POs para atendimento / Contas a Pagar: ciência / Will e Sanchez: DANFEs da viagem)
   - **Tabela:** DANFE · Fornecedor · Data · Valor · PO + Total, Recarga e **Saldo** (em vermelho se negativo)
   - Todas as DANFEs e POs anexadas.
6. Confira e clique **Enviar**.

Envio parcial é permitido: rode a Etapa 2 de novo quando chegarem novas DANFEs. As que já foram
prestadas são apontadas no aviso (retire-as da pasta ou mova para uma subpasta `enviadas`).

---

## 4. Log (`FLASH_LOG.csv`)

Uma linha por solicitação e por DANFE prestada — abre no Excel:

`DataHora; Etapa; Viagem; Navio; Referencia; RQA; Portador; Cartao; ValorRecarga; DANFE; Fornecedor; DataDANFE; ValorDANFE; PO`

Serve de base para o controle de **saldo Flash por recarga** e para o encontro de contas.

> O log é gravado quando o e-mail é **montado**. Se você descartar o e-mail sem enviar, apague as linhas
> correspondentes no CSV para a DANFE não aparecer como "já prestada".

---

## 5. Limitações conhecidas

- Funciona só no **Outlook desktop (Windows)**. No Outlook Web/novo Outlook não há VBA — a alternativa seria Power Automate.
- O valor da DANFE vem do **nome do arquivo**; a macro não lê o PDF. Nome errado = valor errado.
- A macro não envia nada sozinha: o envio é sempre manual, depois da conferência.
