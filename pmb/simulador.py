"""Simulador DETERMINÍSTICO de OS de manutenção (dados 100% SINTÉTICOS) no schema do Mobility Data Connector.

Gera ~250 OS em ~6 meses para as linhas LR-01 e LR-02 (seeds/demo/): corretivas emergenciais e planejadas,
preventivas e preditivas por plano (no prazo, atrasadas, vencidas), melhorias, backlog aberto e reincidências
(algumas falhas repetem de propósito para disparar o alerta "N vezes em X dias").
Classificação ISO 14224 (tipo, modo, causa, mecanismo, ação, plano) vai em tags, como num CMMS real.
Paradas de linha vão num CSV separado no formato do contrato de parada v2 (id_lancamento, os_ref, hora_inicio, duracao_min, acao).
Técnicos aparecem só como FUNÇÃO (ex.: "Técnico Mec 1"). Mesma semente -> mesmos bytes.

Uso: python run.py simular   (grava em dados_sinteticos/demo/)
"""
import csv
import random
from datetime import date, datetime, timedelta
from pathlib import Path

from pmb import config

SEEDS = config.SEEDS / "demo"
SAIDA = config.ROOT / "dados_sinteticos" / "demo"

# Perfil sintético de falhas: subconjunto -> (falhas esperadas no período, {modo: peso}).
PERFIL = {
    "LR-01-RB01-FER": (11, {"RB-FER": 8, "RB-COL": 2}),
    "LR-01-RB01-EIX": (3, {"RB-VIB": 2, "RB-POS": 1}),
    "LR-01-RB01-CTL": (5, {"RB-SRV": 3, "RB-POS": 2}),
    "LR-01-TR01-COR": (5, {"TR-DES": 3, "TR-TRV": 2}),
    "LR-01-TR01-SEN": (3, {"TR-SEN": 1}),
    "LR-01-TR02-COR": (2, {"TR-TRV": 2, "TR-VIB": 1}),
    "LR-01-DS01-BIC": (7, {"DS-ENT": 5, "DS-VAZ": 1, "DS-VEX": 1}),
    "LR-01-VI01-CAM": (5, {"VI-LEI": 4, "VI-ILU": 1}),
    "LR-01-CL01-IO": (2, {"CL-IO": 1}),
    "LR-01-CL01-RED": (4, {"CL-COM": 3, "CL-PRG": 1}),
    "LR-01-MS01-VEN": (9, {"MS-VEN": 1}),
    "LR-01-MS01-VAC": (3, {"MS-VAC": 3, "MS-VAR": 1}),
    "LR-02-RB01-FER": (5, {"RB-FER": 3, "RB-COL": 2}),
    "LR-02-RB01-EIX": (3, {"RB-VIB": 2, "RB-POS": 1}),
    "LR-02-RB01-CTL": (3, {"RB-SRV": 2, "RB-POS": 1}),
    "LR-02-TR01-COR": (4, {"TR-DES": 2, "TR-TRV": 2}),
    "LR-02-TR01-SEN": (3, {"TR-SEN": 1}),
    "LR-02-TR02-COR": (5, {"TR-DES": 3, "TR-VIB": 2}),
    "LR-02-TR03-COR": (2, {"TR-TRV": 1}),
    "LR-02-DS01-BIC": (11, {"DS-ENT": 8, "DS-VAZ": 1}),
    "LR-02-DS01-ROS": (4, {"DS-VAZ": 2, "DS-VEX": 1}),
    "LR-02-VI01-CAM": (4, {"VI-LEI": 3, "VI-COM": 1}),
    "LR-02-CL01-IO": (2, {"CL-IO": 2, "CL-PRG": 1}),
    "LR-02-CL01-RED": (2, {"CL-COM": 1}),
    "LR-02-MS01-VEN": (9, {"MS-VEN": 1}),
    "LR-02-MS01-VAC": (4, {"MS-VAC": 2, "MS-VAR": 1}),
}
# Reincidências injetadas (subconjunto, modo, datas). As 3 primeiras disparam o alerta 3x/15 dias; a última NÃO (21 dias).
REINCIDENCIAS = [
    ("LR-01-RB01-FER", "RB-FER", ["2026-07-06", "2026-07-10", "2026-07-14", "2026-07-17"]),
    ("LR-02-MS01-VEN", "MS-VEN", ["2026-08-03", "2026-08-08", "2026-08-12"]),
    ("LR-02-DS01-BIC", "DS-ENT", ["2026-05-11", "2026-05-19", "2026-05-24"]),
    ("LR-02-VI01-CAM", "VI-ILU", ["2026-06-01", "2026-06-12", "2026-06-22"]),
]
# Reparo típico (min) por modo, e (causa, mecanismo, ação) plausíveis.
REPARO = {"RB-COL": 50, "RB-POS": 40, "RB-SRV": 70, "RB-VIB": 120, "RB-FER": 45, "TR-TRV": 40, "TR-DES": 30, "TR-SEN": 20,
          "TR-VIB": 60, "DS-ENT": 35, "DS-VAZ": 35, "DS-VEX": 45, "VI-LEI": 20, "VI-COM": 25, "VI-ILU": 30, "CL-COM": 45,
          "CL-IO": 60, "CL-PRG": 40, "MS-VAC": 35, "MS-VEN": 40, "MS-VAR": 25, "XX-OUT": 20}
