import tkinter as tk
import tkinter.ttk as ttk

import sonar_core as core
import sonar_point

REPEATS = 4

SINGLE_COLOR = "#d62728"
AVERAGED_COLOR = "#1f77b4"
ZERO_COLOR = "#2ca02c"
PEAK_COLOR = "#2ca02c"


class SonarApp:
    def __init__(self, root):
        self.root = root
        self.config = core.get_config()
        self.pulse = core.get_pulse()

        self.sample_rate = self.config["sample_rate"]
        self.sound_speed = self.config["sound_speed"]
        self.total_steps = self.config["total_steps"]

        probe = core.get_sensor(0)
        self.signal_length = len(probe)
        self.max_depth = core.max_measurable_depth(
            self.signal_length, len(self.pulse), self.sample_rate, self.sound_speed
        )
        self.tolerance = 2 * core.depth_resolution(self.sample_rate, self.sound_speed)

        self.depths_single = []
        self.depths_avg = []
        self.rows = []
        self.last_single = None
        self.last_avg = None
        self.running = False
        self.vars = {}

        self.build()
        self.fill_config()
        self.update_readout()

    def build(self):
        self.root.title("Лабораторна 1. Олійник Гліб, ІПЗ-24-2")
        self.root.geometry("1280x660")
        self.root.minsize(1060, 560)

        bar = tk.Frame(self.root, padx=8, pady=8)
        bar.pack(side="top", fill="x")
        tk.Frame(self.root, height=1, bg="#b5b5b5").pack(side="top", fill="x")

        button_font = ("TkDefaultFont", 9)

        self.button = tk.Button(bar, text="Вперед", width=11, pady=8,
                                font=button_font, command=self.forward)
        self.button.pack(side="left")

        self.all_button = tk.Button(bar, text="Пройти все", width=11, pady=8,
                                    font=button_font, command=self.run_all)
        self.all_button.pack(side="left", padx=6)

        self.stop_button = tk.Button(bar, text="Стоп", width=8, pady=8,
                                     font=button_font, state="disabled",
                                     command=self.stop)
        self.stop_button.pack(side="left")

        self.reset_button = tk.Button(bar, text="Скинути", width=11, pady=8,
                                      font=button_font, command=self.reset)
        self.reset_button.pack(side="left", padx=6)

        self.point_button = tk.Button(bar, text="Аналіз точки", width=13, pady=8,
                                      font=button_font, command=self.open_point)
        self.point_button.pack(side="left")


        self.show_single = tk.IntVar(value=1)
        self.show_avg = tk.IntVar(value=1)

        toggles = tk.LabelFrame(bar, text="Показувати", padx=6, pady=2,
                                font=("TkDefaultFont", 8))
        toggles.pack(side="left", padx=(14, 0))

        tk.Checkbutton(toggles, text="1 запит", variable=self.show_single,
                       fg=SINGLE_COLOR, activeforeground=SINGLE_COLOR,
                       command=self.draw_all).pack(side="left")
        tk.Checkbutton(toggles, text="усереднення %d" % REPEATS,
                       variable=self.show_avg, fg=AVERAGED_COLOR,
                       activeforeground=AVERAGED_COLOR,
                       command=self.draw_all).pack(side="left")

        self.progress = ttk.Progressbar(bar, length=170,
                                        maximum=self.total_steps)
        self.progress.pack(side="right", padx=(8, 0))

        self.status = tk.Label(bar, text="", anchor="e", width=26,
                               fg="#444444")
        self.status.pack(side="right")

        self.side = tk.Frame(self.root)
        self.side.pack(side="right", fill="y", padx=5, pady=5)

        self.column_left = tk.Frame(self.side)
        self.column_left.pack(side="left", fill="y", anchor="n")

        self.column_right = tk.Frame(self.side)
        self.column_right.pack(side="left", fill="y", anchor="n", padx=(10, 0))

        self.target = self.column_left

        plots = tk.Frame(self.root)
        plots.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        plots.rowconfigure(0, weight=1)
        plots.rowconfigure(1, weight=0)
        plots.columnconfigure(0, weight=1)
        plots.columnconfigure(1, weight=1)

        self.profile_canvas = tk.Canvas(plots, bg="white", height=300)
        self.profile_canvas.grid(row=0, column=0, columnspan=2, sticky="nsew")

        self.osc_canvas = tk.Canvas(plots, bg="white", height=150)
        self.osc_canvas.grid(row=1, column=0, sticky="nsew", pady=(5, 0))

        self.corr_canvas = tk.Canvas(plots, bg="white", height=150)
        self.corr_canvas.grid(row=1, column=1, sticky="nsew", padx=(5, 0),
                              pady=(5, 0))

        self.profile_canvas.bind("<Configure>", lambda e: self.draw_profile())
        self.osc_canvas.bind("<Configure>", lambda e: self.draw_osc())
        self.corr_canvas.bind("<Configure>", lambda e: self.draw_corr())

    def section(self, title):
        self.group = tk.LabelFrame(self.target, text=title, padx=6, pady=4,
                                   font=("TkDefaultFont", 8, "bold"))
        self.group.pack(fill="x", pady=(0, 6))

    def row(self, name, key, color="black"):
        line = tk.Frame(self.group)
        line.pack(fill="x")
        tk.Label(line, text=name, width=20, anchor="w",
                 font=("TkDefaultFont", 8)).pack(side="left")
        var = tk.StringVar(value="-")
        tk.Label(line, textvariable=var, width=11, anchor="e", fg=color,
                 font=("TkDefaultFont", 8)).pack(side="left")
        self.vars[key] = var

    def fill_config(self):
        self.section("Отримано від сервера")
        self.row("Точок маршруту", "steps")
        self.row("Частота дискр.", "fs")
        self.row("Швидкість звуку", "c")
        self.row("Несуча частота", "f0")
        self.row("Довжина шаблону", "plen")
        self.row("Довжина запису", "slen")

        self.section("Розраховано")
        self.row("Тривалість імпульсу", "tau")
        self.row("Роздільна здатність", "res")
        self.row("Макс. глибина", "limit")
        self.row("Множень на крок", "ops")

        self.target = self.column_right

        self.section("Поточний замір")
        self.row("Крок", "step")
        self.row("Зсув k_max (сер.)", "k", AVERAGED_COLOR)
        self.row("Зсув k_max (1 зап.)", "k1", SINGLE_COLOR)
        self.row("Пік R(k)", "peak", AVERAGED_COLOR)
        self.row("Затримка", "delay", AVERAGED_COLOR)
        self.row("Глибина (сер. %d)" % REPEATS, "depth", AVERAGED_COLOR)
        self.row("Глибина (1 запит)", "depth1", SINGLE_COLOR)
        self.row("Пік/СКЗ (сер.)", "snr", AVERAGED_COLOR)
        self.row("Пік/СКЗ (1 запит)", "snr1", SINGLE_COLOR)
        self.row("СКВ шуму (сер.)", "noise", AVERAGED_COLOR)
        self.row("СКВ шуму (1 запит)", "noise1", SINGLE_COLOR)

        self.section("Профіль дна")
        self.row("Мін. глибина", "dmin")
        self.row("Макс. глибина", "dmax")
        self.row("Середня глибина", "davg")
        self.row("Стрибок (сер. %d)" % REPEATS, "jump", AVERAGED_COLOR)
        self.row("Стрибок (1 запит)", "jump1", SINGLE_COLOR)
        self.row("Розбіжних кроків", "bad")
        self.row("Кореляція Пірсона", "r")

        self.vars["steps"].set("%d" % self.total_steps)
        self.vars["fs"].set("%g Гц" % self.sample_rate)
        self.vars["c"].set("%g м/с" % self.sound_speed)
        self.vars["f0"].set("%g Гц" % self.config["carrier_freq"])
        self.vars["plen"].set("%d відл." % len(self.pulse))
        self.vars["tau"].set("%.1f мс" % (
            core.pulse_duration(len(self.pulse), self.sample_rate) * 1000))
        self.vars["slen"].set("%d відл." % self.signal_length)
        self.vars["res"].set("%.3f м" % core.depth_resolution(
            self.sample_rate, self.sound_speed))
        self.vars["limit"].set("%.2f м" % self.max_depth)
        self.vars["ops"].set("%d" % core.multiplications_per_step(
            self.signal_length, len(self.pulse)))

    def step_once(self):
        step = len(self.depths_avg)
        if step >= self.total_steps:
            return False

        self.status.configure(text="крок %d..." % step)
        self.root.update_idletasks()

        try:
            single, averaged = core.measure_pair(step, self.pulse, self.sample_rate,
                                                 self.sound_speed, REPEATS)
        except Exception as error:
            self.status.configure(text="помилка зв'язку: %s" % error)
            return False

        self.last_single = single
        self.last_avg = averaged
        self.depths_single.append(single["depth"])
        self.depths_avg.append(averaged["depth"])
        self.rows.append({
            "k1": single["k_max"], "k4": averaged["k_max"],
            "snr1": single["snr"], "snr4": averaged["snr"],
            "noise1": single["noise"], "noise4": averaged["noise"],
            "peak4": averaged["peak"], "delay4": averaged["delay"],
        })

        self.update_readout()
        self.draw_all()
        return True

    def forward(self):
        if self.running:
            return
        if self.step_once():
            if len(self.depths_avg) >= self.total_steps:
                self.finish("маршрут пройдено")
            else:
                self.status.configure(text="крок %d готовий"
                                           % (len(self.depths_avg) - 1))

    def run_all(self):
        if self.running or len(self.depths_avg) >= self.total_steps:
            return
        self.running = True
        self.button.configure(state="disabled")
        self.all_button.configure(state="disabled")
        self.reset_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.root.after(1, self.tick)

    def tick(self):
        if not self.running:
            self.finish("зупинено на кроці %d" % len(self.depths_avg))
            return
        if not self.step_once():
            self.finish(self.status.cget("text"))
            return
        if len(self.depths_avg) >= self.total_steps:
            self.finish("маршрут пройдено повністю")
            return
        self.root.after(1, self.tick)

    def open_point(self):
        step = max(len(self.depths_avg) - 1, 0)
        sonar_point.open_window(self.root, self.config, self.pulse, step)

    def stop(self):
        self.running = False

    def finish(self, message):
        self.running = False
        self.stop_button.configure(state="disabled")
        self.reset_button.configure(state="normal")
        done = len(self.depths_avg) >= self.total_steps
        self.button.configure(state="disabled" if done else "normal")
        self.all_button.configure(state="disabled" if done else "normal")
        self.status.configure(text=message)

    def reset(self):
        if self.running:
            return
        self.depths_single = []
        self.depths_avg = []
        self.rows = []
        self.last_single = None
        self.last_avg = None
        self.button.configure(state="normal")
        self.all_button.configure(state="normal")
        self.status.configure(text="")
        self.update_readout()
        self.draw_all()

    def update_readout(self):
        self.progress.configure(value=len(self.depths_avg))

        if not self.rows:
            for key in ("k", "k1", "peak", "delay", "depth", "depth1", "snr",
                        "snr1", "noise", "noise1", "dmin", "dmax", "davg",
                        "jump", "jump1", "bad", "r"):
                self.vars[key].set("-")
            self.vars["step"].set("0 / %d" % self.total_steps)
            return

        last = self.rows[-1]
        depths = self.depths_avg
        depths_one = self.depths_single

        bad = 0
        for i in range(len(depths)):
            if abs(depths_one[i] - depths[i]) > self.tolerance:
                bad += 1

        self.vars["step"].set("%d / %d" % (len(depths), self.total_steps))
        self.vars["k"].set("%d" % last["k4"])
        self.vars["k1"].set("%d" % last["k1"])
        self.vars["peak"].set("%.1f" % last["peak4"])
        self.vars["delay"].set("%.2f мс" % (last["delay4"] * 1000))
        self.vars["depth"].set("%.2f м" % depths[-1])
        self.vars["depth1"].set("%.2f м" % depths_one[-1])
        self.vars["snr"].set("%.2f" % last["snr4"])
        self.vars["snr1"].set("%.2f" % last["snr1"])
        self.vars["noise"].set("%.3f" % last["noise4"])
        self.vars["noise1"].set("%.3f" % last["noise1"])
        self.vars["dmin"].set("%.2f м" % min(depths))
        self.vars["dmax"].set("%.2f м" % max(depths))
        self.vars["davg"].set("%.2f м" % core.mean(depths))
        self.vars["jump"].set("%.2f м" % core.smoothness(depths))
        self.vars["jump1"].set("%.2f м" % core.smoothness(depths_one))
        self.vars["bad"].set("%d / %d" % (bad, len(depths)))
        if len(depths) > 1:
            self.vars["r"].set("%.4f" % core.pearson(depths_one, depths))
        else:
            self.vars["r"].set("-")

    def draw_all(self):
        self.draw_profile()
        self.draw_osc()
        self.draw_corr()

    def draw_profile(self):
        canvas = self.profile_canvas
        canvas.delete("all")

        width = canvas.winfo_width()
        height = canvas.winfo_height()
        if width < 200 or height < 120:
            return

        pad_left = 60
        pad_right = 20
        pad_top = 28
        pad_bottom = 46

        plot_w = width - pad_left - pad_right
        plot_h = height - pad_top - pad_bottom
        last_index = max(self.total_steps - 1, 1)

        def to_x(i):
            return pad_left + (i / last_index) * plot_w

        def to_y(depth):
            return pad_top + (depth / self.max_depth) * plot_h

        canvas.create_rectangle(pad_left, pad_top, pad_left + plot_w,
                                pad_top + plot_h, outline="black")
        canvas.create_text(pad_left, 12, anchor="w",
                           text="Профіль дна, м")

        for i in range(7):
            depth = self.max_depth * i / 6
            y = to_y(depth)
            if i > 0:
                canvas.create_line(pad_left, y, pad_left + plot_w, y,
                                   fill="#dddddd")
            canvas.create_text(pad_left - 8, y, text="%.0f" % depth, anchor="e")

        tick = max(self.total_steps // 10, 1)
        for i in range(0, self.total_steps, tick):
            x = to_x(i)
            canvas.create_line(x, pad_top + plot_h, x, pad_top + plot_h + 5)
            canvas.create_text(x, pad_top + plot_h + 16, text=str(i))

        canvas.create_text(pad_left + plot_w / 2, pad_top + plot_h + 34,
                           text="крок маршруту")

        x = to_x(0)

        if self.depths_avg:
            count = len(self.depths_avg)

            if count > 1 and self.show_single.get():
                line = []
                for i, depth in enumerate(self.depths_single):
                    line.extend([to_x(i), to_y(depth)])
                canvas.create_line(line, fill=SINGLE_COLOR)

            if count > 1 and self.show_avg.get():
                line = []
                for i, depth in enumerate(self.depths_avg):
                    line.extend([to_x(i), to_y(depth)])
                canvas.create_line(line, fill=AVERAGED_COLOR, width=2)

            current = count - 1
            x = to_x(current)
            reference = self.depths_avg if self.show_avg.get() else self.depths_single
            y = to_y(reference[current])
            canvas.create_line(x, pad_top, x, y, dash=(4, 3))
            canvas.create_oval(x - 5, y - 5, x + 5, y + 5, outline="black", width=2)
            canvas.create_text(x, y + 16, text="%.1f м" % reference[current])

        canvas.create_rectangle(x - 10, pad_top - 20, x + 10, pad_top,
                                fill="gray70", outline="black")

    def plot(self, canvas, title, xlabel, series, marks, points=()):
        canvas.delete("all")

        width = canvas.winfo_width()
        height = canvas.winfo_height()
        if width < 200 or height < 80:
            return

        pad_left = 60
        pad_right = 20
        pad_top = 26
        pad_bottom = 26

        plot_w = width - pad_left - pad_right
        plot_h = height - pad_top - pad_bottom

        canvas.create_rectangle(pad_left, pad_top, pad_left + plot_w,
                                pad_top + plot_h, outline="black")
        canvas.create_text(pad_left, 12, anchor="w", text=title)

        visible = [item for item in series if item[0]]
        if not visible:
            canvas.create_text(pad_left + plot_w / 2, pad_top + plot_h / 2,
                               text="немає даних", fill="#888888")
            return

        lo = min(min(values) for values, color, width_ in visible)
        hi = max(max(values) for values, color, width_ in visible)
        if hi == lo:
            hi = lo + 1.0
        margin = (hi - lo) * 0.08
        lo -= margin
        hi += margin

        length = max(len(values) for values, color, width_ in visible)

        def to_x(i):
            return pad_left + (i / max(length - 1, 1)) * plot_w

        def to_y(value):
            return pad_top + (hi - value) / (hi - lo) * plot_h

        if lo < 0 < hi:
            zero = to_y(0.0)
            canvas.create_line(pad_left, zero, pad_left + plot_w, zero,
                               fill=ZERO_COLOR)

        canvas.create_text(pad_left - 8, pad_top + 6, text="%.1f" % hi, anchor="e")
        canvas.create_text(pad_left - 8, pad_top + plot_h - 6, text="%.1f" % lo,
                           anchor="e")

        tick = max(length // 10, 1)
        for i in range(0, length, tick):
            x = to_x(i)
            canvas.create_line(x, pad_top + plot_h, x, pad_top + plot_h + 4)
            canvas.create_text(x, pad_top + plot_h + 14, text=str(i))

        canvas.create_text(pad_left + plot_w - 2, 12, anchor="e", text=xlabel)

        for position, mark in enumerate(marks):
            index, color, label = mark
            if index is None:
                continue
            x = to_x(index)
            canvas.create_line(x, pad_top, x, pad_top + plot_h, fill=color,
                               dash=(3, 2))
            if label:
                near_right = x > pad_left + plot_w * 0.7
                anchor = "e" if near_right else "w"
                offset = -4 if near_right else 4
                canvas.create_text(x + offset, pad_top + 9 + position * 13,
                                   anchor=anchor, text=label, fill=color)

        for values, color, line_width in visible:
            flat = []
            for i, value in enumerate(values):
                flat.extend([to_x(i), to_y(value)])
            canvas.create_line(flat, fill=color, width=line_width)

        for index, value, color in points:
            x = to_x(index)
            y = to_y(value)
            canvas.create_oval(x - 4, y - 4, x + 4, y + 4, outline=color, width=2)

    def draw_osc(self):
        single = self.last_single["signal"] if (
            self.last_single and self.show_single.get()) else None
        averaged = self.last_avg["signal"] if (
            self.last_avg and self.show_avg.get()) else None

        marks = []
        if self.last_avg and self.show_avg.get():
            marks.append((self.last_avg["k_max"], PEAK_COLOR, None))

        self.plot(self.osc_canvas,
                  "Сигнал датчика X[i]",
                  "відлік i",
                  [(single, SINGLE_COLOR, 1), (averaged, AVERAGED_COLOR, 1)],
                  marks)

    def draw_corr(self):
        single = self.last_single["correlation"] if (
            self.last_single and self.show_single.get()) else None
        averaged = self.last_avg["correlation"] if (
            self.last_avg and self.show_avg.get()) else None

        marks = []
        points = []
        if self.last_avg and self.show_avg.get():
            k = self.last_avg["k_max"]
            marks.append((k, PEAK_COLOR, "k_max = %d" % k))
            points.append((k, self.last_avg["correlation"][k], PEAK_COLOR))

        self.plot(self.corr_canvas,
                  "Функція взаємної кореляції R(k)",
                  "зсув k",
                  [(single, SINGLE_COLOR, 1), (averaged, AVERAGED_COLOR, 1)],
                  marks, points)


def run():
    root = tk.Tk()
    SonarApp(root)
    root.mainloop()
