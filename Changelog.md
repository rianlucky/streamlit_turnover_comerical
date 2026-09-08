# Changelog

## [0.6.0] - 2026-09-08

- **Remoção crítica de dados sensíveis do histórico do git**: `assets/painel_cidade_CLT_media_turnover.html` (dado real de 596 colaboradores) foi retirado do rastreamento e do único commit existente foi reescrito (amend + `push --force-with-lease`) para não conter mais o arquivo — necessário porque o repositório vai virar público. O arquivo continua no disco local (o app precisa dele para rodar), só não vai mais para o GitHub. Adicionado `assets/*.html` ao `.gitignore`.
- Conferido o restante do código/documentação em busca de nomes/dados reais vazados — nada encontrado além do arquivo acima.
- **Pendência a decidir**: como a fonte de dados hoje é só esse arquivo local, o app publicado no Streamlit Cloud (que só recebe o que está no GitHub) vai ficar sem dado nenhum assim que o repo for público. Precisa mover a base de colaboradores para algum lugar que o app deployado consiga ler sem ela estar no git (ex.: a mesma base Neon usada no login) antes de publicar de verdade.

## [0.5.0] - 2026-09-08

- Adicionado login por e-mail (`src/auth.py`, `src/auth_ui.py`): tela 1 pede o e-mail; tela 2 mostra um de três casos — (a) sem acesso cadastrado → orienta a solicitar inclusão a `rian.jesus@pacaembu.com`; (b) acesso cadastrado e primeiro login → pede para criar e confirmar uma senha; (c) acesso cadastrado e senha já definida → pede a senha.
- O DO concede acesso só inserindo o e-mail (sem senha) — cada pessoa define a própria senha no primeiro login.
- Credenciais persistidas em Postgres (Neon), via `st.connection("sql")` — necessário porque o sistema de arquivos do Streamlit Community Cloud é efêmero (some em reboot/redeploy), então não dá pra guardar senha em arquivo local.
- Senhas com hash `bcrypt` (nunca armazenadas em texto puro).
- `scripts/grant_access.py`: script de linha de comando para conceder (ou remover) acesso por e-mail, rodado localmente contra o Neon.
- `.streamlit/secrets.toml.example` adicionado (modelo seguro pra versionar); `.streamlit/secrets.toml` real continua fora do git.
- Botão "Sair" no cabeçalho do dashboard.
- `requirements.txt`: adicionados `sqlalchemy`, `psycopg2-binary`, `bcrypt`.

## [0.4.0] - 2026-09-08

- Filtro Status trocado de `radio` para `multiselect` (lista, mesmo padrão de Cidade/Cargo); opções `Ativo`/`Desligado`, vazio = Ambos.
- Grupo de cargo "Supervisor de Vendas" renomeado para "Supervisor" (`CARGO_GROUP_MAP`/`CARGO_GROUP_ORDER`).
- Período: voltou a ser dois campos (`De`/`Até`) em vez do `select_slider` — são `st.selectbox`, então dá pra digitar para buscar o mês, o que o slider não permitia. Valor padrão passou a ser calculado dinamicamente: últimos 12 meses contando do último mês com qualquer admissão ou desligamento na base (`last_active_month`), não mais fixo em `2025-08`/`2027-02`.
- Rótulos de dados (maior e menor valor da série) adicionados nos gráficos "Turnover Real Mensal", "Headcount Ativo", "Saldo Líquido Mensal" e "Indicador legado".
- Dois novos indicadores adicionados abaixo dos gráficos existentes:
  - **Permanência Média: Ativos × Desligados** — tempo de casa médio de quem está ativo vs. quem foi desligado, no filtro de cidade/cargo/período atual (ignora o filtro de Status, já que o objetivo é comparar os dois grupos).
  - **Curva de Retenção por Coorte de Admissão** — % de cada leva mensal de admitidos ainda ativa após 3/6/12 meses, com 3 indicadores-resumo (média ponderada pelo tamanho da coorte) e um gráfico de linha com a tendência pelas últimas 18 coortes elegíveis.
- Gestores/Executivos: adiado por decisão do usuário até a chegada dos dados do Databricks (ver `Context.md`).

## [0.3.0] - 2026-09-08

