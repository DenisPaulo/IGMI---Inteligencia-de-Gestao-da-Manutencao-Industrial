# IGMI --- Inteligência de Gestão da Manutenção Industrial

## Visão do projeto e prompt mestre \| Versão 1.0

## 1. Visão

Criar uma plataforma independente de fornecedor que transforme dados de
manutenção e operação em informação confiável, análises de
confiabilidade e recomendações práticas para apoiar Engenharia, PCM,
Manutenção e Gestão Industrial.

A solução combina engenharia de dados, qualidade da informação,
indicadores determinísticos, inteligência artificial generativa e
dashboards. A IA amplia a capacidade de analisar, relacionar
informações, identificar padrões e organizar investigações; não
substitui a engenharia nem a decisão humana.

Perguntas que deverá ajudar a responder: - Quais linhas e equipamentos
mais impactam a produção? - Onde se concentram falhas e horas de
parada? - Quais problemas são recorrentes? - Como está o backlog e a
aderência preventiva? - Quais hipóteses merecem investigação? - Como
comprovar o resultado de uma melhoria?

## 2. Pontos fortes e princípios consolidados

### Arquitetura orientada a dados

Fluxo de referência:

``` text
Fontes -> Ingestão -> RAW -> SILVER -> GOLD -> Quality Checks
                                             |             |
                                         Dashboards    Camada IA
                                                           |
                                                  Agentes e ferramentas
                                                           |
                                                  Análises fundamentadas
```

A IA consulta dados aprovados pelos controles de qualidade, por
ferramentas específicas. Não recebe indiscriminadamente o banco inteiro.

### Separação de responsabilidades

-   SQL, Python e banco analítico calculam.
-   IA interpreta, investiga, correlaciona e comunica.
-   Especialistas validam hipóteses e aprovam ações.

MTTR, MTBF, disponibilidade, Pareto, horas de parada, backlog e
aderência preventiva devem ser calculados de forma determinística e
reproduzível. A IA não inventa nem recalcula informalmente indicadores.

### Qualidade e rastreabilidade

-   Dados reprovados em checks bloqueantes não devem ser tratados como
    confiáveis.
-   Cargas rejeitadas, erros e correções devem permanecer rastreáveis.
-   Origem, período, data e versão dos dados devem acompanhar as
    análises, quando possível.
-   A IA deve declarar quando a qualidade ou o volume dos dados
    limitarem uma conclusão.
-   Regras e testes existentes devem ser preservados.

### Métricas com significado definido

-   MTTR deve usar conjunto coerente de ordens e tempos.
-   Tempo de mão de obra e tempo de parada não devem ser confundidos.
-   Custos devem respeitar regras de origem e elegibilidade do negócio.
-   Medidas de naturezas diferentes não devem ser misturadas.
-   Criticidade deve usar critérios explícitos, documentados e
    aprovados.

### Segurança e independência

Começar com dados sintéticos. Não versionar credenciais, segredos,
arquivos `.env`, exportações reais ou bases operacionais. A camada de IA
será independente: se estiver indisponível, ingestão, transformações,
checks, indicadores e dashboards continuarão funcionando.

A primeira versão dos agentes será somente de leitura. Qualquer ação
futura que altere ordens, planos, cadastros ou sistemas exigirá
confirmação humana.

### Evidências antes de recomendações

Apresentar período, escopo, indicadores, volume de registros, ordens
relacionadas, tendências, limitações e evidências. Separar fatos,
interpretações, hipóteses e recomendações. Não declarar causa raiz sem
comprovação.

## 3. Escopo funcional

### Núcleo analítico

Ingestão, contratos, RAW/SILVER/GOLD, controles de qualidade,
rastreabilidade e consultas. Indicadores possíveis: OS
abertas/concluídas, backlog, MTTR, MTBF, horas de parada, Pareto,
reincidência, aderência preventiva, criticidade e qualidade do dado.

### Agente Analista de Confiabilidade

Analisa linhas e equipamentos, perdas, tendências, Pareto e
recorrências. Exemplo: "Analise a confiabilidade da linha LR-01 nos
últimos seis meses". Deve consultar ferramentas, verificar qualidade e
volume, apresentar indicadores, evidências, hipóteses e próximos passos.

### Motor de Criticidade e Priorização

Classificação determinística com critérios aprovados pela engenharia.
Critérios possíveis: impacto na produção, segurança, frequência de
falhas, tempo de reparo, parada, redundância e consequência da falha. A
IA explica a classificação e aponta lacunas, mas não inventa pesos ou
limites.

### Assistente DMAIC

Apoia Define, Measure, Analyze, Improve e Control: delimita problema,
reúne linha de base, organiza evidências e hipóteses, estrutura
alternativas e propõe acompanhamento. Hipóteses não são causas
comprovadas.

### Copiloto de Gestão da Manutenção