CLASSIF = {
    "RB-COL": [("C-OPE", "M-SOB", "A-REI"), ("C-PRJ", "M-SOB", "A-AJU")], "RB-POS": [("C-MAN", "M-SOFT", "A-AJU"), ("C-DES", "M-DES", "A-AJU")],
    "RB-SRV": [("C-DES", "M-ELE", "A-SUB"), ("C-INS", "M-ELE", "A-REP")], "RB-VIB": [("C-DES", "M-DES", "A-LUB"), ("C-MAN", "M-FAD", "A-SUB")],
    "RB-FER": [("C-DES", "M-DES", "A-SUB"), ("C-PRJ", "M-FAD", "A-MOD"), ("C-MAN", "M-AFR", "A-AJU")],
    "TR-TRV": [("C-OPE", "M-SOB", "A-REI"), ("C-DES", "M-DES", "A-REP")], "TR-DES": [("C-MAN", "M-AFR", "A-AJU"), ("C-DES", "M-DES", "A-AJU")],
    "TR-SEN": [("C-INS", "M-ELE", "A-SUB"), ("C-OPE", "M-CON", "A-LIM")], "TR-VIB": [("C-DES", "M-DES", "A-SUB")],
    "DS-ENT": [("C-OPE", "M-CON", "A-LIM"), ("C-PRJ", "M-CON", "A-LIM")], "DS-VAZ": [("C-MAN", "M-SOFT", "A-AJU"), ("C-DES", "M-DES", "A-AJU")],
    "DS-VEX": [("C-DES", "M-DES", "A-SUB"), ("C-INS", "M-AFR", "A-REP")],
    "VI-LEI": [("C-OPE", "M-CON", "A-LIM"), ("C-MAN", "M-SOFT", "A-AJU")], "VI-COM": [("C-INS", "M-ELE", "A-REP")], "VI-ILU": [("C-DES", "M-DES", "A-SUB")],
    "CL-COM": [("C-INS", "M-ELE", "A-REP"), ("C-DES", "M-COR", "A-SUB")], "CL-IO": [("C-DES", "M-ELE", "A-SUB")], "CL-PRG": [("C-GES", "M-SOFT", "A-REI")],
    "MS-VAC": [("C-OPE", "M-CON", "A-LIM"), ("C-DES", "M-DES", "A-SUB")], "MS-VEN": [("C-DES", "M-DES", "A-SUB"), ("C-GES", "M-FAD", "A-SUB")],
    "MS-VAR": [("C-MAN", "M-AFR", "A-REP")], "XX-OUT": [("C-DIV", "M-DESC", "A-REI")],
}
TEXTO = {  # descrições no estilo de quem abre a OS no celular
    "RB-COL": ["{eq} parou com alarme de colisão, operador rearmou", "Colisão do robô na entrada da mesa, peça torta no berço", "Robô bateu na proteção durante reagrupamento"],
    "RB-POS": ["{eq} perdeu referência, posição de pega deslocada", "Robô errando posição de descarga, precisa referenciar"],
    "RB-SRV": ["Alarme de servo/sobrecorrente no eixo do {eq}", "Robô desarmando por sobrecorrente no eixo 2"],
    "RB-VIB": ["Ruído anormal no redutor do {eq}", "Vibração alta no eixo do robô, barulho ao girar"],
    "RB-FER": ["{eq} não pega a peça, garra soltando", "Garra do robô deixando cair peça no reagrupamento", "Ventosa da ferramenta do robô não segura a peça"],
    "TR-TRV": ["{eq} travou, peças acumulando", "Transportador parando sozinho no meio do ciclo"],
    "TR-DES": ["Correia do {eq} desalinhada, peça saindo de lado", "Correia puxando para um lado, ajustar"],
    "TR-SEN": ["Sensor de presença do {eq} sem sinal", "Transportador não vê a peça, sensor piscando"],
    "TR-VIB": ["Barulho no rolete do {eq}", "Vibração no motorredutor do transportador"],
    "DS-ENT": ["{eq} entupido, sem saída de pó", "Bico do dispenser de pó entupindo de novo", "Pó empedrado no bico, falhando aplicação"],
    "DS-VAZ": ["Vazão de pó fora do padrão no {eq}", "Dispenser jogando pó demais, peça com excesso"],
    "DS-VEX": ["Vazamento de pó na rosca do {eq}", "Pó vazando pela vedação do dosador"],
    "VI-LEI": ["Visão reprovando peça boa no {eq}", "Câmera não lê a marcação, reprovação falsa"],
    "VI-COM": ["Sistema de visão sem comunicação com o CLP", "{eq} offline, sem imagem"],
    "VI-ILU": ["Iluminação da câmera fraca no {eq}", "Lâmpada da visão piscando"],
    "CL-COM": ["Falha de rede de campo no {eq}, linha parou", "Perda de comunicação com remota do CLP"],
    "CL-IO": ["Cartão de entrada do {eq} com falha", "Saída do CLP não aciona, cartão de E/S em falha"],
    "CL-PRG": ["CLP em stop após alteração de parâmetro", "Falha de programa no {eq}, reiniciado"],
    "MS-VAC": ["Mesa de ventosas sem vácuo suficiente", "Vácuo baixo na {eq}, peça escorregando"],
    "MS-VEN": ["Ventosa rasgada na {eq}", "Ventosas da mesa danificadas, peça marcando", "Trocar ventosas da mesa, perdendo peça"],
    "MS-VAR": ["Vazamento de ar na mangueira da {eq}", "Chiado de ar na mesa de ventosas"],
    "XX-OUT": ["{eq} parou, causa não identificada", "Parada estranha no {eq}, voltou sozinho após rearme"],
}
ACAO_TXT = {"A-SUB": "substituição", "A-REP": "reparo", "A-AJU": "ajuste", "A-LIM": "limpeza", "A-REI": "rearme e teste",
            "A-LUB": "lubrificação", "A-MOD": "modificação", "A-INS": "inspeção"}
