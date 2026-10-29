import os
import queue
import threading
import time
import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
import tkinter.ttk as ttk

import matplotlib

matplotlib.use("TkAgg")

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

import fleet_core as core
import fleet_ga as ga
import fleet_plots as plots
import fleet_research as research
import fleet_sa as sa

DEFAULT_VARIANT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "variant05.json")


def parse_number(text, kind):
    value = text.strip().replace(",", ".")

    if kind is int:
        return int(float(value))

    return float(value)


def parse_list(text, kind):
    values = []

    for part in text.replace(";", " ").split():
        for piece in part.split(","):
            if piece.strip():
                values.append(kind(piece.strip()))

    return values


class FleetApp:
    def __init__(self, root):
        self.root = root

        self.variant = None
        self.worker = None
        self.stop_flag = threading.Event()
        self.events = queue.Queue()

        self.results = {"ga": None, "sa": None}
        self.mode = "ga"
        self.last_draw = 0.0
        self.pending = None
        self.research = None

        self.build()
        self.poll()

        if os.path.exists(DEFAULT_VARIANT):
            self.open_variant(DEFAULT_VARIANT)
        else:
            self.redraw()

    def build(self):
        self.root.title("Лабораторна 3. Олійник Гліб, ІПЗ-24-2")
        self.root.geometry("1300x760+10+5")
        self.root.minsize(1100, 640)

        button_font = ("TkDefaultFont", 9)

        bar = tk.Frame(self.root, padx=8, pady=8)
        bar.pack(side="top", fill="x")
        tk.Frame(self.root, height=1, bg="#b5b5b5").pack(side="top", fill="x")

        tk.Button(bar, text="Відкрити JSON", width=14, pady=6, font=button_font,
                  command=self.choose_variant).pack(side="left")

        self.info = tk.Label(bar, text="", anchor="w", fg="#444444")
        self.info.pack(side="left", padx=12)

        self.research_button = tk.Button(bar, text="Дослідження", width=14, pady=6,
                                         font=button_font, command=self.open_research)
        self.research_button.pack(side="right")

        self.status = tk.Label(self.root, text="", anchor="w", bg="black", fg="white",
                               padx=6, pady=3, font=("TkDefaultFont", 9, "bold"))
        self.status.pack(side="bottom", fill="x")

        left = tk.Frame(self.root, padx=6, pady=6)
        left.pack(side="left", fill="y")

        self.tabs = ttk.Notebook(left)
        self.tabs.pack(fill="x")

        self.ga_vars = {}
        self.sa_vars = {}

        self.build_ga_tab()
        self.build_sa_tab()

        self.tabs.bind("<<NotebookTabChanged>>", self.on_tab)

        buttons = tk.Frame(left, pady=6)
        buttons.pack(fill="x")

        self.run_button = tk.Button(buttons, text="Запустити", width=12, pady=6,
                                    font=button_font, command=self.start)
        self.run_button.pack(side="left")

        self.stop_button = tk.Button(buttons, text="Стоп", width=8, pady=6,
                                     font=button_font, state="disabled", command=self.stop)
        self.stop_button.pack(side="left", padx=6)

        tk.Label(left, text="Результат", font=("TkDefaultFont", 9, "bold"),
                 anchor="w").pack(fill="x", pady=(4, 2))

        holder = tk.Frame(left)
        holder.pack(fill="both", expand=True)

        self.output = tk.Text(holder, width=46, height=12, font=("Consolas", 9),
                              wrap="none", relief="solid", borderwidth=1)
        scroll = tk.Scrollbar(holder, command=self.output.yview)
        self.output.config(yscrollcommand=scroll.set)

        scroll.pack(side="right", fill="y")
        self.output.pack(side="left", fill="both", expand=True)

        right = tk.Frame(self.root, padx=4, pady=4)
        right.pack(side="left", fill="both", expand=True)

        self.figure = Figure(figsize=(6.5, 4.8), dpi=100, layout="tight")
        self.canvas = FigureCanvasTkAgg(self.figure, master=right)

        toolbar = NavigationToolbar2Tk(self.canvas, right, pack_toolbar=False)
        toolbar.update()
        toolbar.pack(side="bottom", fill="x")

        self.canvas.get_tk_widget().pack(side="top", fill="both", expand=True)

    def add_field(self, frame, row, title, store, key, value):
        tk.Label(frame, text=title, anchor="w", width=10,
                 font=("TkDefaultFont", 9)).grid(row=row, column=0, sticky="w", pady=1)

        var = tk.StringVar(value=str(value))
        tk.Entry(frame, textvariable=var, width=10).grid(row=row, column=1, sticky="w")

        store[key] = var

    def add_choice(self, frame, row, title, names, current):
        tk.Label(frame, text=title, anchor="w", width=10,
                 font=("TkDefaultFont", 9)).grid(row=row, column=0, sticky="w", pady=1)

        var = tk.StringVar(value=names[current])
        ttk.Combobox(frame, textvariable=var, width=15, state="readonly",
                     values=list(names.values())).grid(row=row, column=1, columnspan=2,
                                                       sticky="w")
        return var

    def build_ga_tab(self):
        frame = tk.Frame(self.tabs, padx=8, pady=8)
        self.tabs.add(frame, text="Генетичний алгоритм")

        defaults = ga.GAParams()
        rows = [("M", "population", defaults.population),
                ("pc", "pc", defaults.pc),
                ("pm", "pm", defaults.pm),
                ("k", "tournament", defaults.tournament),
                ("elite", "elite", defaults.elite),
                ("max_gen", "max_generations", defaults.max_generations),
                ("stall", "stagnation", defaults.stagnation),
                ("delay, ms", "delay", 20)]

        for row, (title, key, value) in enumerate(rows):
            self.add_field(frame, row, title, self.ga_vars, key, value)

        self.pm_hint = tk.Label(frame, text="1/L = —", fg="#777777",
                                font=("TkDefaultFont", 8))
        self.pm_hint.grid(row=2, column=2, sticky="w", padx=4)

        row = len(rows)
        self.selection_var = self.add_choice(frame, row, "відбір", ga.SELECTION_NAMES,
                                             defaults.selection)
        self.crossover_var = self.add_choice(frame, row + 1, "схрещування",
                                             ga.CROSSOVER_NAMES, defaults.crossover)

        self.restart_var = tk.IntVar(value=1 if defaults.restart else 0)
        tk.Checkbutton(frame, text="перезапуск популяції при стагнації",
                       variable=self.restart_var).grid(row=row + 2, column=0, columnspan=3,
                                                       sticky="w", pady=(4, 0))

    def build_sa_tab(self):
        frame = tk.Frame(self.tabs, padx=8, pady=8)
        self.tabs.add(frame, text="Імітація відпалу")

        defaults = sa.SAParams()
        rows = [("To", "t_start", defaults.t_start),
                ("T_min", "t_min", defaults.t_min),
                ("alpha", "alpha", defaults.alpha),
                ("dT", "delta_t", defaults.delta_t),
                ("L", "iterations", defaults.iterations),
                ("max_eval", "max_evaluations", defaults.max_evaluations),
                ("delay, ms", "delay", 20)]

        for row, (title, key, value) in enumerate(rows):
            self.add_field(frame, row, title, self.sa_vars, key, value)

        tk.Label(frame, text="L — переходів на ступінь T", fg="#777777",
                 font=("TkDefaultFont", 8)).grid(row=4, column=2, sticky="w", padx=4)
        tk.Label(frame, text="dT — для лінійного закону", fg="#777777",
                 font=("TkDefaultFont", 8)).grid(row=3, column=2, sticky="w", padx=4)

        self.law_var = self.add_choice(frame, len(rows), "закон", sa.COOLING_NAMES,
                                       defaults.law)

    def read_ga(self):
        params = ga.GAParams()

        try:
            params.population = parse_number(self.ga_vars["population"].get(), int)
            params.pc = parse_number(self.ga_vars["pc"].get(), float)
            params.pm = parse_number(self.ga_vars["pm"].get(), float)
            params.tournament = parse_number(self.ga_vars["tournament"].get(), int)
            params.elite = parse_number(self.ga_vars["elite"].get(), int)
            params.max_generations = parse_number(self.ga_vars["max_generations"].get(), int)
            params.stagnation = parse_number(self.ga_vars["stagnation"].get(), int)
            delay = parse_number(self.ga_vars["delay"].get(), float)
        except ValueError:
            messagebox.showerror("Параметри ГА", "Параметри мають бути числами.")
            return None, 0

        problems = []
        if params.population < 2:
            problems.append("M має бути не менше 2.")
        if not 0.0 <= params.pc <= 1.0:
            problems.append("pc має бути в межах [0, 1].")
        if not 0.0 <= params.pm <= 1.0:
            problems.append("pm має бути в межах [0, 1].")
        if params.tournament < 1:
            problems.append("k має бути не менше 1.")
        if not 0 <= params.elite < params.population:
            problems.append("elite має бути в межах [0, M).")
        if params.max_generations < 1 or params.stagnation < 1:
            problems.append("max_gen і stall мають бути додатними.")

        if problems:
            messagebox.showerror("Параметри ГА", "\n".join(problems))
            return None, 0

        for key, names, var in (("selection", ga.SELECTION_NAMES, self.selection_var),
                                ("crossover", ga.CROSSOVER_NAMES, self.crossover_var)):
            for code, name in names.items():
                if name == var.get():
                    setattr(params, key, code)

        params.restart = bool(self.restart_var.get())

        return params, max(0.0, delay) / 1000.0

    def read_sa(self):
        params = sa.SAParams()

        try:
            params.t_start = parse_number(self.sa_vars["t_start"].get(), float)
            params.t_min = parse_number(self.sa_vars["t_min"].get(), float)
            params.alpha = parse_number(self.sa_vars["alpha"].get(), float)
            params.delta_t = parse_number(self.sa_vars["delta_t"].get(), float)
            params.iterations = parse_number(self.sa_vars["iterations"].get(), int)
            params.max_evaluations = parse_number(self.sa_vars["max_evaluations"].get(), int)
            delay = parse_number(self.sa_vars["delay"].get(), float)
        except ValueError:
            messagebox.showerror("Параметри SA", "Параметри мають бути числами.")
            return None, 0

        problems = []
        if params.t_start <= 0 or params.t_min <= 0:
            problems.append("To і T_min мають бути додатними.")
        if params.t_min >= params.t_start:
            problems.append("T_min має бути меншою за To.")
        if not 0.0 < params.alpha < 1.0:
            problems.append("alpha має бути в межах (0, 1).")
        if params.delta_t <= 0:
            problems.append("dT має бути додатним.")
        if params.iterations < 1 or params.max_evaluations < 1:
            problems.append("L і max_eval мають бути додатними.")

        if problems:
            messagebox.showerror("Параметри SA", "\n".join(problems))
            return None, 0

        for code, name in sa.COOLING_NAMES.items():
            if name == self.law_var.get():
                params.law = code

        return params, max(0.0, delay) / 1000.0

    def choose_variant(self):
        if self.running():
            return

        path = filedialog.askopenfilename(
            title="Файл варіанта",
            initialdir=os.path.dirname(DEFAULT_VARIANT),
            filetypes=[("JSON", "*.json"), ("Усі файли", "*.*")])

        if path:
            self.open_variant(path)

    def open_variant(self, path):
        try:
            variant = core.load_variant(path)
        except (OSError, ValueError) as error:
            messagebox.showerror("Помилка вхідних даних", str(error))
            return

        self.variant = variant
        self.results = {"ga": None, "sa": None}

        cells = sum(variant.ships)
        self.info.config(text="%s: поле %dx%d, кораблі %s (%d клітинок), рифів %d"
                         % (variant.name, variant.size, variant.size, variant.ships,
                            cells, len(variant.reefs)))
        self.pm_hint.config(text="1/L = %.3f" % (1.0 / variant.gene_count()))

        self.set_output("Варіант завантажено. Вхідні дані коректні.\n\n"
                        "Довжина хромосоми L = %d (ген - номер допустимого положення корабля).\n"
                        "Допустимих положень за довжинами:\n%s"
                        % (variant.gene_count(),
                           "\n".join("  L=%d: %d" % (length, len(ids))
                                     for length, ids in sorted(variant.placements.items(),
                                                               reverse=True))))
        self.status.config(text="Готово")
        self.redraw()

    def on_tab(self, _event=None):
        self.mode = "ga" if self.tabs.index("current") == 0 else "sa"

        if not self.running():
            self.redraw()
            self.show_result()

    def running(self):
        return self.worker is not None and self.worker.is_alive()

    def start(self):
        if self.variant is None or self.running():
            return

        if self.mode == "ga":
            params, delay = self.read_ga()
            target = self.run_ga
        else:
            params, delay = self.read_sa()
            target = self.run_sa

        if params is None:
            return

        self.stop_flag.clear()
        self.results[self.mode] = None
        self.set_buttons(True)
        self.set_output("Пошук триває...")

        self.worker = threading.Thread(target=target, args=(self.variant, params, delay),
                                       daemon=True)
        self.worker.start()

    def stop(self):
        self.stop_flag.set()

    def set_buttons(self, busy):
        self.run_button.config(state="disabled" if busy else "normal")
        self.stop_button.config(state="normal" if busy else "disabled")
        self.research_button.config(state="disabled" if busy else "normal")

        state = "disabled" if busy else "normal"
        for index in range(self.tabs.index("end")):
            if index != self.tabs.index("current"):
                self.tabs.tab(index, state=state)

    def run_ga(self, variant, params, delay):
        started = time.perf_counter()
        algorithm = ga.GeneticAlgorithm(variant, params)
        last = [0.0]
        slept = [0.0]

        def report(final):
            self.events.put(("ga", {
                "genes": list(algorithm.best_genes),
                "fitness": algorithm.best_fitness,
                "best": list(algorithm.history_best),
                "mean": list(algorithm.history_mean),
                "generation": algorithm.generation,
                "evaluations": algorithm.evaluations,
                "success": algorithm.success,
                "solved_generation": algorithm.solved_generation,
                "solved_evaluations": algorithm.solved_evaluations,
                "restarts": algorithm.restarts,
                "elapsed": time.perf_counter() - started - slept[0],
                "final": final,
                "stopped": final and not algorithm.finished,
            }))

        def on_generation(_algorithm):
            if delay:
                time.sleep(delay)
                slept[0] += delay

            now = time.perf_counter()
            if now - last[0] > 0.08:
                last[0] = now
                report(False)

        algorithm.run(should_stop=self.stop_flag.is_set, on_generation=on_generation)
        report(True)

    def run_sa(self, variant, params, delay):
        started = time.perf_counter()
        algorithm = sa.SimulatedAnnealing(variant, params)
        last = [0.0]
        slept = [0.0]

        def report(final):
            self.events.put(("sa", {
                "genes": list(algorithm.best_genes),
                "fitness": algorithm.best_fitness(),
                "energy": algorithm.energy,
                "best_energy": algorithm.best_energy,
                "temperature": algorithm.temperature,
                "level": algorithm.level,
                "levels": list(algorithm.history_level),
                "energies": list(algorithm.history_energy),
                "bests": list(algorithm.history_best),
                "temperatures": list(algorithm.history_temperature),
                "accepted": list(algorithm.history_accepted),
                "evaluations": algorithm.evaluations,
                "success": algorithm.success,
                "solved_level": algorithm.solved_level,
                "solved_evaluations": algorithm.solved_evaluations,
                "elapsed": time.perf_counter() - started - slept[0],
                "final": final,
                "stopped": final and not algorithm.finished,
            }))

        def on_level(_algorithm):
            if delay:
                time.sleep(delay)
                slept[0] += delay

            now = time.perf_counter()
            if now - last[0] > 0.08:
                last[0] = now
                report(False)

        algorithm.run(should_stop=self.stop_flag.is_set, on_level=on_level)
        report(True)

    def poll(self):
        latest = None

        while True:
            try:
                kind, snapshot = self.events.get_nowait()
            except queue.Empty:
                break

            self.results[kind] = snapshot
            latest = kind

            if snapshot["final"]:
                self.finish(kind, snapshot)

        if latest is not None:
            self.pending = latest

        now = time.perf_counter()
        if self.pending is not None and (now - self.last_draw > 0.15 or not self.running()):
            self.update_status(self.pending)
            if self.pending == self.mode:
                self.redraw()
            self.pending = None
            self.last_draw = now

        self.root.after(50, self.poll)

    def finish(self, kind, snapshot):
        self.set_buttons(False)
        self.update_status(kind)

        if kind == self.mode:
            self.redraw()
            self.show_result()

        print("\n=== %s ===" % ("Генетичний алгоритм" if kind == "ga" else "Імітація відпалу"))
        print(self.result_text(kind, snapshot))

    def result_text(self, kind, snapshot):
        lines = [core.describe(self.variant, snapshot["genes"], snapshot["fitness"]), ""]

        if snapshot["stopped"]:
            lines.append("Пошук зупинено користувачем.")

        if kind == "ga":
            lines.append("Поколінь: %d" % snapshot["generation"])
            if snapshot["success"]:
                lines.append("Розв'язок знайдено на поколінні %d" % snapshot["solved_generation"])
                lines.append("Обчислень F до розв'язку: %d" % snapshot["solved_evaluations"])
            lines.append("Обчислень F усього: %d" % snapshot["evaluations"])
            lines.append("Перезапусків популяції: %d" % snapshot["restarts"])
        else:
            lines.append("Ступенів температури: %d" % len(snapshot["levels"]))
            if snapshot["success"]:
                lines.append("Розв'язок знайдено на ступені %d" % snapshot["solved_level"])
                lines.append("Обчислень E до розв'язку: %d" % snapshot["solved_evaluations"])
            lines.append("Обчислень E усього: %d" % snapshot["evaluations"])
            lines.append("Кінцева температура T: %.4f" % snapshot["temperature"])

        lines.append("Час роботи алгоритму: %.3f с" % snapshot["elapsed"])
        return "\n".join(lines)

    def show_result(self):
        snapshot = self.results.get(self.mode)

        if snapshot is not None and snapshot["final"]:
            self.set_output(self.result_text(self.mode, snapshot))
        elif snapshot is None and self.variant is not None:
            self.set_output("Для цього алгоритму ще немає результату.\n"
                            "Натисніть \"Запустити\".")

    def set_output(self, text):
        self.output.config(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("1.0", text)
        self.output.config(state="disabled")

    def update_status(self, kind):
        snapshot = self.results.get(kind)
        if snapshot is None:
            return

        if kind == "ga":
            mean = snapshot["mean"][-1] if snapshot["mean"] else 0.0
            text = ("ГА | Покоління: %d | Найкращий F: %g | Середній F: %.2f | Обчислень F: %d"
                    % (snapshot["generation"], snapshot["fitness"], mean,
                       snapshot["evaluations"]))
        else:
            accepted = snapshot["accepted"][-1] if snapshot["accepted"] else 0.0
            text = ("SA | Ступінь T: %d | T: %.4f | E: %g | Найкраща E: %g | "
                    "Прийнято: %.0f%% | Обчислень E: %d"
                    % (snapshot["level"], snapshot["temperature"], snapshot["energy"],
                       snapshot["best_energy"], 100.0 * accepted, snapshot["evaluations"]))

        if snapshot["final"]:
            text += " | " + ("розв'язок знайдено" if snapshot["success"] else
                             "зупинено" if snapshot["stopped"] else "розв'язок не знайдено")

        self.status.config(text=text)

    def redraw(self):
        self.figure.clear()

        if self.variant is None:
            self.canvas.draw_idle()
            return

        snapshot = self.results.get(self.mode)
        genes = snapshot["genes"] if snapshot else None
        fitness = snapshot["fitness"] if snapshot else None

        if self.mode == "ga":
            grid = self.figure.add_gridspec(1, 2, width_ratios=[1.0, 1.1])
            field = self.figure.add_subplot(grid[0, 0])
            chart = self.figure.add_subplot(grid[0, 1])

            plots.draw_field(field, self.variant, genes, fitness)
            plots.draw_ga_history(chart, snapshot["best"] if snapshot else [],
                                  snapshot["mean"] if snapshot else [])
        else:
            grid = self.figure.add_gridspec(3, 2, width_ratios=[1.0, 1.1])
            field = self.figure.add_subplot(grid[:, 0])
            energy = self.figure.add_subplot(grid[0, 1])
            temperature = self.figure.add_subplot(grid[1, 1], sharex=energy)
            accepted = self.figure.add_subplot(grid[2, 1], sharex=energy)

            plots.draw_field(field, self.variant, genes, fitness)

            if snapshot:
                plots.draw_sa_history(energy, temperature, accepted, snapshot["levels"],
                                      snapshot["energies"], snapshot["bests"],
                                      snapshot["temperatures"], snapshot["accepted"])
            else:
                plots.draw_sa_history(energy, temperature, accepted, [], [], [], [], [])

        self.canvas.draw_idle()

    def open_research(self):
        if self.variant is None or self.running():
            return

        if self.research is not None and self.research.alive():
            self.research.window.lift()
            return

        ga_params, _ = self.read_ga()
        if ga_params is None:
            return

        sa_params, _ = self.read_sa()
        if sa_params is None:
            return

        self.research = ResearchWindow(self, ga_params, sa_params)


class ResearchWindow:
    def __init__(self, app, ga_params, sa_params):
        self.app = app
        self.variant = app.variant
        self.ga_params = ga_params
        self.sa_params = sa_params

        self.worker = None
        self.stop_flag = threading.Event()
        self.events = queue.Queue()
        self.report = None

        self.window = tk.Toplevel(app.root)
        self.window.title("Дослідження параметрів — %s" % self.variant.name)
        self.window.geometry("1200x760+60+40")
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        self.build()
        self.poll()

    def alive(self):
        try:
            return bool(self.window.winfo_exists())
        except tk.TclError:
            return False

    def build(self):
        bar = tk.Frame(self.window, padx=8, pady=8)
        bar.pack(side="top", fill="x")

        self.vars = {}
        fields = [("запусків", "runs", str(research.STUDY_RUNS), 4),
                  ("порівняння", "compare", str(research.COMPARE_RUNS), 4),
                  ("M", "population", ", ".join(str(v) for v in research.POPULATION_VALUES), 16),
                  ("pm", "mutation", ", ".join(str(v) for v in research.MUTATION_VALUES), 16),
                  ("alpha", "alpha", ", ".join(str(v) for v in research.ALPHA_VALUES), 16)]

        for title, key, value, width in fields:
            tk.Label(bar, text=title).pack(side="left", padx=(8, 2))
            var = tk.StringVar(value=value)
            tk.Entry(bar, textvariable=var, width=width).pack(side="left")
            self.vars[key] = var

        self.start_button = tk.Button(bar, text="Почати", width=10, command=self.start)
        self.start_button.pack(side="left", padx=(12, 4))

        self.stop_button = tk.Button(bar, text="Стоп", width=8, state="disabled",
                                     command=self.stop_flag.set)
        self.stop_button.pack(side="left")

        self.copy_button = tk.Button(bar, text="Копіювати таблиці", width=16,
                                     state="disabled", command=self.copy_tables)
        self.copy_button.pack(side="left", padx=4)

        line = tk.Frame(self.window, padx=8)
        line.pack(side="top", fill="x")

        self.progress = ttk.Progressbar(line, length=300)
        self.progress.pack(side="left")

        self.label = tk.Label(line, text="Базові параметри взято з вкладок головного вікна.",
                              fg="#444444", anchor="w")
        self.label.pack(side="left", padx=8)

        self.tabs = ttk.Notebook(self.window)
        self.tabs.pack(fill="both", expand=True, padx=8, pady=8)

        self.pages = {}
        for key, title in (("population", "Вплив M (ГА)"), ("mutation", "Вплив pm (ГА)"),
                           ("alpha", "Вплив alpha (SA)"), ("compare", "ГА vs SA")):
            self.pages[key] = self.build_page(title)

    def build_page(self, title):
        frame = tk.Frame(self.tabs)
        self.tabs.add(frame, text=title)

        table = ttk.Treeview(frame, show="headings", height=5)
        table.pack(side="top", fill="x", padx=4, pady=4)

        figure = Figure(figsize=(8, 3.6), dpi=100, layout="tight")
        canvas = FigureCanvasTkAgg(figure, master=frame)

        toolbar = NavigationToolbar2Tk(canvas, frame, pack_toolbar=False)
        toolbar.update()
        toolbar.pack(side="bottom", fill="x")

        canvas.get_tk_widget().pack(side="top", fill="both", expand=True)

        return {"table": table, "figure": figure, "canvas": canvas}

    def start(self):
        if self.worker is not None and self.worker.is_alive():
            return

        try:
            runs = int(self.vars["runs"].get())
            compare_runs = int(self.vars["compare"].get())
            population = parse_list(self.vars["population"].get(), int)
            mutation = parse_list(self.vars["mutation"].get(), float)
            alpha = parse_list(self.vars["alpha"].get(), float)
        except ValueError:
            messagebox.showerror("Дослідження", "Значення мають бути числами через кому.",
                                 parent=self.window)
            return

        problems = []
        if runs < 1 or compare_runs < 1:
            problems.append("Кількість запусків має бути додатною.")
        if len(population) < 1 or any(value < 2 for value in population):
            problems.append("Значення M мають бути не менше 2.")
        if len(mutation) < 1 or any(not 0 <= value <= 1 for value in mutation):
            problems.append("Значення pm мають бути в межах [0, 1].")
        if len(alpha) < 1 or any(not 0 < value < 1 for value in alpha):
            problems.append("Значення alpha мають бути в межах (0, 1).")
        if any(self.ga_params.elite >= value for value in population):
            problems.append("Кожне M має бути більше за elite = %d." % self.ga_params.elite)

        if problems:
            messagebox.showerror("Дослідження", "\n".join(problems), parent=self.window)
            return

        self.stop_flag.clear()
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.copy_button.config(state="disabled")
        self.progress.config(value=0)

        def work():
            def progress(done, total, text):
                self.events.put(("progress", (done, total, text)))

            report = research.run_all(self.variant, self.ga_params, self.sa_params,
                                      population, mutation, alpha, runs, compare_runs,
                                      progress=progress, should_stop=self.stop_flag.is_set)
            self.events.put(("done", report))

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def poll(self):
        if not self.alive():
            return

        while True:
            try:
                kind, payload = self.events.get_nowait()
            except queue.Empty:
                break

            if kind == "progress":
                done, total, text = payload
                self.progress.config(maximum=total, value=done)
                self.label.config(text="%d/%d  %s" % (done, total, text))
            else:
                self.show(payload)

        self.window.after(80, self.poll)

    def show(self, report):
        self.report = report

        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.copy_button.config(state="normal")

        stopped = self.stop_flag.is_set()
        self.label.config(text="Зупинено - показано завершені частини." if stopped
                          else "Дослідження завершено.")

        for (key, (title, lines)) in zip(("population", "mutation", "alpha", "compare"),
                                         research.tables(report)):
            page = self.pages[key]
            self.fill_table(page["table"], lines)

            rows = report.get(key, [])
            if key == "compare":
                plots.draw_compare(page["figure"], rows)
            elif key == "alpha":
                plots.draw_study(page["figure"], rows, "alpha", "Сер. кількість ступенів T")
            else:
                plots.draw_study(page["figure"], rows, "M" if key == "population" else "pm",
                                 "Сер. кількість поколінь")
            page["canvas"].draw_idle()

        print("\n=== Дослідження: %s ===" % self.variant.name)
        for title, lines in research.tables(report):
            print(title)
            print(research.format_table(lines))
            print()

    def fill_table(self, table, lines):
        header = lines[0]
        table.delete(*table.get_children())
        table.config(columns=list(range(len(header))))

        for index, title in enumerate(header):
            table.heading(index, text=title)
            table.column(index, width=150 if index else 110, anchor="center")

        for line in lines[1:]:
            table.insert("", "end", values=line)

    def copy_tables(self):
        if self.report is None:
            return

        self.window.clipboard_clear()
        self.window.clipboard_append(research.tab_separated(self.report))
        self.label.config(text="Таблиці скопійовано в буфер обміну (через табуляцію).")

    def close(self):
        self.stop_flag.set()
        self.window.destroy()


def run():
    root = tk.Tk()
    FleetApp(root)
    root.mainloop()
