# Contexto do projeto

## Objetivo

Recriar em Streamlit o dashboard de turnover comercial existente em um painel HTML local, mantendo os cálculos atuais, com fidelidade visual aos gráficos e componentes do painel original, e preparando a arquitetura para uma futura fonte Databricks.

## Estado atual

- V5: `app.py` é um roteador fino (autenticação + `st.navigation`/`st.Page`); o conteúdo antes nele agora vive em `app_pages/dashboard.py`. Segunda página, `app_pages/comparativo_turnover.py`, compara a fórmula de turnover do Comercial (efetivo médio) com a do D.O. (efetivo do fechamento do mês anterior), com uma recomendação de qual usar oficialmente.
- Barra lateral: logo do projeto (`assets/icons/logo_sidebar.png`) no topo acima das abas, ícones Material Symbols por página, saudação "Olá, {nome}" + botão Sair abaixo da navegação.
- Código organizado em módulos (`src/data_logic.py`, `src/charts.py`, `src/components.py`, `src/styles.py`, `src/auth.py`, `src/auth_ui.py`).
- Dados lidos do payload JSON já presente no HTML original (sem conexão Databricks) — ver "Origem dos dados e limitações" abaixo.
- Filtros: cidade (multiseleção, exibida como "Cidade/UF"), grupo de cargo (multiseleção com 7 grupos agregados), período (`De`/`Até`, dois `selectbox` digitáveis) e status (multiseleção "Ativo"/"Desligado", vazio = ambos).
- Período padrão calculado dinamicamente: últimos 12 meses a partir do último mês com dado (`last_active_month`), não um valor fixo — hoje resulta em Ago/25→Jul/26.
- KPIs (6 cartões), cinco visualizações (Plotly, recriando os gráficos Chart.js do HTML original, barras com cantos arredondados e rótulo do maior/menor valor em 4 delas) e tabela analítica de colaboradores com busca (nome, cargo, cidade **e ID**), ordenação e paginação (20 por página).
- Permanência exibida de forma humanizada ("X anos e X meses" / "X anos" / "X meses" / "X dias"), com cor por faixa.
- Um indicador complementar abaixo dos gráficos principais: Permanência Média (Ativos × Desligados).
- Paleta de cores, tipografia (DM Sans) e estilo de cartões/badges/tabela replicados via CSS injetado (`src/styles.py`) e tema em `.streamlit/config.toml`.

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
- **Cuidado de segurança aplicado**: a query original que o usuário colou tinha `nome_gestor = '<nome de um diretor>'` (nome de um diretor) escrito direto no SQL. Como esse script vai para o repositório público, o nome foi movido para `.streamlit/secrets.toml` -> `[databricks].gestor_referencia` (fora do git) em vez de ficar hardcoded no `.py`.
- Testado localmente: reconstrução do schema (`ALTER TABLE ... ADD COLUMN IF NOT EXISTS`) não quebrou os 596 registros já carregados; simulação com dados sintéticos no formato que a query do Databricks devolve (antes do rename `Cargo Atual`->`Cargo Atual2` etc.) validou o caminho `sync_from_databricks.fetch_from_databricks()` -> `_neon_people.replace_people_rows()` sem erro. **Não testado**: a conexão OAuth real com o Databricks (exige navegador interativo, que o assistente não tem neste ambiente) — o usuário precisa rodar `sync_from_databricks.py` uma vez para validar isso na prática.

## Limitações da base (colunas disponíveis)

A base (hoje na tabela `people_rows` do Neon — ver seção anterior) tem estas colunas por colaborador: `Registro, Nome, Cargo Atual2, Grupo, Cidade, Admissão, Demissão, Status, Perm_meses`. **Não há campo de UF/Estado nem de gestor/gerente responsável.**

- **UF da cidade**: como a base não traz o estado, `src/data_logic.py:CITY_UF` mapeia cada uma das 43 cidades para sua UF manualmente (conhecimento geográfico geral, não uma coluna da base). Convém alguém do time validar essa lista, em especial cidades menos conhecidas (`Bálsamo`, `Nova Marilândia`, `Piratininga`, `Rio Preto` etc.). "Lotes" não é uma cidade real (é um segmento/tipo de operação) e fica sem UF.
- **Grupos de cargo**: a base atual só tem 7 valores em `Cargo Atual2` (`Analista de Parcerias`, `Analista de Vendas Junior`, `Assistente de Vendas`, `Auxiliar de Vendas`, `Coordenador Comercial`, `Gerente Comercial`, `Supervisor de Vendas`). O mapeamento pedido citava títulos adicionais (`Gerente de Vendas`, `Gerente de Lotes Comercial`, `Coordenador de Vendas`, `Analista de Suporte de Vendas`, `Analista de Lotes Comerciais`) que **não existem nesta base**; foram incluídos em `CARGO_GROUP_MAP` por precaução (caso apareçam em uma carga futura), mas hoje não têm efeito.
- **Executivos/Gestores — adiado**: pedido para filtrar por gestor e montar um "Ranking de Executivos por turnover" usando 7 nomes específicos. A base atual **não tem nenhuma coluna ligando colaborador → gestor**. Procurei em outras planilhas da pasta `People Analytics` em busca de um de/para; o único achado foi `00 - Central de Gente & Dados/.OLD/Relatórios Base/Movimentações e Admissões_Abril até Julho_Dir Comercial.xlsx` (aba "Admissões"), que tem colunas `Gestor`/`Nome Gestor`/`Diretoria`/`Estado` — mas é um extrato parcial (só admissões de abril a julho de um ano), não cobre os 596 colaboradores da base atual. Por decisão do usuário (2026-09-08), fica para quando a base vier do Databricks, que deve trazer esse campo. Quando chegar: adicionar o filtro "Executivos" (classificando os 7 nomes informados como grupo "Executivos") e o ranking de turnover por gestor (mesma fórmula de turnover real, agregada por gestor em vez de cidade/cargo).

