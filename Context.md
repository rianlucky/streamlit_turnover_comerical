# Contexto do projeto

## Objetivo

Recriar em Streamlit o dashboard de turnover comercial existente em um painel HTML local, mantendo os cálculos atuais, com fidelidade visual aos gráficos e componentes do painel original, e preparando a arquitetura para uma futura fonte Databricks.

## Estado atual (V1 — 2026-09-10)

- `app.py` é um roteador fino (autenticação + `st.navigation`/`st.Page`) com 3 páginas: `app_pages/dashboard.py` (Movimentação de Pessoas), `app_pages/ranking.py` (Top 5 por Cidade/Cargo/Gestor) e `app_pages/comparativo_turnover.py` (fórmula Comercial × D.O.).
- Barra lateral: logo do projeto, ícones Material Symbols por página, saudação "Olá, {nome}" + botão Sair, e um rodapé cinza (`render_sidebar_status()`) com a data da última sincronização e contadores de cargo/cidade fora do mapeamento.
- Código organizado em módulos (`src/data_logic.py`, `src/charts.py`, `src/components.py`, `src/styles.py`, `src/auth.py`, `src/auth_ui.py`) + scripts de carga (`scripts/_neon_people.py`, `load_people_data.py`, `sync_from_databricks.py`, `test_databricks.py`, `grant_access.py`).
- **Dados vêm do Databricks** (via `scripts/sync_from_databricks.py`, OAuth U2M manual) carregados na tabela `people_rows` do Neon — não mais do HTML local (isso mudou nas versões 0.8.x, ver Changelog). O HTML local só serve de bootstrap inicial (`load_people_data.py`, sem `--csv`).
- Filtros: Cidade (multiseleção, "Cidade/UF"), Cargo (grupo agregado), Gestor, Equipe (Vendas UH/Lotes Comerciais/Repasses) e Período (`st.date_input`, calendário único). Status (Ativo/Desligado, padrão Ativo) fica junto da tabela.
- Período padrão: últimos 12 meses a partir do último mês com dado (`last_active_month`).
- KPIs (6 cartões), 8 visualizações (Admissões×Demissões, Turnover Real, Headcount Ativo, Saldo Líquido, Desligamentos por Tipo, Turnover Voluntário, Indicador legado, mapa de concentração de mão de obra) e tabela analítica com busca (nome, cargo, cidade — **sem acento** — e ID), ordenação, paginação e exportação Excel.
- Permanência humanizada, com cor por faixa; card "Permanência Média: Ativos × Desligados" com barra comparativa.
- Paleta, tipografia (DM Sans) e estilo replicados via CSS injetado (`src/styles.py`) — inclui o cartão de login dividido (marca + formulário).
- Login por e-mail/senha (bcrypt) com bloqueio de conta após 5 tentativas erradas (15 min).

## Login e infraestrutura (2026-09-08)

- Repositório GitHub (`rianlucky/streamlit_turnover_comerical`) vai ficar **público** — a pedido do usuário. Antes disso, removi o HTML local com dado real de 596 colaboradores do rastreamento do git **e reescrevi o único commit existente** (amend + `push --force-with-lease`) pra ele não aparecer nem no histórico. O arquivo continua no disco local — só não vai mais pro GitHub. Conferi o resto do código/docs em busca de nomes/dados reais vazados: nada além desse arquivo. O caminho/nome do arquivo também não fica mais hardcoded em lugar nenhum do repositório (`data_logic._find_html_source()` acha qualquer `.html` dentro de `assets/`).
- Login por e-mail implementado (`src/auth.py`, `src/auth_ui.py`), persistido no Neon: tela 1 pede e-mail; tela 2 mostra um de três casos (sem acesso -> pede pra solicitar a `rian.jesus@pacaembu.com`; acesso liberado sem senha ainda -> cria senha; acesso com senha -> loga). O DO concede acesso só inserindo o e-mail (`scripts/grant_access.py`), sem definir senha nenhuma — quem cria a senha é a própria pessoa, no primeiro login.
- Considerado (e descartado por ora) usar Microsoft Entra ID (`st.login`) pra SSO corporativo — mais robusto, mas depende de um App registration no Azure AD que o TI ainda não tem disponível. Fica como possível evolução futura; a lógica de "logado ou não" está isolada em `auth_ui.require_login()`, então dá pra trocar sem reescrever o resto do app.

