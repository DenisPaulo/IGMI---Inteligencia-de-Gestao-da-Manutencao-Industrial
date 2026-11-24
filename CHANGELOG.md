## 0.3.3.1 — Documentação e nomenclatura pública (2026-11-24)

- README atualizado para a versão 0.3.3.1, com tabela de versões até esta entrega e links para os guias existentes em `docs/`.
- Capturas do dashboard de demonstração descritas a partir dos arquivos atuais em `docs/img/`.
- Aba de comparação do dashboard demo unificada nos identificadores `LR-01` e `LR-02` (navegação, título, colunas e legendas).
- Títulos da prévia HTML e da árvore nos prints de terminal passam a usar o nome IGMI; o warehouse padrão do pipeline principal fica em `warehouse/igmi.duckdb`.
- A coluna `link` de `gold.fato_os` permanece no contrato, sem URL de fornecedor.
- Relatório determinístico descreve a IA opcional do copiloto e de `igmi-ia` (confirmação `AUTORIZAR`, warehouse sintético local).
- Nenhuma alteração em regras de KPIs, Quality Checks, custos ou consulta somente leitura.

## 0.3.3 — Nomenclatura fictícia e portfólio (2026-11-17)

- Identificadores técnicos migrados para `LR-01` e `LR-02`; nomes públicos `Linha Robotizada_1` e `Linha Robotizada_2`.
- Hierarquias de equipamentos, planos preventivos, centros de custo, dados sintéticos e simulação preservados com novos prefixos.
- Copiloto, seletores, dashboard, testes, CI e documentos atualizados; IDs explícitos reconhecem `LR-01-RB01` etc.
- Ajustada a sintaxe JavaScript para chaves com hífen (`L['LR-01']`), preservando gráficos e nomes amigáveis na interface.
- CLI multilinha e fixture de testes do pacote-base restaurados para preservar a confirmação `AUTORIZAR`.
- Imagens antigas do dashboard devem ser removidas e recriadas após regenerar a demo; consulte `docs/IGMI_0.3.3.md`.
- Nenhuma alteração em regras de KPIs, Quality Checks, custos ou consulta somente leitura.

## 0.3.2.1 — Estabilização das respostas e README (2026-11-17)

- Corrigida a seleção de KPIs quando o usuário solicita explicitamente disponibilidade em pergunta composta.
- Alertas do mesmo modo/equipamento são apresentados em grupo, com OS distintas e sem somar janelas sobrepostas.
- Fluxo de interpretação planejada admite até 3 hipóteses curtas; comandos anteriores mantêm o limite anterior. Números inventados, terminologia inconsistente e excesso continuam bloqueados.
- Se o usuário solicitar explicitamente três ações, a saída precisa conter três recomendações ou permanece bloqueada, sem repetição paga.
- Reforçadas as instruções para recomendações práticas, testáveis e não categóricas; uma chamada autorizada no máximo por turno.
- Atualizado README com arquitetura, comandos Git Bash, segurança, marcos, limitações e exemplos; guia de patch e rollback adicionado.
- Novos testes de regressão com IA simulada, sem chamadas pagas. **Validação integrada completa ainda depende do ambiente Windows/DuckDB.**

## 0.3.2 — Planejamento inteligente de consultas (2026-11-17)

- Adicionado roteamento local multi-intenção, sem chamadas de IA para escolher ferramentas.
- Consultas deduplicadas: KPIs, ranking de paradas, reincidências e MTTR em uma pergunta.
- Matriz de cobertura por intenção, evidências separadas por alvo e fatos numéricos determinísticos.
- Payload limitado e consentimento explícito: uma chamada paga por turno, no máximo.
- Sem evidências suficientes, mantém resposta parcial e não aciona API.
- Exportação com plano de ferramentas/cobertura; testes de regressão sem rede.
- Patch incremental; sem alterações em SQL, pipeline, warehouse ou arquivos sensíveis.

## 0.3.1 — conversação robusta e análises multialvo (2026-11-17)

