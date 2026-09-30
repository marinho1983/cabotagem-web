# Estudo — Envio de POs de Rancho (Anchor Marine)

> Status: **guardado para oportunidade futura** (30/09/2026).
> Fonte: caixa Outlook `ops.fin@posidoniashipping.com`, envios de fev/2026 a set/2026.

## 1. Como o envio é feito hoje

| Item | Padrão atual |
|---|---|
| Remetente | Posidonia \| OPS FIN (`ops.fin@posidoniashipping.com`) |
| Para | `anchormarine@anchormarine.com.br` (Anchor Marine Ship Supplier — contato Thiago Alves) |
| Cc | `ops.fin@posidoniashipping.com` |
| Frequência | 1 lote mensal, sempre no fim do mês (27/02, 26/03, 27/04, 28/05, 30/06, 28/07, 31/08, 28/09) |
| Conteúdo | 4 POs de rancho — Amazon Pioneer, Pathfinder, Commander, Courage |
| Material de limpeza | Até jul/2026 no mesmo e-mail ("rancho e material"); desde 31/08 em e-mail separado (PO 034804, PO 036312) |
| Corpo | Saudação → lista "Nº PO – NAVIO" em negrito → 4 orientações (título fiscal, envio ao protocolo, prazo dia 20, fluxo de pagamento) → assinatura |
| Anexos | PDF de cada PO, nome = observação do MXM |
| Resposta do fornecedor | Para `protocolofiscal@` com Cc `ops.fin@`, uma NFS por PO + dados bancários |

Histórico de assuntos:

| Data envio | Assunto | POs |
|---|---|---|
| 27/02/2026 | POs Fevereiro - Navios Amazon | 24834, 24837, 24843, 24844 |
| 26/03/2026 | POs Março- Amazons - Entrega de rancho e material | 26205 (material), 26210, 26212… |
| 27/04/2026 | POs Abril- Amazons - Entrega de rancho e material | 28066 (material), 28021, 28026… |
| 28/05/2026 | POs Maio- Amazons - Entrega de rancho e material | 29891 (material), 29855, 29857… |
| 30/06/2026 | POs Junho- Amazons - Entrega de rancho e material | 031620 (material), 031606, 031610… |
| 28/07/2026 | POs Julho- Amazons - Entrega de rancho e material | 033128 (material), 033082, 033083, 033085, 033087 |
| 31/08/2026 | POs JULHO- Amazons - Entrega de rancho | 034800, 034801, 034802, 034803 |
| 28/09/2026 | POs Agosto - Amazons - Entrega de rancho | 036313, 036314, 036315, 036316 |

## 2. Problemas encontrados

1. **Mês do assunto inconsistente** — "JULHO" enviado em 31/08 (viagens 26015); "Julho" em 28/07 (viagens 26013/14, rancho de 24/06 a 20/07); "Agosto" enviado em 28/09. Não se sabe se é mês de entrega, competência ou envio.
2. **"AMAZON PIONNER"** escrito errado no corpo desde fevereiro (no PDF está "PIONEER").
3. **Anexo sem extensão** — 28/09, PO036314 (Pathfinder) foi como `application/octet-stream`, sem `.pdf`.
4. **Nome dos anexos sem padrão** — "PO036316 - OPS - SHP…", "OPS SHP - PO 034802…", "PO 033082-OPS - SHP…"; PO com 5 e 6 dígitos.
5. **Orientação nº 3 contradiz o envio** — pede emissão até dia 20, mas a PO chega entre dias 26 e 31.
6. **Sem valor, viagem e tipo de rancho no corpo** — o e-mail de aprovação do MXM já traz tudo (ex.: PO 033087, R$ 10.000,00, ACR26014, rancho longo/curto, DANFEs).
7. Concordância: "Segue em anexo as POs" → "Seguem".

## 3. E-mail padrão proposto

**De:** ops.fin@posidoniashipping.com · **Para:** anchormarine@anchormarine.com.br · **Cc:** ops.fin@posidoniashipping.com

**Assunto:** `PO RANCHO | {MÊS/AAAA} | {PO nº(s)} | Navios Amazon`

**Corpo:**

> **Prezados,**
>
> Seguem em anexo as POs aprovadas referentes ao fornecimento e entrega de rancho em **{MÊS/AAAA}**:
>
> | PO | Navio | Viagem | Tipo | Valor |
> |---|---|---|---|---|
> | 0XXXXX | AMAZON PIONEER | APN26XXX | Rancho Mensal | R$ X.XXX,XX |
> | 0XXXXX | AMAZON PATHFINDER | APT26XXX | Rancho Mensal | R$ X.XXX,XX |
> | 0XXXXX | AMAZON COMMANDER | ACM26XXX | Rancho Complementar | R$ X.XXX,XX |
> | 0XXXXX | AMAZON COURAGE | ACR26XXX | Rancho Mensal | R$ X.XXX,XX |
>
> Pedimos a gentileza de observar as seguintes orientações:
>
> 1. **Uma nota por PO**, no mesmo valor indicado acima.
> 2. **Identificação no título fiscal:** número da PO e nome da embarcação obrigatórios.
> 3. **Envio do título fiscal:** para protocolofiscal@posidoniashipping.com, com cópia para ops.fin@posidoniashipping.com.
> 4. **Prazo para emissão:** até {X} dias úteis após o recebimento desta PO.
> 5. **Fluxo de pagamentos:** após o envio da PO, tratativas de pagamento exclusivamente com o Protocolo Fiscal.
>
> Agradecemos a atenção e ficamos à disposição.
>
> **Att. | Best Regards.**

**Nome dos anexos:** `PO036313 - OPS SHP - AMAZON PIONEER - COMPRA E ENTREGA DE RANCHO - @ALUMAR - APN26016.pdf`

## 4. Perguntas em aberto

1. Envio por PO (na aprovação) ou lote mensal? — recomendação: por PO.
2. Mês do assunto = mês da entrega, competência ou envio? — recomendação: entrega.
3. Prazo de emissão: manter "até dia 20" ou "X dias úteis após a PO"? (confirmar com Protocolo Fiscal)
4. Pode constar valor da PO no e-mail ao fornecedor?
5. Incluir protocolofiscal@ em cópia já no envio da PO?
6. Material de limpeza: e-mail separado ou linha da tabela?
7. Assinatura: pessoal ou genérica da caixa OPS FIN?