## Fonte de dados: HTML local -> Neon (2026-09-09)

- **Pendência da seção anterior resolvida**: o usuário pediu acesso ao Databricks (PAT ou service principal/OAuth M2M) ao time de dados, mas a liberação está pendente ("situação delicada" — provavelmente exige aprovação de admin). Enquanto isso, `load_source_data()` foi migrada para ler a tabela `people_rows` no mesmo Neon do login, em vez do HTML local — resolve o problema de deploy sem esperar o Databricks.
- `scripts/load_people_data.py` faz o carregamento (TRUNCATE + insert completo, não incremental): por padrão a partir do HTML local (usado para o bootstrap inicial, já rodado — 596 registros carregados e conferidos batendo com os números do HTML: 143 meses, 43 cidades, mesmos grupos); com `--csv` a partir de um export manual do Databricks SQL Editor (usa o login do próprio usuário no navegador, sem precisar de PAT/token — só a query em si passa a exigir credencial quando o acesso à API for liberado).
- Eixo de meses (`labels`/`keys`, antes vindo do payload do HTML) passou a ser gerado por `data_logic._month_range()` — fixo em 2015-04 até 5 meses à frente do mês atual — porque essa metadata não tem relação com colaborador nenhum e assim nenhuma fonte de dado (HTML, CSV do Databricks) precisa carregá-la.
- Segurança: nenhum dado de colaborador é impresso pelos scripts (só contagens); `*.csv` foi adicionado ao `.gitignore` (mesma lógica do `assets/*.html`) para qualquer export futuro do Databricks; a única credencial de acesso à base é a connection string do Neon em `.streamlit/secrets.toml` (fora do git).
- `.streamlit/secrets.toml`/`.example` ganharam uma seção `[databricks]` (`server_hostname`, `http_path`, `token` ou `client_id`/`client_secret`) e `scripts/test_databricks.py`, prontos para quando o PAT/service principal chegar — nesse ponto, `load_people_data.py --csv` pode ser trocado por uma consulta direta ao SQL Warehouse, sem mexer em `load_source_data()` de novo.
- **Ainda pendente**: a liberação do PAT/OAuth M2M em si (fora do controle do assistente); e o processo de refresh da base no Neon continua manual (rodar um dos scripts de carga de novo) até essa credencial existir.

## Sync semi-automatizado via OAuth (2026-09-09)