MELHORIAS = [("LR-01-RB01-FER", "Melhoria: trocar material das ventosas da garra (reincidência)"),
             ("LR-02-MS01-VEN", "Melhoria: novo suporte das ventosas da mesa (reincidência)"),
             ("LR-02-DS01-BIC", "Melhoria: instalar vibrador no silo do dispenser (entupimento recorrente)"),
             ("LR-01-DS01-BIC", "Melhoria: proteção contra umidade no bico dosador"),
             ("LR-01-TR01-SEN", "Melhoria: suporte com regulagem para sensor de presença"),
             ("LR-02-TR02-COR", "Melhoria: guia lateral na correia intermediária"),
             ("LR-01-VI01-CAM", "Melhoria: cúpula anti-reflexo na iluminação da visão"),
             ("LR-02-CL01-RED", "Melhoria: refazer conectores da rede de campo"),
             ("LR-01-CL01", "Melhoria: alarme no supervisório para queda de rede"),
             ("LR-02-RB01-CTL", "Melhoria: ventilação forçada no painel do controlador do robô"),
             ("LR-01-MS01-VAC", "Melhoria: vacuostato com indicação local"),
             ("LR-02-VI01-CAM", "Melhoria: rotina de limpeza automática da lente")]


def _seed(nome):
    with open(SEEDS / f"{nome}.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _ts(d: datetime) -> str:
    return d.strftime("%Y-%m-%d %H:%M:%S")


def _turno(h):
    return "A" if 6 <= h < 14 else ("B" if 14 <= h < 22 else "C")


class _Sim:
    def __init__(self):
        p = {r["chave"]: r["valor"] for r in _seed("parametros_demo")}
        self.rng = random.Random(int(p["semente"]))
        self.ini, self.fim = date.fromisoformat(p["periodo_inicio"]), date.fromisoformat(p["periodo_fim"])
        self.agora = datetime.fromisoformat(p["export_em"])
        self.eq = {r["equipment_id"]: r for r in _seed("equipamentos")}
        self.planos = _seed("planos_preventivos")
        self.tec = _seed("tecnicos")
        self.tipos = {r["tipo_id"]: r for r in _seed("tipos_os")}
        self.tasks, self.acts, self.tt, self.paradas = [], [], [], []
        self.tags = {}

    # ---------- utilidades ----------
    def tag(self, code, nome):
        if code not in self.tags:
            self.tags[code] = (f"DEMO-G{len(self.tags) + 1:03d}", nome)
        return self.tags[code][0]

    def funcao(self, esp, hora):
        t = [r for r in self.tec if r["especialidade_id"] == esp and r["turno"] == _turno(hora)]
        return t[0]["funcao"]

    def dia_util(self, d: date) -> date:
        return d + timedelta(days=1) if d.weekday() == 6 else d     # linha não roda domingo

    def nova_os(self, equipment_id, tipo, desc, abertura, prog_ate, done, tags, atividades, plano=None, cls=None):
        n = len(self.tasks) + 1
        tid, short = f"DEMO-T{n:04d}", f"dd{n:06x}"
        status = "completed" if done is not None else ("in_progress" if atividades else "scheduled")
        if tipo == "CANC":
            status, tipo, done = "canceled", tags.pop(0), None
        self.tasks.append([tid, short, short, equipment_id, status, desc, _ts(abertura), _ts(prog_ate),
                           "" if done is None else _ts(done), "true" if plano else "false",
                           sum(a[2] for a in atividades), ""])
        sys_tag = self.tipos[tipo]["tag_sistema"]
        codes = [sys_tag, f"tipo:{tipo}"] + ([f"plano:{plano}"] if plano else [])
        if cls:
            codes += [f"modo:{cls[0]}", f"causa:{cls[1]}", f"mec:{cls[2]}", f"acao:{cls[3]}"]
        for c in codes:
            self.tt.append((tid, self.tag(c, c)))
        for i, (nome, ini, minutos) in enumerate(atividades, 1):
            self.acts.append([f"{tid}-A{i}", tid, nome, _ts(ini), minutos])
        return tid, short

    # ---------- preventivas e preditivas ----------
    def preventivas(self):
        r = self.rng
        for pl in self.planos:
            per, tol, est = int(pl["periodicidade_dias"]), int(pl["tolerancia_dias"]), float(pl["horas_estimadas"])
            d = self.ini + timedelta(days=r.randrange(min(per, 20)))
            while d <= self.fim:
                d = self.dia_util(d)
                ab = datetime.combine(d, datetime.min.time()) + timedelta(hours=r.choice([8, 9, 10, 15, 16]))
                ate = ab + timedelta(minutes=int(est * 60))
                limite = ab + timedelta(days=tol)
                x = r.random()
                if x < 0.03:
                    done, cancel = None, True
                elif limite > self.agora and x < 0.6:
                    done, cancel = None, False                      # ainda dentro do prazo: aberta
                elif x < 0.80:
                    done, cancel = ab + timedelta(days=r.randint(0, tol), minutes=int(est * 60 * 1.5) + r.randint(0, 120)), False
                elif x < 0.95:
                    done, cancel = limite + timedelta(days=r.randint(1, 10), minutes=int(est * 60 * 1.5) + r.randint(0, 120)), False   # atrasada
                else:
                    done, cancel = None, False                      # vencida e aberta
                if done is not None and done > self.agora:
                    done = None
                acts = []
                if done is not None:
                    real = max(15, int(est * 60 * r.uniform(0.7, 1.5)))
                    ini = done - timedelta(minutes=real)
                    acts = [(f"{self.funcao(pl['especialidade_id'], ini.hour)} · execução do plano {pl['plano_id']}", ini, real)]
                tipo = pl["tipo_id"]
                desc = f"[{pl['plano_id']}] {pl['descricao']}"
                if cancel:
                    self.nova_os(pl["equipment_id"], "CANC", desc + " (cancelada: linha sem programação)", ab, ate, None, [tipo], [], plano=pl["plano_id"])
                else:
                    self.nova_os(pl["equipment_id"], tipo, desc, ab, ate, done, [], acts, plano=pl["plano_id"])
                    if tipo == "PRED" and done is not None and r.random() < 0.18:   # P-F: inspeção achou sinal antes da falha
                        self.pf.append((pl["equipment_id"], done))
                d += timedelta(days=per)

    # ---------- corretivas ----------
    def eventos_corretivos(self):
        r, dias = self.rng, (self.fim - self.ini).days + 1
        ev = []
        for sub, (n, modos) in PERFIL.items():
            k = max(0, round(n * 0.9 * r.uniform(0.75, 1.25)))
            for _ in range(k):
                d = self.dia_util(self.ini + timedelta(days=r.randrange(dias)))
                if d > self.fim:
                    d = self.fim
                modo = r.choices(list(modos), weights=list(modos.values()))[0]
                if r.random() < 0.05:
                    modo = "XX-OUT"
                ev.append((sub, modo, d, None))
        for sub, modo, datas in REINCIDENCIAS:
            for s in datas:
                ev.append((sub, modo, date.fromisoformat(s), "EMG"))
        for sub, d in self.pf:                                # achado da inspeção vira corretiva planejada
            ev.append((sub, r.choice(list(PERFIL.get(sub, (0, {"RB-VIB": 1}))[1])), (d + timedelta(days=r.randint(1, 4))).date(), "PLN-PF"))
        ev.sort(key=lambda e: (e[2], e[0], e[1]))
        return ev

    def corretivas(self):
        r = self.rng
        fim_linha = {}                                        # última parada por linha (sem sobreposição)
        for sub, modo, d, forca in self.eventos_corretivos():
            e = self.eq[sub]
            linha = e["linha_id"]
            emg = forca == "EMG" or (forca is None and r.random() < 0.72)
            t = datetime.combine(d, datetime.min.time()) + timedelta(minutes=r.randrange(0, 24 * 60))
            causa, mec, acao = r.choice(CLASSIF[modo])
            nome_eq = self.eq[e["pai_id"]]["nome"] if e["nivel"] == "subconjunto" else e["nome"]
            desc = r.choice(TEXTO[modo]).format(eq=nome_eq)
            if forca == "PLN-PF":
                desc = "Achado na inspeção preditiva: " + desc[0].lower() + desc[1:]
            base = REPARO[modo]
            esp = e["especialidade_id"]
            if emg:
                if linha in fim_linha and t < fim_linha[linha]:
                    t = fim_linha[linha] + timedelta(minutes=r.randint(30, 240))
                resp = r.randint(5, 25)
                reparo = max(10, int(base * r.lognormvariate(0, 0.45)))
                parada = resp + reparo + r.randint(3, 10)
                fim_linha[linha] = t + timedelta(minutes=parada)
                ini = t + timedelta(minutes=resp)
                f1 = self.funcao(esp, ini.hour)
                acts = [(f"{f1} · diagnóstico no local", ini, min(15, reparo // 3 + 5)),
                        (f"{f1} · {ACAO_TXT[acao]}", ini + timedelta(minutes=min(15, reparo // 3 + 5)), reparo)]
                if modo in ("RB-SRV", "RB-POS", "CL-COM", "VI-COM") and r.random() < 0.5:
                    outra = "ELE" if esp == "MEC" else "MEC"
                    acts.append((f"{self.funcao(outra, ini.hour)} · apoio {('elétrico' if outra == 'ELE' else 'mecânico')}", ini, reparo // 2))
                done = t + timedelta(minutes=parada + r.randint(10, 90))
                if done > self.agora:
                    done, acts = None, acts[:1]
                tid, short = self.nova_os(sub, "CORR-EMG", desc, t, t + timedelta(minutes=base), done, [], acts, cls=(modo, causa, mec, acao))
                self.paradas.append([None, short, t.strftime("%Y-%m-%dT%H:%M"), parada, "incluir"])
            else:
                ab = t
                prog = datetime.combine(self.dia_util((t + timedelta(days=r.randint(1, 6))).date()), datetime.min.time()) + timedelta(hours=r.choice([8, 9, 14]))
                reparo = max(15, int(base * 1.3 * r.lognormvariate(0, 0.35)))
                x = r.random()
                if prog > self.agora - timedelta(days=2) or (x < 0.30 and t.date() > self.fim - timedelta(days=60)):
                    done, acts = None, []                     # backlog: corretiva planejada ainda não executada
                    if prog < self.agora and r.random() < 0.4:   # começou, aguardando peça
                        acts = [(f"{self.funcao(esp, prog.hour)} · início do serviço, aguardando peça", prog, 30)]
                else:
                    done = prog + timedelta(days=r.choice([0, 0, 0, 1, 3, 8]), minutes=reparo + 20)
                    if done > self.agora:
                        done = None
                    acts = [] if done is None else [(f"{self.funcao(esp, prog.hour)} · {ACAO_TXT[acao]} programado(a)", done - timedelta(minutes=reparo + 20), reparo)]
                desc += f" (solicitada em {ab:%d/%m %H:%M})"
                self.nova_os(sub, "CORR-PLN", desc, prog, prog + timedelta(minutes=int(base * 1.3)), done, [], acts, cls=(modo, causa, mec, acao))

    def melhorias(self):
        r = self.rng
        for i, (eqid, desc) in enumerate(MELHORIAS):
            ab = datetime.combine(self.dia_util(self.ini + timedelta(days=20 + i * 14)), datetime.min.time()) + timedelta(hours=10)
            horas_est = r.randint(4, 16)
            ate = ab + timedelta(hours=horas_est)              # scheduled_to - scheduled_from = horas estimadas
            e = self.eq[eqid]
            esp = e["especialidade_id"] or "MEC"
            if i % 3 == 2 or ab + timedelta(days=30) > self.agora:
                done, acts = None, []                         # melhorias em aberto (envelhecidas no backlog)
                if i % 2:
                    acts = [(f"{self.funcao(esp, 9)} · levantamento e compra de material", ab + timedelta(days=2), 90)]
            else:
                horas = max(2, int(horas_est * r.uniform(0.7, 1.4)))
                done = ab + timedelta(days=r.randint(7, 30), hours=horas)
                acts = [(f"{self.funcao(esp, 9)} · execução da melhoria", done - timedelta(hours=horas), horas * 60)]
            self.nova_os(eqid, "MELH", desc, ab, ate, done, [], acts)

    def rodar(self):
        self.pf = []
        self.preventivas()
        self.corretivas()
        self.melhorias()
        for i, p in enumerate(sorted(self.paradas, key=lambda x: (x[2], x[1])), 1):
            p[0] = f"DEMO-L{i:04d}"
        return self


def gerar(saida: Path | None = None) -> dict:
    s = _Sim().rodar()
    saida = Path(saida or SAIDA)
    con_dir, par_dir = saida / "conector", saida / "paradas"
    con_dir.mkdir(parents=True, exist_ok=True)
    par_dir.mkdir(parents=True, exist_ok=True)
    eqs = {r["equipment_id"]: r for r in _seed("equipamentos")}
    linhas = {r["linha_id"]: r for r in _seed("linhas")}
    from pmb import ingest
    cols = ingest.contrato()["tabelas"]

    def w(path, cab, rows):
        with open(path, "w", encoding="utf-8", newline="") as f:
            wr = csv.writer(f, lineterminator="\n")
            wr.writerow(cab)
            wr.writerows(rows)

    w(con_dir / "tasks.csv", cols["tasks"], s.tasks)
    w(con_dir / "activities.csv", cols["activities"], s.acts)
    w(con_dir / "equipments.csv", cols["equipments"],
      [[k, v["nome"], linhas[v["linha_id"]]["cost_center"]] for k, v in eqs.items()])
    w(con_dir / "tasks_tags.csv", cols["tasks_tags"], s.tt)
    w(con_dir / "tags.csv", cols["tags"], [[tid, code, nome] for code, (tid, nome) in s.tags.items()])
    w(con_dir / "_parameters.csv", ["key", "value"], [["last_export_date", _ts(s.agora)], ["network.timezone", "America/Sao_Paulo"]])
    w(par_dir / "paradas_demo.csv", ["id_lancamento", "os_ref", "hora_inicio", "duracao_min", "acao"], s.paradas)
    return {"os": len(s.tasks), "atividades": len(s.acts), "paradas": len(s.paradas), "saida": saida}