Responde perguntas em linguagem natural usando ferramentas autorizadas.
Exemplos: prioridades da semana, corretivas antigas, reincidências,
aderência preventiva e qualidade dos dados.

### Dashboards

Visões executiva, confiabilidade por linha/equipamento, backlog,
preventivas, Pareto, reincidência, qualidade, criticidade e análises dos
agentes. O dashboard tradicional deve continuar útil sem IA.

## 4. Arquitetura técnica de referência

``` text
Fontes -> Ingestão/RAW -> SILVER/GOLD -> Quality Checks
                                          |
                           +--------------+-------------+
                           |                            |
                       Dashboards                 Camada analítica
                       HTML / BI                  Python + DuckDB
                                                        |
                                               Ferramentas controladas
                                                        |
                                                  Orquestrador IA
                                                        |
                                      Analista | Criticidade | DMAIC | Copiloto
```

Tecnologias de referência: Python, DuckDB, SQL, Pandas quando
necessário, FastAPI, HTML/CSS/JavaScript, Power BI quando aplicável e
API de modelo de linguagem. LangGraph ou outra orquestração é opcional;
não começar com complexidade desnecessária.

Estrutura indicativa, a ajustar após inspeção do código:

``` text
projeto/
├── contrato/  dados_sinteticos/  seeds/
├── sql/{silver,gold}/
├── pmb/
│   ├── ingestion/  quality/  analytics/
│   └── intelligence/
│       ├── agents/{reliability,criticality,dmaic,copilot}.py
│       ├── tools/
│       ├── engine/
│       ├── api/
│       └── config/
├── tests/  docs/  run.py
```

## 5. Regras inegociáveis

1.  Não usar nomes de sistemas fornecedores no nome do produto, módulos,
    agentes ou identidade.
2.  Inspecionar repositório, contratos, testes e schemas antes de
    alterar código.
3.  Não remover nem enfraquecer checks existentes.
4.  Não permitir que a IA invente indicadores, registros, causas ou
    evidências.
5.  Não permitir SQL arbitrário sem controles.
6.  Usar consultas parametrizadas e somente leitura na primeira versão.
7.  Não permitir escrita em sistemas externos na primeira versão.
8.  Separar fatos, cálculos, interpretações, hipóteses e recomendações.
9.  Rastrear origem e contexto dos dados.
10. Manter pipeline e dashboards funcionais sem IA.
11. Começar com dados sintéticos e proteger dados reais e credenciais.
12. Não presumir nomes de tabelas, colunas, arquivos ou comandos:
    confirmar no código.
13. Criar testes para ferramentas, agentes, permissões e respostas.
14. Exigir confirmação humana para futuras ações operacionais.

## 6. Plano de evolução

**Fase 1 --- Inspeção:** mapear repositório, documentação, comandos,
schemas, tabelas GOLD, indicadores, testes e checks. Entrega: mapa
técnico e plano de integração.

**Fase 2 --- Ferramentas analíticas:** conexão DuckDB somente leitura;
funções Python específicas para KPIs, OS, Pareto, equipamentos e
reincidências; filtros, limites, validação e testes.

**Fase 3 --- Analista de Confiabilidade:** integração com modelo via
API, ferramentas autorizadas, respostas estruturadas, evidências,
limitações e testes para ausência de dados ou cargas reprovadas.

**Fase 4 --- API e interface:** FastAPI, integração web, filtros,
evidências e tratamento de indisponibilidade.

**Fase 5 --- Criticidade:** formalizar critérios com engenharia,
implementar motor determinístico e validar resultados.

**Fase 6 --- DMAIC:** estruturar projetos, linha de base, hipóteses,
planos e acompanhamento.

**Fase 7 --- Copiloto:** ampliar consultas em linguagem natural e
integrar módulos.

## 7. Padrão de qualidade das respostas

Toda resposta deve identificar escopo e período, usar apenas ferramentas
autorizadas, apresentar indicadores e evidências, separar fatos de
hipóteses, informar limitações, evitar causalidade não comprovada e
sugerir ações proporcionais às evidências.

Formato recomendado: 1. Resumo executivo; 2. Escopo e período; 3.
Qualidade e volume dos dados; 4. Indicadores; 5. Perdas e recorrências;
6. Hipóteses para investigação; 7. Recomendações; 8. Ordens e
evidências; 9. Limitações.

------------------------------------------------------------------------

# 8. PROMPT MESTRE PARA CRIAÇÃO DO PROJETO

Copie o texto abaixo para orientar um agente de desenvolvimento ou uma
conversa dedicada à implementação.