## Indicadores complementares implementados

- **Permanência Média: Ativos × Desligados** (`app.py`, chama `filter_people(..., status_selected=[])` para sempre comparar os dois grupos, independente do filtro de Status escolhido): tempo de casa médio dos dois grupos, no filtro de cidade/cargo/período atual.

## Outras sugestões de indicadores (ainda não implementadas)

- **Turnover por grupo de cargo**: ranking de turnover real médio por Auxiliar/Assistentes/Analistas/…/Gerente — mesmo cálculo do dashboard, agregado por `Grupo` em vez de cidade.
- **Turnover por cidade/UF**: ranking de cidades (ou UFs) com maior turnover no período — identifica onde a rotatividade está concentrada.
- **Attrition precoce**: % de desligados com permanência < 3 meses sobre o total de desligados no período — indicador clássico de qualidade de contratação/onboarding.
- **Sazonalidade de desligamentos**: desligamentos por mês-calendário (Jan, Fev, …) agregando todos os anos, para ver se há meses historicamente mais críticos.
- **Curva de retenção por coorte de admissão** (% ainda ativo após 3/6/12 meses): chegou a ser implementada e depois removida a pedido do usuário (2026-09-08) — ver Changelog 0.6/0.7.1/0.7.2. Fica registrada aqui como ideia caso queiram retomar.

Não é possível (sem dado novo): turnover voluntário vs. involuntário (não há campo de motivo do desligamento).

## Regras preservadas

- Turnover real mensal: `[(admissões + desligamentos) / 2] / efetivo médio do mês * 100`.
- Efetivo médio: média do headcount no início e no fim do mês.
- Indicador legado: `desligamentos / headcount do mês anterior * 100`.
- Médias dos indicadores consideram apenas valores maiores que zero.
- A tabela inclui colaboradores ativos em qualquer parte do período selecionado.

## Decisões de fidelidade visual

- Gráficos Admissões×Demissões e Saldo Líquido: barras (como no Chart.js original), não linhas.
- Turnover real e Indicador legado: linha com preenchimento de área e linha tracejada de média do período, igual ao HTML original.
- Tabela: badges coloridos para Cargo/Status e permanência colorida por faixa (`<3m` vermelho, `<12m` âmbar, `≥12m` verde), igual às classes `.badge`/`.perm-*` do HTML.
- A multiseleção de cidade do HTML original (painel custom com checkbox "selecionar todas") foi substituída pelo `st.multiselect` nativo do Streamlit — funcionalmente equivalente (vazio = Global/todas), mas sem recriar o dropdown customizado via JS. O filtro de cargo segue o mesmo padrão (multiseleção, vazio = todos os grupos).
- Período: dois `st.selectbox` "De"/"Até" (digitáveis — dá pra buscar o mês por texto). Chegamos a testar um único `st.select_slider` (duas alças), inspirado no filtro de período do RealizaDO, mas o usuário achou pouco funcional (só dá pra arrastar, não digitar) e pediu para voltar a algo em que seja possível escrever; o valor padrão, porém, passou a ser calculado (últimos 12 meses a partir do último mês com dado), o que o slider não tinha.
- Ordenação de colunas da tabela: no HTML é feita clicando no cabeçalho; no Streamlit foi implementada via seletor "Ordenar por" + seletor de direção, pois não há suporte nativo a clique-para-ordenar em tabelas HTML renderizadas via `st.html`.
- Barras (Admissões×Demissões, Saldo Líquido) com cantos arredondados (`marker_cornerradius`, requer `plotly>=5.24`).
- Rótulos de dados: só no maior e no menor ponto de cada série (não em todos os pontos), nos gráficos Turnover Real, Headcount Ativo, Saldo Líquido e Indicador legado — implementado em `charts._minmax_annotations`.

## Próxima etapa

Após a validação da primeira execução, conectar a camada de carregamento ao Databricks e registrar a origem, credenciais e consulta sem alterar as regras de negócio.