- Novo `/pergunta` para até 12 linhas e 1.200 caracteres; `/fim` conclui e `/cancelar` descarta.
- Consentimento por turno alterado para confirmação literal `AUTORIZAR`, após encerrar a pergunta, sem autorização por `sim` ou `s`.
- Cobertura do robô e da mesa de ventosas com evidências distintas; omissão de alvo pela IA bloqueia a interpretação sem retry pago.
- Consultas multialvo limitadas a 30 registros e recortadas antes do envio ao modelo; dados ausentes no recorte geram resposta parcial sem IA.
- Contexto ambíguo pede esclarecimento. Entrada e Markdown exportado sanitizados sem perder acentos e quebras de linha.
- Histórico completo da sessão é exportado apenas sob comando explícito; nenhum salvamento automático.
- Testes específicos sem API real: 76 aprovados + 7 subtestes; validação da suíte completa depende do DuckDB no Windows.
- Patch incremental apenas com arquivos alterados/adicionados.

## 0.3.0 — copiloto de confiabilidade econômico (2026-11-17)

- Adicionado comando `python run.py igmi-chat`: perguntas objetivas offline e interpretação IA opcional.
- Roteamento determinístico de consultas GOLD, com limite e evidências por turno.
- Confirmação por pergunta antes de usar API paga; até uma chamada por turno e teto local por sessão.
- Retenção apenas de contexto mínimo na memória; cache invalidado por linha/carga/arquivo.
- Exportação Markdown explícita e auditoria por pergunta (chamadas e tokens).
- Preservados `igmi`, `igmi-ia`, validadores de IA e controles de qualidade.
- Testes offline adicionados; suíte completa requer DuckDB no ambiente Windows.
- Entrega incremental somente com arquivos novos ou alterados.

## 0.2.1 — economia de tokens e precisão (2026-11-17)

- CLI usa nova implementação econômica: uma chamada à API por análise, sem tool-calling iterativo.
- Recorte controlado de resultados antes do envio ao modelo; dados completos permanecem no JSON de auditoria.
- Fatos numéricos e conversões de unidades gerados por Python; IA apenas interpreta qualitativamente.
- Interpretação inválida bloqueada, com fatos determinísticos preservados e sem repetição paga.
- Regressões automatizadas sem uso real de API; mantém consultas somente leitura e controles QD existentes.
- Patch distribuído somente com arquivos alterados; código legado preservado.

## 0.2.0 — ajuste de instruções e diagnóstico do validador (2026-11-17)

- Instruções à IA refinadas para evitar números novos em campos de interpretação.
- Rejeição por número sem evidência agora informa o campo específico; nenhuma
  validação foi removida ou flexibilizada.
- Incluídos testes de regressão do diagnóstico e das instruções.
- Sem reenvio automático à API: nova chamada só ocorre por comando explícito.

# Histórico — IGMI

## 0.2.0 — 2026-11-17

- Adicionado Analista de Confiabilidade com IA por API opcional (Responses API / chamadas de função).
- Criado comando `python run.py igmi-ia` com autorização explícita de uso pago.
- Preservado `python run.py igmi` determinístico e offline.
- Criada validação de linha e período fechado; bloqueio de filtros que não correspondam aos KPIs disponíveis.
- Criada allowlist de oito ferramentas de consulta read-only e limites de chamadas.
- Adicionada resposta JSON estruturada, IDs de evidência e validação básica de números.
- Evidenciada diferença entre indicadores globais de qualidade e KPIs da linha.
- Adicionados testes em `tests_igmi/test_ia.py` com cliente simulado (sem pagamento).
- Adicionadas dependências opcionais, template de ambiente e documentação de Git Bash.

**Validação:** 25 testes `tests_igmi` passaram neste ambiente; a suíte completa depende de DuckDB e deve ser rodada no Windows do usuário. Nenhuma chamada real à API foi realizada.

## 0.1.0 — fundação analítica

- Preservados pipelines de manutenção e demonstração.
- Criado relatório determinístico de confiabilidade, modo read-only.
- Integrado bloqueio por 27 verificações de qualidade da demo.
- Usuário validou 106 testes com Python no Windows.
