# IGMI — Entrega 0.1.0 e próximos passos

## O que foi feito

1. Inspeção da estrutura recebida: dois pipelines (principal e demonstração), contratos, SQL, dados sintéticos, testes, documentação e CI.
2. Preservação do pipeline original e de seus **18 checks principais** e **27 checks QD da demonstração** (arquivos originais mantidos).
3. Criação do pacote **`igmi/`** para separar a camada nova do código existente em `pmb/`.
4. Ferramentas de consulta controladas à GOLD: KPIs, equipamentos, Pareto, alertas de reincidência, OS, tendência mensal, backlog e qualidade do dado.
5. Abertura exclusiva em **modo somente leitura**, com SQL fixo e parâmetros validados; nenhuma ferramenta que execute SQL livre.
6. Gate de qualidade: executar os 27 checks existentes antes de qualquer consulta; bloquear se algum falhar, se a quantidade de checks estiver diferente de 27 ou se a carga não estiver OK.
7. Primeiro Analista de Confiabilidade **determinístico**, com contexto do dataset, recomendações para validação humana, OS relacionadas e hipóteses explicitamente não comprovadas.
8. Saída de relatório em Markdown e JSON; comando adicionado ao `run.py`.
9. Prompt Mestre de referência copiado para `docs/igmi/PROMPT_MESTRE.md`.
10. Testes de unidade adicionais com conectores simulados; não dependem de API de IA.

## Estado da validação neste ambiente

- A revisão dos arquivos e a compilação sintática Python foram realizadas.
- Os testes unitários isolados podem ser executados sem DuckDB.
- **Limitação:** a dependência `duckdb==1.5.6` não estava instalada no ambiente que montou a entrega e não houve acesso a um pacote instalável para completar os testes de integração. Assim, **não se afirma que o pipeline completo passou** neste ambiente. Os testes e a CI originais foram preservados e devem ser executados no computador com dependências instaladas.
- A ausência de execução do pipeline aqui não significa que os testes originais falharam: significa **não executados** neste ambiente.

## Como executar no Windows (PowerShell)

```powershell
# Abra o PowerShell na pasta IGMI
py -m pip install -r requirements.txt

# Constrói o pipeline principal e testa seus checks
py run.py all

# Gera o conjunto sintético e o warehouse de demonstração
py run.py simular demo demo-preview

# Gera relatório da primeira análise para LR-01
py run.py igmi --linha LR-01 --formato markdown --saida export/igmi_relatorio_LR-01.md

# Consulta uma segunda linha em JSON
py run.py igmi --linha LR-02 --formato json --saida export/igmi_LR-02.json

# Executa a suíte original e as adições
py run.py test
```

Relatórios ficam em `export/`, ignorado pelo Git. O dashboard permanece em `export/demo_dashboard.html`.

## Atenção ao período

O dataset sintético atual representa **01/04/2026 a 30/09/2026**. A análise usa **esse período completo**, mesmo que a solicitação mencione “últimos seis meses”. Ela **não** calcula seis meses móveis a partir do dia atual. Isso impede apresentar KPIs do intervalo errado como se fossem atuais. O suporte a qualquer intervalo de datas deverá calcular novamente as métricas de acordo com os dicionários de KPI e passar pelos controles apropriados.

## Próximos passos de desenvolvimento

**1. Validação local:** instalar dependências, executar `all`, `simular demo demo-preview`, `igmi` e `test`. Conferir os relatórios gerados para LR-01 e LR-02, e investigar qualquer erro antes de integrar IA.

**2. Testes adicionais e cobertura:** testar com banco realmente modificado (QD reprovado) e garantir bloqueio total. Conferir que nenhum valor da camada generativa poderá escapar do conjunto de ferramentas aprovadas.

**3. Analista de Confiabilidade com modelo de linguagem (opcional):** o copiloto (`igmi-chat`) e o comando `igmi-ia` oferecem interpretação qualitativa sobre fatos calculados em Python, com confirmação `AUTORIZAR` e no máximo uma chamada por turno. O uso com dados reais permanece condicionado a controles, aprovação e política de dados.

**4. API e dashboard:** integrar FastAPI com autenticação, permissões e rate limit; adicionar interface no dashboard sem remover a versão offline.

**5. Criticidade:** formalizar pesos, critérios e classes com engenharia. O motor calcula determinísticamente; IA apenas explica.

**6. DMAIC e Copiloto:** avançar conforme as ferramentas analíticas e os controles estiverem estabilizados.

## Regras inegociáveis

- Nome do projeto e dos módulos novos independente de fornecedor: **IGMI**.
- Código anterior do pacote `pmb/` fica como legado técnico para evitar regressões; não integra o nome público do produto.
- Sem dados reais, segredos, SQL livre ou escrita por agentes na versão inicial.
- Nunca usar um resultado com QD reprovado.
- Nunca apresentar correlação como causa raiz comprovada.

**Histórico Git:** o pacote de entrega `.rar` não inclui a pasta `.git` do arquivo original, para não distribuir metadados e configurações de repositório. Para preservar os commits e a origem remota, copie as mudanças para o clone Git que você já utiliza.
