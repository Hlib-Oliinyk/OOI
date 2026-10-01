import tkinter as tk

import sonar_core as core

SINGLE_COLOR = "#d62728"
AVERAGED_COLOR = "#1f77b4"
TEMPLATE_COLOR = "#2ca02c"
PEAK_COLOR = "#2ca02c"
ZERO_COLOR = "#2ca02c"

DEFAULT_REPEATS = 4


class PointApp:
    def __init__(self, root, config=None, pulse=None, step=0):
        self.root = root
        self.config = config if config else core.get_config()
        self.pulse = pulse if pulse else core.get_pulse()

        self.sample_rate = self.config["sample_rate"]
        self.sound_speed = self.config["sound_speed"]
        self.total_steps = self.config["total_steps"]

        self.single = None
        self.averaged = None
        self.cells = {}

        self.build()

        self.step_var.set(str(step))
        self.measure()

    def build(self):
        self.root.title("Кореляційний аналіз точки зондування")
        self.root.geometry("1000x780")
        self.root.minsize(780, 620)

        bar = tk.Frame(self.root, padx=8, pady=8)
        bar.pack(side="top", fill="x")
        tk.Frame(self.root, height=1, bg="#b5b5b5").pack(side="top", fill="x")

        tk.Label(bar, text="Крок:").pack(side="left")
        self.step_var = tk.StringVar(value="0")
        tk.Spinbox(bar, from_=0, to=self.total_steps - 1, width=6,
                   textvariable=self.step_var).pack(side="left", padx=(4, 12))

        tk.Label(bar, text="Запитів:").pack(side="left")
        self.repeats_var = tk.StringVar(value=str(DEFAULT_REPEATS))
        tk.Spinbox(bar, from_=1, to=32, width=5,
                   textvariable=self.repeats_var).pack(side="left", padx=(4, 12))

        self.button = tk.Button(bar, text="Виміряти", width=12, pady=8,
                                font=("TkDefaultFont", 9), command=self.measure)
        self.button.pack(side="left")

        self.status = tk.Label(bar, text="", fg="#444444")
        self.status.pack(side="left", padx=10)

        table = tk.Frame(self.root, padx=10, pady=8)
        table.pack(side="bottom", fill="x")
        tk.Frame(self.root, height=1, bg="#b5b5b5").pack(side="bottom", fill="x")

        headers = ("", "k_max", "Затримка", "Глибина", "Пік R(k)",
                   "Пік / СКЗ", "СКВ шуму")
        for column, text in enumerate(headers):
            tk.Label(table, text=text, fg="#666666",
                     font=("TkDefaultFont", 8)).grid(row=0, column=column,
                                                     sticky="w", padx=(0, 18))

        lines = (("усереднення", "avg", AVERAGED_COLOR),
                 ("один запит", "one", SINGLE_COLOR))
        fields = ("k", "delay", "depth", "peak", "snr", "noise")

        for row, (name, key, color) in enumerate(lines, start=1):
            tk.Label(table, text=name, fg=color,
                     font=("TkDefaultFont", 8, "bold")).grid(
                row=row, column=0, sticky="w", padx=(0, 18))
            for column, field in enumerate(fields, start=1):
                var = tk.StringVar(value="-")
                tk.Label(table, textvariable=var,
                         font=("TkDefaultFont", 9)).grid(row=row, column=column,
                                                         sticky="w",
                                                         padx=(0, 18))
                self.cells[(key, field)] = var

        plots = tk.Frame(self.root, padx=5, pady=5)
        plots.pack(side="top", fill="both", expand=True)
        plots.columnconfigure(0, weight=1)
        plots.rowconfigure(0, weight=3)
        plots.rowconfigure(1, weight=2)
        plots.rowconfigure(2, weight=3)

        self.signal_canvas = tk.Canvas(plots, bg="white", height=190)
        self.signal_canvas.grid(row=0, column=0, sticky="nsew")

        self.template_canvas = tk.Canvas(plots, bg="white", height=130)
        self.template_canvas.grid(row=1, column=0, sticky="nsew", pady=(6, 0))

        self.corr_canvas = tk.Canvas(plots, bg="white", height=190)
        self.corr_canvas.grid(row=2, column=0, sticky="nsew", pady=(6, 0))

        self.signal_canvas.bind("<Configure>", lambda e: self.draw_signal())
        self.template_canvas.bind("<Configure>", lambda e: self.draw_template())
        self.corr_canvas.bind("<Configure>", lambda e: self.draw_corr())

    def read_step(self):
        try:
            step = int(self.step_var.get())
        except ValueError:
            return 0
        if step < 0:
            return 0
        if step > self.total_steps - 1:
            return self.total_steps - 1
        return step

    def read_repeats(self):
        try:
            repeats = int(self.repeats_var.get())
        except ValueError:
            return DEFAULT_REPEATS
        if repeats < 1:
            return 1
        if repeats > 32:
            return 32
        return repeats

    def measure(self):
        step = self.read_step()
        repeats = self.read_repeats()

        self.step_var.set(str(step))
        self.repeats_var.set(str(repeats))
        self.repeats = repeats
        self.step = step

        self.button.configure(state="disabled")
        self.status.configure(text="зондування...")
        self.root.update_idletasks()

        try:
            signals = core.fetch_signals(step, repeats)
        except Exception as error:
            self.status.configure(text="помилка зв'язку: %s" % error)
            self.button.configure(state="normal")
            return

        self.single = core.analyse(signals[0], self.pulse, self.sample_rate,
                                   self.sound_speed)
        if repeats > 1:
            self.averaged = core.analyse(core.average_signals(signals),
                                         self.pulse, self.sample_rate,
                                         self.sound_speed)
        else:
            self.averaged = None

        self.status.configure(text="крок %d, запитів %d" % (step, repeats))
        self.button.configure(state="normal")

        self.fill_cells("one", self.single)
        self.fill_cells("avg", self.averaged)
        self.draw_all()

    def fill_cells(self, key, result):
        if result is None:
            for field in ("k", "delay", "depth", "peak", "snr", "noise"):
                self.cells[(key, field)].set("-")
            return

        self.cells[(key, "k")].set("%d" % result["k_max"])
        self.cells[(key, "delay")].set("%.2f мс" % (result["delay"] * 1000))
        self.cells[(key, "depth")].set("%.2f м" % result["depth"])
        self.cells[(key, "peak")].set("%.1f" % result["peak"])
        self.cells[(key, "snr")].set("%.2f" % result["snr"])
        self.cells[(key, "noise")].set("%.3f" % result["noise"])

    def reference(self):
        return self.averaged if self.averaged else self.single

    def draw_all(self):
        self.draw_signal()
        self.draw_template()
        self.draw_corr()

    def plot(self, canvas, title, xlabel, series, mark=None, peak_of=None):
        canvas.delete("all")

        width = canvas.winfo_width()
        height = canvas.winfo_height()
        if width < 200 or height < 80:
            return

        pad_left = 62
        pad_right = 18
        pad_top = 26
        pad_bottom = 26

        plot_w = width - pad_left - pad_right
        plot_h = height - pad_top - pad_bottom

        canvas.create_rectangle(pad_left, pad_top, pad_left + plot_w,
                                pad_top + plot_h, outline="black")
        canvas.create_text(pad_left, 12, anchor="w", text=title)
        canvas.create_text(pad_left + plot_w, 12, anchor="e", text=xlabel,
                           fill="#666666")

        visible = [item for item in series if item[0]]
        if not visible:
            canvas.create_text(pad_left + plot_w / 2, pad_top + plot_h / 2,
                               text="немає даних", fill="#888888")
            return

        lo = min(min(values) for values, color, label in visible)
        hi = max(max(values) for values, color, label in visible)
        if hi == lo:
            hi = lo + 1.0
        margin = (hi - lo) * 0.08
        lo -= margin
        hi += margin

        length = max(len(values) for values, color, label in visible)

        def to_x(i):
            return pad_left + (i / max(length - 1, 1)) * plot_w

        def to_y(value):
            return pad_top + (hi - value) / (hi - lo) * plot_h

        if lo < 0 < hi:
            zero = to_y(0.0)
            canvas.create_line(pad_left, zero, pad_left + plot_w, zero,
                               fill=ZERO_COLOR)

        canvas.create_text(pad_left - 8, pad_top + 6, text="%.1f" % hi,
                           anchor="e")
        canvas.create_text(pad_left - 8, pad_top + plot_h - 6, text="%.1f" % lo,
                           anchor="e")

        tick = max(length // 10, 1)
        for i in range(0, length, tick):
            x = to_x(i)
            canvas.create_line(x, pad_top + plot_h, x, pad_top + plot_h + 4)
            canvas.create_text(x, pad_top + plot_h + 14, text=str(i))

        if mark is not None:
            x = to_x(mark)
            canvas.create_line(x, pad_top, x, pad_top + plot_h, fill=PEAK_COLOR,
                               dash=(3, 2))

        for values, color, label in visible:
            flat = []
            for i, value in enumerate(values):
                flat.extend([to_x(i), to_y(value)])
            canvas.create_line(flat, fill=color)

        if peak_of is not None and mark is not None:
            x = to_x(mark)
            y = to_y(peak_of[mark])
            canvas.create_oval(x - 4, y - 4, x + 4, y + 4, outline=PEAK_COLOR,
                               width=2)

        row = 0
        for values, color, label in visible:
            if not label:
                continue
            canvas.create_text(pad_left + plot_w - 6, pad_top + 10 + row * 14,
                               anchor="e", text=label, fill=color)
            row += 1

    def draw_signal(self):
        single = self.single["signal"] if self.single else None
        averaged = self.averaged["signal"] if self.averaged else None
        reference = self.reference()

        self.plot(self.signal_canvas,
                  "1. Прийнятий сигнал X[i] для точки step = %d"
                  % getattr(self, "step", 0),
                  "відлік i",
                  [(single, SINGLE_COLOR, "одне вимірювання"),
                   (averaged, AVERAGED_COLOR,
                    "усереднення %d вимірювань" % getattr(self, "repeats", 1)
                    if averaged else None)],
                  reference["k_max"] if reference else None)

    def draw_template(self):
        self.plot(self.template_canvas,
                  "2. Еталонний зондувальний імпульс Y[j]  (%d відліків)"
                  % len(self.pulse),
                  "відлік j",
                  [(self.pulse, TEMPLATE_COLOR, None)])

    def draw_corr(self):
        single = self.single["correlation"] if self.single else None
        averaged = self.averaged["correlation"] if self.averaged else None
        reference = self.reference()

        single_label = None
        if self.single:
            single_label = "одного сигналу, k = %d" % self.single["k_max"]

        averaged_label = None
        if self.averaged:
            averaged_label = "усередненого, k = %d" % self.averaged["k_max"]

        self.plot(self.corr_canvas,
                  "3. Функції взаємної кореляції R(k)",
                  "зсув k",
                  [(single, SINGLE_COLOR, single_label),
                   (averaged, AVERAGED_COLOR, averaged_label)],
                  reference["k_max"] if reference else None,
                  reference["correlation"] if reference else None)


def open_window(parent, config=None, pulse=None, step=0):
    window = tk.Toplevel(parent)
    PointApp(window, config, pulse, step)
    window.transient(parent)
    return window


def run():
    root = tk.Tk()
    PointApp(root)
    root.mainloop()


if __name__ == "__main__":
    run()
