# Changelog

## [1.0.0] - 2026-09-10

Fecha a V1: base real do Databricks em produção, filtros/indicadores novos e
uma auditoria de fechamento (segurança, dado dinâmico, visibilidade). Resume
tudo que ficou faltando entre o 0.8.1 e aqui, que não tinha sido registrado
version a versão.

**Filtros e dados**
- Filtro **Gestor** e **Equipe** (segmento de negócio: "Vendas UH"/"Lotes
  Comerciais"/"Repasses" — separado da Cidade, que voltou a ser sempre o
  local real do colaborador).
- Período trocado para um único seletor de calendário (`st.date_input`).
- `CARGO_GROUP_MAP` restrito aos cargos comerciais confirmados pelo usuário
  (normaliza senioridade Junior/Pleno/Sênior e variantes de gênero/typo).
- Corte de desligados: só entram na análise os últimos 10 anos —
  **dinâmico** (`hoje − 10 anos`, recalculado a cada carga), assim como o
  início do eixo de meses dos gráficos.
- Cidade normalizada (CAIXA ALTA sem acento -> nome "bonito" com UF).

**Indicadores e páginas novas**
- **Turnover Voluntário**: query traz `Tipo Desligamento` (Voluntário/
  Involuntário/Acordo/Transferência); 2 gráficos novos (desligamentos por
  tipo empilhado, turnover voluntário mensal).
- Nova aba **Ranking**: Top 5 de turnover médio e desligamentos por
  Cidade/Cargo/Gestor.
- **Mapa de concentração de mão de obra** (bolhas por cidade, só ativos) e
  gráfico comparativo na Permanência Média — ao lado do card já existente.
- Exportar para Excel na tabela "Colaboradores no filtro".

**Segurança e confiabilidade**
- Login: bloqueio de conta após 5 tentativas de senha erradas (15 min),
  mitigando força bruta — `src/auth.py`.
- Corrigido incidente de produção: `get_data()` cacheava indefinidamente
  entre deploys (bytecode da função nunca mudava, mesmo com
  `load_source_data()` mudando toda hora) — removida a camada de cache.
- Corrigido "SSL connection has been closed unexpectedly" do Neon
  (`pool_pre_ping`/`pool_recycle`) + tela de erro amigável no login.
- Carga do Neon (`_neon_people.replace_people_rows`) ficou atômica
  (TRUNCATE + insert na mesma transação) depois de dois incidentes de
  base zerada por query vazia/duplicata/erro de tipo.

**Login redesenhado**
- Cartão dividido (marca + logo à esquerda, formulário à direita), no
  padrão comum de telas de login de mercado.

**Fechamento da auditoria (2026-09-10)**
- Busca da tabela agora ignora acento.
- `perm_meses` parou de ser lido (nunca foi usado em cálculo — ver
  `OBSOLETO.md`, criado nesta versão).
- Barra lateral: "Dados atualizados em" (nova tabela `sync_meta`) + contador
  de registros com cargo/cidade fora do mapeamento — visibilidade em vez de
  descoberta manual, já que a base é atualizada mensalmente.
- Pendências que sobraram (sync manual, sem PAT ainda, sem testes
  automatizados, cobertura parcial de Gestor em desligados, 6 pessoas sem
  cidade) registradas em `NEXTSTEPS.md` (uso interno, não versionado).

## [0.8.1] - 2026-09-09

- **`scripts/sync_from_databricks.py`**: carrega `people_rows` direto do Databricks via OAuth U2M (login interativo no navegador, sem PAT/token), rodando a query real fornecida pelo usuário contra `rh.gold.fato_funcionario_ativo`/`fato_funcionario_inativo` (com join em `enterprise.data.dim_local` pra trazer Cidade). Substitui a etapa manual de exportar CSV do SQL Editor.
- A query também traz **Gestor** e **Cargo Gestor** (até 5 níveis de hierarquia acima do colaborador, via CTE de reportes) — dado novo, ainda não usado na interface, mas resolve a limitação "Executivos/Gestores — adiado" registrada em "Limitações da base": agora o campo existe na base, falta só o filtro/ranking na UI (não implementado nesta versão).
- `people_rows` ganhou as colunas `setor`, `gestor`, `cargo_gestor` (nullable — o bootstrap via HTML não preenche).
- Extraído `scripts/_neon_people.py` (schema + upload da tabela), compartilhado por `load_people_data.py` e `sync_from_databricks.py` — evita as duas fontes de carga divergirem de schema.
- **Segurança**: o nome do gestor de referência usado na query (um diretor específico) foi parametrizado em `.streamlit/secrets.toml` -> `[databricks].gestor_referencia`, não hardcoded no script — o repositório é público, então nomes de executivos/estrutura organizacional não podem ir para o código versionado.

## [0.8.0] - 2026-09-09