- Em vez de esperar o PAT/M2M, o usuário decidiu rodar a query real (fornecida por ele, contra `rh.gold.fato_funcionario_ativo`/`fato_funcionario_inativo`, com join em `enterprise.data.dim_local` para Cidade) direto do próprio computador via OAuth U2M — `scripts/sync_from_databricks.py`. Resolve o refresh sem precisar de token, só exige rodar o script localmente (login no navegador) sempre que quiser atualizar a base.
- Essa query trouxe dois campos novos que a base local (HTML) nunca teve: **Gestor** e **Cargo Gestor** (até 5 níveis de hierarquia acima do colaborador). Isso resolve o dado que faltava para a pendência "Executivos/Gestores — adiado" (ver "Limitações da base") — a base agora tem a coluna, mas o filtro "Executivos" e o ranking de turnover por gestor **ainda não foram implementados na UI**, fica como próximo passo quando o usuário pedir.
- `people_rows` ganhou colunas `setor`/`gestor`/`cargo_gestor` (nullable); schema e upload foram extraídos para `scripts/_neon_people.py`, compartilhado entre `load_people_data.py` (HTML/CSV) e `sync_from_databricks.py` (OAuth), pra não haver duas versões do schema.
- **Cuidado de segurança aplicado**: a query original que o usuário colou tinha `nome_gestor = '<nome de um diretor>'` escrito direto no SQL. Como esse script vai para o repositório público, o nome foi movido para `.streamlit/secrets.toml` -> `[databricks].gestor_referencia` (fora do git) em vez de ficar hardcoded no `.py`.
- Testado localmente: reconstrução do schema (`ALTER TABLE ... ADD COLUMN IF NOT EXISTS`) não quebrou os 596 registros já carregados; simulação com dados sintéticos no formato que a query do Databricks devolve (antes do rename `Cargo Atual`->`Cargo Atual2` etc.) validou o caminho `sync_from_databricks.fetch_from_databricks()` -> `_neon_people.replace_people_rows()` sem erro. **Não testado**: a conexão OAuth real com o Databricks (exige navegador interativo, que o assistente não tem neste ambiente) — o usuário precisa rodar `sync_from_databricks.py` uma vez para validar isso na prática.

## Limitações da base (2026-09-10)

A base (`people_rows` no Neon, carregada do Databricks) tem: `Registro, Nome, Cargo Atual2, Grupo, Cidade, Admissão, Demissão, Status, Setor, Gestor, Cargo Gestor, Tipo Desligamento, Equipe`. `Perm_meses` também é gravada mas não é mais lida (ver `OBSOLETO.md`).

- **UF da cidade**: a base não traz UF/estado por colaborador; `src/data_logic.py:CITY_UF`/`CITY_RAW_TO_DISPLAY` mapeiam cidade -> nome bonito + UF manualmente. Cidade nova ainda não mapeada cai num fallback de Title Case (sem acento certo) e é contada no rodapé da barra lateral ("cidade fora do mapeamento") — sinal pra atualizar o dicionário.
- **Cargos**: `CARGO_GROUP_MAP` é a allowlist definitiva dos cargos comerciais (classificados um a um com o usuário em 2026-09-09/10 — títulos fora dela, ex.: Marketing, Financeiro Comercial, são descartados). Cargo novo/renomeado também é contado no rodapé da barra lateral.
- **Executivos/Gestores — resolvido**: a query do Databricks traz `Gestor`/`Cargo Gestor` (até 5 níveis de hierarquia) e `Equipe`. Existe filtro de Gestor e um grupo de cargo "Executivos", além do Ranking por Gestor. **Mas a cobertura de Gestor pra quem já foi desligado é parcial** (~38% em 2026-09-10, join por `id_funcionario`+`data_desligamento` contra `rh.silver.oracle_hcm_pit_adm_00003_desligados_relatorio`) — ver `NEXTSTEPS.md`.
- **6 pessoas sem Cidade** (join de `dim_local` sem correspondência) — identificadas por `Setor`, decisão de correção pendente (ver `NEXTSTEPS.md`).

## Indicadores implementados

- **Permanência Média: Ativos × Desligados** — tempo de casa médio dos dois grupos (ignora o filtro de Status), com uma barra comparativa.
- **Turnover Voluntário/Involuntário** — a query do Databricks passou a trazer `Tipo Desligamento`; virou 2 gráficos (desligamentos por tipo empilhado, turnover voluntário mensal) e alimenta o corte de 10 anos e o cálculo de turnover voluntário (desligamentos voluntários ÷ efetivo médio, sem admissões no numerador).
- **Ranking (Top 5)**: turnover médio e total de desligamentos por Cidade, Cargo e Gestor, numa aba própria.
- **Mapa de concentração de mão de obra**: bolhas por cidade (só ativos), ao lado da Permanência Média.

## Outras sugestões de indicadores (ainda não implementadas)