> Você é um **Arquiteto de Software, Engenheiro de Dados e Especialista
> em Gestão da Manutenção Industrial e Confiabilidade**, com experiência
> em Python, SQL, DuckDB, indicadores de manutenção, APIs e integração
> segura de IA.
>
> Sua missão é projetar e desenvolver uma plataforma de **Inteligência
> de Gestão da Manutenção Industrial**, que transforme dados de
> manutenção e operação em análises confiáveis, apoio à decisão e
> recomendações fundamentadas.
>
> **Identidade obrigatória:** a solução deve ter nome e identidade
> próprios, independentes de fornecedores. Não utilize nomes de sistemas
> de terceiros no nome do projeto, produto, módulos, agentes, pastas ou
> identidade visual. O nome de trabalho é IGMI --- Inteligência de
> Gestão da Manutenção Industrial.
>
> **Princípio arquitetural:** SQL, Python e banco analítico calculam; a
> IA interpreta, investiga relações, resume evidências e recomenda
> caminhos; especialistas humanos validam hipóteses e aprovam decisões.
> Nunca use o modelo de linguagem como fonte primária de indicadores.
>
> **Antes de programar:** inspecione árvore de diretórios, documentação,
> configurações, comandos, contratos, schemas, tabelas, views, testes e
> controles de qualidade. Mapeie o que já existe e apresente um plano
> antes de alterações. Não presuma nomes de tabelas, colunas, funções ou
> arquivos. Preserve funcionalidades, contratos e testes existentes.
>
> **Arquitetura:** utilize, conforme o projeto existente, Python,
> DuckDB, SQL, camadas RAW/SILVER/GOLD, Quality Checks, FastAPI,
> interface web/BI e API de modelo de linguagem. A camada de IA deve ser
> independente do pipeline.
>
> **Agentes previstos:** (1) Analista de Confiabilidade; (2) Motor de
> Criticidade e Priorização determinístico; (3) Assistente DMAIC; (4)
> Copiloto de Gestão da Manutenção. Desenvolva incrementalmente e comece
> pelo Analista de Confiabilidade.
>
> **Ferramentas:** implemente funções Python específicas para consultar
> OS, KPIs, Pareto, equipamentos, reincidências, backlog, preventivas,
> criticidade e qualidade. Use somente leitura na primeira versão,
> consultas parametrizadas, filtros e limites, validação, tratamento de
> erros e retornos estruturados com origem e período. Não permita SQL
> arbitrário nem exponha credenciais.
>
> **Segurança e qualidade:** dados reprovados em checks bloqueantes não
> podem ser tratados como confiáveis. Informe limitações, preserve
> rastreabilidade, não altere dados silenciosamente, comece com dados
> sintéticos e não permita escrita em sistemas externos na primeira
> versão. Separe fatos, interpretações, hipóteses e recomendações.
>
> **Método de trabalho:** inspecionar, documentar, propor, implementar o
> menor incremento útil, criar/atualizar testes, executar testes, listar
> arquivos alterados e explicar como executar. Não faça refatorações
> amplas sem justificativa e não remova testes para fazer a
> implementação passar.
>
> **Primeira entrega:** construir a fundação do Analista de
> Confiabilidade: conexão somente leitura com o banco; ferramentas para
> KPIs, OS, equipamentos, Pareto e reincidências; validação de qualidade
> e período; integração com modelo por API; resposta estruturada com
> evidências; testes automatizados; endpoint ou interface simples.
>
> **Pergunta de demonstração:** "Analise a confiabilidade da linha LR-01
> nos últimos seis meses." A resposta deve mostrar escopo, período,
> qualidade e volume, indicadores, perdas, recorrências, hipóteses,
> recomendações, OS relacionadas e limitações. Utilize dataset sintético
> somente depois de confirmar sua estrutura. Nunca invente dados para
> preencher lacunas.
>
> **Sucesso:** entregar inteligência útil e confiável sem comprometer
> integridade, rastreabilidade, segurança ou autonomia dos processos
> existentes. Priorize confiabilidade, clareza, manutenção simples e
> valor operacional --- não complexidade tecnológica ou efeitos
> demonstrativos de IA.

## 9. Decisões a confirmar

-   Nome definitivo e identidade visual;
-   Repositório e versão de código-base;
-   Schemas e tabelas disponíveis;
-   Definições oficiais dos indicadores;
-   Critérios e responsáveis pela matriz de criticidade;
-   Modelo de linguagem e orçamento de API;
-   Regras de acesso, autenticação e classificação dos dados;
-   Interface prioritária e ambiente de execução.

**Custos:** APIs de IA normalmente são cobradas conforme modelo e volume
de tokens de entrada e saída. A assinatura do ChatGPT não deve ser
presumida como crédito de API. Podem existir custos de hospedagem,
armazenamento, observabilidade, infraestrutura e BI. A estimativa deve
ser feita com testes reais e preços oficiais vigentes.

## 10. Princípio final

**A inteligência artificial deve tornar a gestão da manutenção mais
capaz de enxergar, compreender, priorizar e agir --- mas a confiança
deve continuar vindo dos dados, dos métodos de engenharia e da validação
humana.**
