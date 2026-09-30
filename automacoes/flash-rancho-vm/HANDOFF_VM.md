# Handoff — trazer o Flash Rancho para dentro da VM

Roteiro para a sessão do Claude Code que roda **na VM** (junto dos outros robôs, ex.: `/home/mlf/triagem-email`).

## Objetivo
Integrar `flash_rancho` ao ambiente dos robôs da VM, **reaproveitando o que já existe lá** em vez das
peças genéricas escritas fora dela:

| Peça genérica atual (`flash_rancho/`) | Substituir por (na VM) |
|---|---|
| `graph.py` — token client-credentials próprio + `.env` | Cliente/autenticação Graph já usado pelos robôs (ver `triagem-email`) |
| Aprovações de PO lidas dos e-mails do MXM (`noreply@mxmwebmanager`) | **Acesso direto ao MXM** (PO, valor, observação, RQA, status) — mais confiável que parsear e-mail |
| Valor da recarga / RQA lidos do assunto e corpo do e-mail | MXM (RQA: valor, data, portador) |
| Viagem / navio só pelo prefixo (APN/APT/ACM/ACR) | **Mestre** (cadastro de viagens/navios/ETB) |
| Agendamento via `crontab` sugerido no README | Mesmo agendador/serviço dos outros robôs |
| Log em arquivo | Mesmo padrão de log/alerta dos robôs (ex.: chat do Teams do robô) |

## O que manter como está (já testado — 16 testes)
- `parse.py` — regras de leitura dos nomes de DANFE/PO e textos
- `conferencia.py` — regras de conferência (bloqueios e avisos)
- `emails.py` — corpo do e-mail de prestação de contas e do relatório
- `tests/` — rodar `python -m pytest -q` após a integração

## Fluxo combinado com o Mario
1. Sinal manual: categoria **FLASH - PRESTAR CONTAS** no e-mail da "SOLICITAÇÃO DE RECARGA FLASH" (caixa OPS FIN).
2. A rotina confere RQA × POs aprovadas × DANFEs (pasta SharePoint/OneDrive) × PDFs das POs (outra pasta).
3. OK → rascunho do encaminhamento (Jessica, Protocolo Fiscal, Contas a Pagar, Willyanson, Sanchez; Cc OPS FIN)
   com tabela, total, saldo e anexos; categoria **FLASH - RASCUNHO PRONTO**.
4. Pendência → relatório em Rascunhos do Mario; categoria **FLASH - PENDENCIA**.
5. Nunca enviar automaticamente.

## Próximas entregas (depois da integração)
1. Conclusão automática (sem categoria) usando o MXM: RQA fechada quando todas as DANFEs têm PO aprovada.
2. Etapa 1: rascunho da SOLICITAÇÃO DE RECARGA para a Jessica a partir do e-mail "Solicitação de Depósito"
   da operação + RQA do MXM.
3. Controle de envio parcial e saldo Flash por RQA (base para o encontro de contas).

## Atenção
O repositório `marinho1983/cabotagem-web` é **público**. Configurações reais (e-mails, cartão, caminhos,
credenciais) ficam só na VM (`config.json`/`.env`, fora do git). Avaliar mover o código para o repositório
privado dos robôs.