- **Resolvida a pendência crítica da 0.6.0**: `data_logic.load_source_data()` não lê mais o HTML local — passou a consultar a tabela `people_rows` no mesmo Postgres (Neon) já usado pro login, via `st.connection("sql")`. Motivo: enquanto não há credencial do Databricks (PAT/OAuth M2M ainda pendente com o time de dados), o app publicado no Streamlit Cloud ficaria sem nenhum dado (o HTML nunca vai pro GitHub). Com a base no Neon, o deploy volta a funcionar com dado real, e a troca futura pro Databricks fica isolada no script de carga — `load_source_data()` não muda de novo.
- Novo `scripts/load_people_data.py`: carrega/recarrega `people_rows` (TRUNCATE + insert completo). Por padrão lê o HTML local (usado para o bootstrap inicial); com `--csv arquivo.csv` lê um export manual do Databricks SQL Editor (mesmas colunas). Nunca imprime dado de colaborador — só contagens.
- Eixo de meses dos gráficos (`labels`/`keys`) deixou de vir do payload do HTML — agora é gerado por `data_logic._month_range()` (fixo em 2015-04 até 5 meses à frente do mês atual), já que essa metadata não depende de colaborador nenhum e assim nenhuma fonte de dado precisa carregá-la.
- `.gitignore`: adicionado `*.csv` — qualquer export baixado do Databricks é PII e não deve ser versionado (mesma lógica do `assets/*.html`).
- Adicionado `.streamlit/secrets.toml` (e `.example`) uma seção `[databricks]` (`server_hostname`, `http_path`, `token`, `client_id`, `client_secret`) e `scripts/test_databricks.py`, para quando a credencial (PAT ou service principal) chegar — testa a conexão com o SQL Warehouse sem precisar mexer no restante do app.
- `requirements.txt`: adicionado `databricks-sql-connector`.

## [0.7.2] - 2026-09-08

- Removida por completo a "Curva de Retenção por Coorte de Admissão" (a pedido do usuário — não só os 3 cartões da 0.7.1, o indicador inteiro: título, gráfico e legenda). Removidas as funções que só existiam para ela: `data_logic.retention_curve`, `data_logic.weighted_retention`, `charts.retention_curve`. "Permanência Média: Ativos × Desligados" continua no dashboard, sem alteração.

## [0.7.1] - 2026-09-08

- Removidos os 3 cartões de indicador (retenção aos 3/6/12 meses) de cima do gráfico "Curva de Retenção por Coorte de Admissão" — a pedido do usuário, ficou só título/subtítulo + gráfico + legenda. "Permanência Média: Ativos × Desligados" não foi alterado.

## [0.7.0] - 2026-09-08

- **Navegação multipágina**: migrado de script único para `st.navigation`/`st.Page`. `app.py` virou um roteador fino (autenticação + navegação); o conteúdo do dashboard foi para `app_pages/dashboard.py`. Cada página só roda depois do login, checado uma única vez no roteador (antes cada página precisava chamar `require_login()` por conta própria).
- **Nova página "Comparativo Turnover"** (`app_pages/comparativo_turnover.py`), pedido da diretoria: compara lado a lado a fórmula de turnover do Comercial (efetivo médio do mês) com a do D.O. (efetivo do fechamento do mês anterior) — mesmo numerador, denominador diferente. Nova série `turn_do` em `data_logic.build_monthly_series`/`select_period`. Inclui um card amarelo de "Recomendação de Mercado" com a leitura de qual fórmula é mais alinhada à prática de RH (efetivo médio) e por quê.
- Filtro Status movido do topo para a linha "Ordenar por/Direção", junto da tabela "Colaboradores no filtro".
- Barra lateral: logo do projeto (ícone + "TurnOver Comercial", `assets/icons/logo_sidebar.png`, gerado a partir do ícone oficial em `assets/icons/`) no topo, acima das abas; ícones Material Symbols em cada aba (`:material/groups:`, `:material/balance:` — o Streamlit não tem suporte nativo a Lucide, Material Symbols é o mais próximo); saudação "Olá, {nome}" + botão Sair abaixo da navegação.
- Visual dos indicadores "Permanência Média" e "Curva de Retenção" ajustado em duas iterações: primeiro viraram números soltos sem borda (pra não parecerem caixas flutuando), depois — a pedido do usuário — voltaram a ser cartões com borda iguais aos 6 KPIs do topo, só que centralizados como grupo (`.kpi-row-centered`) em vez de esticados numa grade de 6 colunas.
- Removidas todas as menções ao nome específico do arquivo HTML de dados em código e documentação (ver 0.6.0) — `data_logic._find_html_source()` localiza qualquer `.html` em `assets/`.

## [0.6.0] - 2026-09-08

- **Remoção crítica de dados sensíveis do histórico do git**: o HTML local com dado real de 596 colaboradores foi retirado do rastreamento e o único commit existente foi reescrito (amend + `push --force-with-lease`) para não conter mais o arquivo — necessário porque o repositório vai virar público. O arquivo continua no disco local (o app precisa dele para rodar), só não vai mais para o GitHub. Adicionado `assets/*.html` ao `.gitignore`.
- Conferido o restante do código/documentação em busca de nomes/dados reais vazados — nada encontrado além do arquivo acima.
- **Pendência a decidir**: como a fonte de dados hoje é só esse arquivo local, o app publicado no Streamlit Cloud (que só recebe o que está no GitHub) vai ficar sem dado nenhum assim que o repo for público. Precisa mover a base de colaboradores para algum lugar que o app deployado consiga ler sem ela estar no git (ex.: a mesma base Neon usada no login) antes de publicar de verdade.
- Removida toda menção ao nome específico do arquivo HTML do código e da documentação (mesmo ele não estando mais no repositório, o nome não precisa aparecer em lugar nenhum). `src/data_logic.py` agora localiza automaticamente qualquer `.html` dentro de `assets/` (`_find_html_source()`), em vez de um caminho fixo.

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
- **Limitação identificada**: a base local não tem um campo de gestor/gerente responsável por colaborador. Não foi possível implementar o filtro "Executivos" nem o "Ranking de Executivos por turnover" (itens do pedido do usuário) por falta dessa coluna. Ver `Context.md` para detalhes e o que falta para viabilizar.

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