- **Attrition precoce**: % de desligados com permanência < 3 meses sobre o total de desligados no período — indicador clássico de qualidade de contratação/onboarding.
- **Sazonalidade de desligamentos**: desligamentos por mês-calendário (Jan, Fev, …) agregando todos os anos, para ver se há meses historicamente mais críticos.
- **Curva de retenção por coorte de admissão** (% ainda ativo após 3/6/12 meses): chegou a ser implementada e depois removida a pedido do usuário (2026-09-08) — ver Changelog 0.6/0.7.1/0.7.2. Fica registrada aqui como ideia caso queiram retomar.

## Regras preservadas

- Turnover real mensal: `[(admissões + desligamentos) / 2] / efetivo médio do mês * 100`.
- Turnover voluntário mensal: `desligamentos voluntários / efetivo médio do mês * 100` (sem admissões no numerador — mede especificamente saída por vontade própria).
- Efetivo médio: média do headcount no início e no fim do mês.
- Indicador legado: `desligamentos / headcount do mês anterior * 100`.
- Médias dos indicadores consideram apenas valores maiores que zero.
- A tabela inclui colaboradores ativos em qualquer parte do período selecionado.
- Corte de 10 anos: desligados com Demissão ≤ (hoje − 10 anos) saem da análise (calculado a cada carga, não é uma data fixa).

## Decisões de fidelidade visual

- Gráficos Admissões×Demissões e Saldo Líquido: barras (como no Chart.js original), não linhas.
- Turnover real e Indicador legado: linha com preenchimento de área e linha tracejada de média do período, igual ao HTML original.
- Tabela: badges coloridos para Cargo/Status e permanência colorida por faixa (`<3m` vermelho, `<12m` âmbar, `≥12m` verde), igual às classes `.badge`/`.perm-*` do HTML.
- A multiseleção de cidade do HTML original (painel custom com checkbox "selecionar todas") foi substituída pelo `st.multiselect` nativo do Streamlit — funcionalmente equivalente (vazio = Global/todas), mas sem recriar o dropdown customizado via JS. O filtro de cargo segue o mesmo padrão (multiseleção, vazio = todos os grupos).
- Período: dois `st.selectbox` "De"/"Até" (digitáveis — dá pra buscar o mês por texto). Chegamos a testar um único `st.select_slider` (duas alças), inspirado no filtro de período do RealizaDO, mas o usuário achou pouco funcional (só dá pra arrastar, não digitar) e pediu para voltar a algo em que seja possível escrever; o valor padrão, porém, passou a ser calculado (últimos 12 meses a partir do último mês com dado), o que o slider não tinha.
- Ordenação de colunas da tabela: no HTML é feita clicando no cabeçalho; no Streamlit foi implementada via seletor "Ordenar por" + seletor de direção, pois não há suporte nativo a clique-para-ordenar em tabelas HTML renderizadas via `st.html`.
- Barras (Admissões×Demissões, Saldo Líquido) com cantos arredondados (`marker_cornerradius`, requer `plotly>=5.24`).
- Rótulos de dados: só no maior e no menor ponto de cada série (não em todos os pontos), nos gráficos Turnover Real, Headcount Ativo, Saldo Líquido e Indicador legado — implementado em `charts._minmax_annotations`.

## Fechamento da V1 (2026-09-10)

Auditoria completa do projeto (código, segurança, dados) fechando a V1: login com
bloqueio por tentativas, busca sem acento, corte de 10 anos/eixo de meses
dinâmicos, `perm_meses` desativada (`OBSOLETO.md`), e visibilidade de dado que
falta na barra lateral (data do último sync + cargo/cidade fora do mapeamento).
Pendências que não bloqueiam a V1 (sync manual sem PAT, sem testes
automatizados, cobertura parcial de Gestor em desligados, 6 pessoas sem
cidade, etc.) ficaram registradas em `NEXTSTEPS.md` — não versionado, é nota
interna de acompanhamento, não documentação pra quem clonar o projeto.
