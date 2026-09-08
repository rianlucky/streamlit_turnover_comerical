# Contexto do projeto

## Objetivo

Recriar em Streamlit o dashboard de turnover comercial existente em `assets/painel_cidade_CLT_media_turnover.html`, mantendo os cálculos atuais, com fidelidade visual aos gráficos e componentes do painel original, e preparando a arquitetura para uma futura fonte Databricks.

## Estado atual

- V4: código organizado em módulos (`src/data_logic.py`, `src/charts.py`, `src/components.py`, `src/styles.py`) e `app.py` como orquestrador enxuto.
- Dados lidos do payload JSON já presente no HTML original (sem conexão Databricks) — ver "Origem dos dados e limitações" abaixo.
- Filtros: cidade (multiseleção, exibida como "Cidade/UF"), grupo de cargo (multiseleção com 7 grupos agregados), período (`De`/`Até`, dois `selectbox` digitáveis) e status (multiseleção "Ativo"/"Desligado", vazio = ambos).
- Período padrão calculado dinamicamente: últimos 12 meses a partir do último mês com dado (`last_active_month`), não um valor fixo — hoje resulta em Ago/25→Jul/26.
- KPIs (6 cartões), cinco visualizações (Plotly, recriando os gráficos Chart.js do HTML original, barras com cantos arredondados e rótulo do maior/menor valor em 4 delas) e tabela analítica de colaboradores com busca (nome, cargo, cidade **e ID**), ordenação e paginação (20 por página).
- Permanência exibida de forma humanizada ("X anos e X meses" / "X anos" / "X meses" / "X dias"), com cor por faixa.
- Dois indicadores complementares abaixo dos gráficos principais: Permanência Média (Ativos × Desligados) e Curva de Retenção por Coorte de Admissão (3/6/12 meses).
- Paleta de cores, tipografia (DM Sans) e estilo de cartões/badges/tabela replicados via CSS injetado (`src/styles.py`) e tema em `.streamlit/config.toml`.

## Origem dos dados e limitações (V4)

A única fonte de dados é `assets/painel_cidade_CLT_media_turnover.html` (payload `ALL_ROWS`), com estas colunas por colaborador: `Registro, Nome, Cargo Atual2, Grupo, Cidade, Admissão, Demissão, Status, Perm_meses`. **Não há campo de UF/Estado nem de gestor/gerente responsável.**

- **UF da cidade**: como a base não traz o estado, `src/data_logic.py:CITY_UF` mapeia cada uma das 43 cidades para sua UF manualmente (conhecimento geográfico geral, não uma coluna da base). Convém alguém do time validar essa lista, em especial cidades menos conhecidas (`Bálsamo`, `Nova Marilândia`, `Piratininga`, `Rio Preto` etc.). "Lotes" não é uma cidade real (é um segmento/tipo de operação) e fica sem UF.
- **Grupos de cargo**: a base atual só tem 7 valores em `Cargo Atual2` (`Analista de Parcerias`, `Analista de Vendas Junior`, `Assistente de Vendas`, `Auxiliar de Vendas`, `Coordenador Comercial`, `Gerente Comercial`, `Supervisor de Vendas`). O mapeamento pedido citava títulos adicionais (`Gerente de Vendas`, `Gerente de Lotes Comercial`, `Coordenador de Vendas`, `Analista de Suporte de Vendas`, `Analista de Lotes Comerciais`) que **não existem nesta base**; foram incluídos em `CARGO_GROUP_MAP` por precaução (caso apareçam em uma carga futura), mas hoje não têm efeito.
- **Executivos/Gestores — adiado**: pedido para filtrar por gestor e montar um "Ranking de Executivos por turnover" usando 7 nomes específicos. A base atual **não tem nenhuma coluna ligando colaborador → gestor**. Procurei em outras planilhas da pasta `People Analytics` em busca de um de/para; o único achado foi `00 - Central de Gente & Dados/.OLD/Relatórios Base/Movimentações e Admissões_Abril até Julho_Dir Comercial.xlsx` (aba "Admissões"), que tem colunas `Gestor`/`Nome Gestor`/`Diretoria`/`Estado` — mas é um extrato parcial (só admissões de abril a julho de um ano), não cobre os 596 colaboradores da base atual. Por decisão do usuário (2026-09-08), fica para quando a base vier do Databricks, que deve trazer esse campo. Quando chegar: adicionar o filtro "Executivos" (classificando os 7 nomes informados como grupo "Executivos") e o ranking de turnover por gestor (mesma fórmula de turnover real, agregada por gestor em vez de cidade/cargo).

## Indicadores complementares implementados

- **Permanência Média: Ativos × Desligados** (`app.py`, chama `filter_people(..., status_selected=[])` para sempre comparar os dois grupos, independente do filtro de Status escolhido): tempo de casa médio dos dois grupos, no filtro de cidade/cargo/período atual.
- **Curva de Retenção por Coorte de Admissão** (`data_logic.retention_curve`): para cada mês de admissão, % da leva ainda ativa após 3/6/12 meses; só calcula um horizonte quando já passou tempo suficiente (compara com `last_active_month`). Resumo com média ponderada pelo tamanho de cada coorte (`weighted_retention`) e gráfico com as últimas 18 coortes elegíveis. Usa cidade/cargo do filtro atual; não considera período nem status (é uma visão histórica por natureza).

## Outras sugestões de indicadores (ainda não implementadas)

- **Turnover por grupo de cargo**: ranking de turnover real médio por Auxiliar/Assistentes/Analistas/…/Gerente — mesmo cálculo do dashboard, agregado por `Grupo` em vez de cidade.
- **Turnover por cidade/UF**: ranking de cidades (ou UFs) com maior turnover no período — identifica onde a rotatividade está concentrada.
- **Attrition precoce**: % de desligados com permanência < 3 meses sobre o total de desligados no período — indicador clássico de qualidade de contratação/onboarding.
- **Sazonalidade de desligamentos**: desligamentos por mês-calendário (Jan, Fev, …) agregando todos os anos, para ver se há meses historicamente mais críticos.

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