- Filtro Cidade agora exibe "Cidade/UF" (ex.: "Assis/SP"); mapeamento cidade→UF adicionado em `src/data_logic.py` (`CITY_UF`), inferido manualmente pois a base não traz o estado por colaborador.
- Filtro Cargo trocado de seleção única para multiseleção com 7 grupos agregados (Auxiliar, Assistentes, Analistas, Analistas Parcerias, Supervisor de Vendas, Coordenador, Gerente), mapeados a partir do cargo real (`Cargo Atual2`) em `CARGO_GROUP_MAP`; permite combinar ou isolar grupos livremente.
- Filtro de período trocado de dois `selectbox` ("De"/"Até") por um único `st.select_slider` (mesmo padrão do RealizaDO), mais intuitivo para ajustar o intervalo.
- Gráficos de barra (Admissões×Demissões e Saldo Líquido) agora com cantos arredondados (`marker_cornerradius`); `plotly` atualizado para `5.24.1` (a versão anterior, 5.18, não suportava a propriedade).
- Adicionado filtro de Status ("Ambos" / "Somente Ativos" / "Somente Inativos") na tabela.
- Busca da tabela agora também localiza por ID (Registro); coluna "Registro" renomeada para "ID".
- Permanência agora é humanizada: "X anos e X meses" / "X anos" / "X meses" / "X dias" (`humanize_tenure` em `src/data_logic.py`), com a cor da faixa (vermelho/âmbar/verde) recalculada a partir do total de dias.
- **Arquitetura**: `get_series`/`filter_people` deixaram de depender do payload agregado pré-calculado (`PAYLOAD.data`, por cidade×grupo antigo) e passaram a montar a série mensal (admissões, desligamentos, headcount) diretamente a partir da base de colaboradores (`ALL_ROWS`). Isso remove a dependência da tabela dinâmica fixa do HTML original e permite qualquer combinação de filtros (cidade, grupo de cargo, status) sem precisar reprocessar o HTML de origem.
- **Limitação identificada**: a base atual (`assets/painel_cidade_CLT_media_turnover.html`) não tem um campo de gestor/gerente responsável por colaborador. Não foi possível implementar o filtro "Executivos" nem o "Ranking de Executivos por turnover" (itens do pedido do usuário) por falta dessa coluna. Ver `Context.md` para detalhes e o que falta para viabilizar.

## [0.2.1] - 2026-09-08

- Corrigido bug em que o CSS/tema não era aplicado: o sanitizador de HTML do `st.markdown(unsafe_allow_html=True)` remove tags `<style>`/`<link>`, fazendo o CSS aparecer como texto literal na página. Trocado por `st.html()` (`src/styles.py`, `src/components.py`, `app.py`) em todos os pontos de injeção de HTML/CSS.
- Corrigido conflito de especificidade CSS que fazia a cor de permanência (`.perm-low/.perm-mid/.perm-ok`) ser sobrescrita pela regra `.tbl td`; seletores agora são `.tbl td.perm-*`.
- Corrigido título cortado no topo da página: o `padding-top` do `.block-container` (1.6rem) era menor que a altura do header fixo do Streamlit (60px), fazendo a barra sobrepor a parte de cima do "Movimentação de Pessoas". Ajustado para 4.5rem.
- Validado visualmente via Playwright (screenshot + inspeção de `computedStyle`/geometria) que KPIs, cartões de gráfico, gráficos Plotly e a tabela (badges e permanência colorida) renderizam como no painel original, sem sobreposição do header.

## [0.2.0] - 2026-09-08

- Reorganizado o projeto em `src/` (`data_logic.py`, `charts.py`, `components.py`, `styles.py`), com `app.py` como orquestrador enxuto; removido `data_logic.py` duplicado da raiz.
- Refeitos os gráficos em Plotly para replicar fielmente os gráficos Chart.js do painel original: Admissões×Demissões e Saldo Líquido em barras, Turnover real/Indicador legado em linha com área preenchida e linha tracejada de média.
- Recriados os cartões de KPI (cores por indicador), cartões de gráfico (título/subtítulo/legenda com marcadores coloridos) e a tabela analítica (badges de cargo/status, permanência colorida por faixa) via HTML/CSS.
- Adicionada paginação (20 por página) e ordenação por coluna na tabela de colaboradores.
- Adicionado tema (`.streamlit/config.toml`) e CSS (`src/styles.py`) com a paleta e a fonte DM Sans do painel original.
- Validado o fluxo completo (multiseleção de cidade, ordenação, busca, paginação) via `streamlit.testing.v1.AppTest`, sem exceções.

## [0.1.0] - 2026-09-08

- Criada a V1 do dashboard Turnover Comercial em Streamlit.
- Reaproveitado o payload local existente no HTML.
- Mantidos os cálculos de turnover real e indicador legado.
- Implementados filtros, KPIs, gráficos e tabela analítica.
- Adicionada estrutura inicial para futura conexão com Databricks.
