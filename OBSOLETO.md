# Obsoleto

Registro de campos/colunas que continuam existindo (geralmente por já estarem
gravados no Neon, ou por custarem mais caro remover do que manter) mas que o
app **não lê mais** — pra alguém não "redescobrir" e tentar usar de novo, e pra
manter o histórico de por que saíram de uso.

## `perm_meses` (tabela `people_rows`)

- **O que era**: permanência em meses, vinda da base original (HTML/planilha),
  pensada como um atalho pronto em vez de calcular a partir de Admissão/Demissão.
- **Por que saiu de uso**: o app sempre calculou a permanência exibida na tela
  (`humanize_tenure`/`humanize_days`, em `src/data_logic.py`) direto a partir de
  `Admissão`/`Demissão`, não a partir dessa coluna — ela nunca foi lida em
  cálculo nenhum, só ficava sendo carregada à toa a cada consulta.
- **O que foi feito (2026-09-10)**: removida de `PEOPLE_ROWS_QUERY` em
  `src/data_logic.py` — o app não seleciona mais essa coluna, então não tem
  como ela voltar a ser usada por acidente. Continua existindo na tabela
  `people_rows` do Neon e sendo gravada por `scripts/_neon_people.py`
  (`COLUMN_MAP`), porque já está lá e não faz mal nenhum manter o histórico —
  só não entra mais em nenhuma leitura do dashboard.
- **Se precisar mexer de novo**: o dado ainda existe no Neon, é só adicionar
  `perm_meses AS "Perm_meses"` de volta em `PEOPLE_ROWS_QUERY` — mas antes disso,
  confirmar que faz sentido usar uma permanência pré-calculada em vez de
  recalcular na hora (evita divergência entre o valor salvo e Admissão/Demissão
  atuais, ex.: depois de uma reintegração ou correção de data).
