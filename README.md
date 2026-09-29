# cabotagem-web
## Workbench › Consulta de Notas (Qive)

Página `/workbench/qive`: qualquer pessoa pesquisa NF-e recebidas e CT-e (tomador) baixados do Qive
por chave, CNPJ, fornecedor, número, período e valor; baixa o XML; vê lançamentos ligados à nota
(campo "Referência" do lançamento = nº da nota ou chave).

### Configuração (Render › Environment)
| Variável | Obrigatória | Descrição |
|---|---|---|
| `QIVE_API_ID` | sim | API ID gerado no Qive (Configurações › API) |
| `QIVE_API_KEY` | sim | API Key gerada no Qive |
| `QIVE_BASE_URL` | não | padrão `https://api.arquivei.com.br` |
| `QIVE_MAX_PAGES` | não | páginas (50 notas cada) por execução do cron; padrão 40 |

### Robô
- Botão "Rodar robô agora" na página (até 4 páginas por tipo, para não estourar o timeout web).
- Automático: criar um Cron Job no Render com o comando `flask --app app qive-sync`
  (ex.: a cada 30 min, `*/30 * * * *`). O robô guarda o cursor e só busca o que é novo.
- "Consultar direto no Qive": busca na hora pela chave de acesso, mesmo antes do robô rodar.
