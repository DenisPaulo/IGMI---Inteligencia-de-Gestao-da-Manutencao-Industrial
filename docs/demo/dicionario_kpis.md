# Dicionário de KPIs (dataset demo)

Todos os números do dashboard demo são **sintéticos**. As fórmulas abaixo são as que estão implementadas em `sql/demo/30_kpis.sql` e `sql/demo/40_pareto_alertas.sql`, e cada uma tem check em `pmb/demo_quality.py` (QD18 a QD27).
As metas são **referências de mercado, indicativas**, não verdade universal. Várias vêm de fornecedores de software de manutenção (CMMS); o valor oficial da SMRP está no documento pago da associação.

## Conjuntos usados

| Conjunto | Definição |
|---|---|
| **Falha** | OS corretiva (emergencial ou planejada) não cancelada (`tipos_os.conta_como_falha = true`) |
| **Falha com parada** | falha com minutos de parada lançados no arquivo de paradas (contrato v2) |
| **Tempo programado** | dias do período × `horas_dia` × `dias_semana` ÷ 7 (seed `linhas.csv`) |
| **Horas de técnico** | Σ dos apontamentos (`activities.duration_in_minutes`) das OS concluídas |
| **OS planejada / reativa** | pelo tipo de OS (`tipos_os.csv`): só a corretiva emergencial é reativa |

## KPIs

| KPI | Fórmula (como está no SQL) | Grão | Referência / meta citada |
|---|---|---|---|
| **MTBF** (h) | (tempo programado − horas de parada) ÷ nº de falhas | equipamento (falhas dos subconjuntos sobem para o pai), linha, planta | definição clássica (SMRP) |
| **MTTR** (h) | Σ minutos de parada das falhas com parada ÷ nº de falhas com parada ÷ 60 | equipamento, linha, planta | definição clássica (SMRP); numerador e denominador do **mesmo conjunto** (QD20) |
| **Disponibilidade** | 1 − horas de parada ÷ tempo programado | equipamento, linha, planta, mês | componente do OEE (Disponibilidade × Desempenho × Qualidade) |
| **% planejada** | horas de técnico em OS planejadas ÷ horas de técnico totais | linha, planta | meta citada ≥ 85% |
| **% reativa** | horas de técnico em corretiva emergencial ÷ horas de técnico totais | linha, planta, mês | meta citada < 20% |
| **PM compliance** | ocorrências de plano fechadas até vencimento + tolerância ÷ ocorrências já vencidas (no prazo + atrasadas + vencidas abertas) | linha, planta, mês | meta citada > 90% |
| **Backlog** (semanas) | Σ horas restantes das OS abertas (estimada − já apontada, mínimo 0) ÷ horas por semana disponíveis para backlog da especialidade | especialidade | faixa citada 2–4 semanas (ou 4–6 de backlog executável) |
| **Aderência à programação** | OS planejadas programadas na semana e fechadas na mesma semana ÷ OS planejadas programadas na semana | semana, linha, planta | faixa saudável **40–90%**: abaixo de 40% o programa foi ignorado; acima de 90% a semana foi carregada de menos |
| **OS envelhecidas** | OS abertas há mais de `os_envelhecida_dias` (30) dias | linha, planta | prática de planejamento (OS > 30 dias) |
| **Custo de parada** | minutos de parada ÷ 60 × custo/h **fictício** do centro de custo da linha | OS, equipamento, linha, planta | só parada; hora de técnico nunca vira custo |
| **Pareto por modo** | Σ da medida (`pareto_medida`: minutos de parada ou nº de falhas) por modo; top `pareto_top` + **Outros** por último; % e % acumulado | planta, linha | prática de confiabilidade (top modos por horas paradas) |
| **Alerta de reincidência** | mesma falha (subconjunto + modo) **N vezes em X dias** (`reincidencia_n` = 3, `reincidencia_dias` = 15); 1 alerta por episódio, rearma X dias depois do último alerta | subconjunto + modo | regra de recorrência descrita em estudo de caso publicado (fonte de fornecedor) |
| **Qualidade do dado** | % de falhas sem modo, com modo "Outro/desconhecido", sem causa/mecanismo/ação; OS concluídas sem apontamento | planta | estudo acadêmico: > 50% das notificações com modo "outro/desconhecido" em uma instalação; monitorar o uso de "outros" (limite demo: 10%) |

## Taxonomia (ISO 14224, adaptada)

- **Hierarquia**: planta > linha > equipamento > subconjunto (`seeds/demo/equipamentos.csv`, campo `pai_id`).
- **Modo de falha** = o que se observa; **causa** = por que aconteceu; **mecanismo** = processo físico; **ação** = o que foi feito.
- Modos são **filtrados pela classe** do equipamento (robô ≠ transportador ≠ dosador): QD09 bloqueia modo de outra classe.
- **Criticidade** A/B/C (impacto × probabilidade): define a prioridade do alerta de reincidência.
- **Curva P-F**: inspeções preditivas (`PRED`) com intervalo menor que o P-F; achados viram corretiva planejada ("Achado na inspeção preditiva: …").

## Fontes (pesquisa de 21/10/2026)

- ISO 14224 (taxonomia de falhas e manutenção): https://www.iso.org/standard/64076.html · explicação didática: https://www.fabrico.io/blog/iso-14224-failure-taxonomy-codes/
- ISO 55000 (gestão de ativos): https://www.iso.org/standard/83053.html
- EN 13306 (terminologia de manutenção, catálogo): https://standards.iteh.ai/catalog/standards/cen/5af77559-b9ac-4b2c-9d8d-d9f0e9b7de4d/en-13306-2017
- SAE JA1011 (critérios de processo RCM): https://www.sae.org/standards/content/ja1011_200908/
- SMRP, métricas de boas práticas (documento completo para membros): https://smrp.org/learning-resources/smrp-library/best-practices-metrics-guidelines/
- Metas de mercado citadas (fornecedores de CMMS): https://www.getmaintainx.com/blog/beginners-guide-maintenance-kpis · https://eworkorders.com/cmms-industry-articles-eworkorders/important-metrics/
- Fórum de praticantes (backlog, PM compliance): https://exchange.smrp.org/discussion/work-management-metrics
- Planejamento e programação, aderência 40–90% (Plant Services): https://www.plantservices.com/planned-maintenance/planning-and-scheduling/article/11295301/understanding-the-math-of-maintenance-planning-and-scheduling
- Modo "outro/desconhecido" em notificações (PHM Society, 2021): https://doi.org/10.36001/phme.2021.v6i1.2792
- Curva P-F e agir antes do alarme: https://www.automationworld.com/products/control/article/13303224/predictive-maintenance-the-smart-way-to-cut-downtime
- Regra de recorrência "3 vezes em 15 dias" (estudo de caso de fornecedor): https://tractian.com/en/case-studies/bosch
