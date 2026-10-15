import queue
import threading
import tkinter as tk
import tkinter.ttk as ttk

import fox_core as core

STUDENT_NAME = "Олійник Г.І."
VARIANT = 5

CELL_MIN = 4
CELL_MAX = 7


class FoxApp:
    def __init__(self, root):
        self.root = root

        self.session = None
        self.annealer = None
        self.worker = None
        self.stop_flag = threading.Event()
        self.events = queue.Queue()

        self.agent_item = None
        self.plot_dirty = False
        self.busy = False

        self.shown_signal = None
        self.shown_best = 0.0

        self.cell = self.pick_cell()

        self.build()
        self.poll()
        self.new_session()

    def pick_cell(self):
        free = self.root.winfo_screenheight() - 230
        cell = free // 100

        if cell < CELL_MIN:
            return CELL_MIN
        if cell > CELL_MAX:
            return CELL_MAX

        return cell

    def build(self):
        self.root.title("Лабораторна 2. Олійник Гліб, ІПЗ-24-2")
        self.root.geometry("%dx%d+20+10" % (100 * self.cell + 520,
                                            100 * self.cell + 130))
        self.root.minsize(960, 620)

        button_font = ("TkDefaultFont", 9)

        bar = tk.Frame(self.root, padx=8, pady=8)
        bar.pack(side="top", fill="x")
        tk.Frame(self.root, height=1, bg="#b5b5b5").pack(side="top", fill="x")

        self.run_button = tk.Button(bar, text="Старт", width=11, pady=8,
                                    font=button_font, command=self.toggle)
        self.run_button.pack(side="left")

        self.step_button = tk.Button(bar, text="Один крок", width=11, pady=8,
                                     font=button_font, command=self.single_step)
        self.step_button.pack(side="left", padx=6)

        self.reset_button = tk.Button(bar, text="Нова сесія", width=11, pady=8,
                                      font=button_font, command=self.new_session)
        self.reset_button.pack(side="left")

        self.params_frame = tk.LabelFrame(bar, text="Гіперпараметри", padx=6, pady=2,
                                          font=("TkDefaultFont", 8))
        self.params_frame.pack(side="left", padx=(14, 0))

        self.vars = {}
        defaults = core.Params()

        self.add_entry("To", "t_start", defaults.t_start, 5)
        self.add_entry("alpha", "alpha", defaults.alpha, 5)
        self.add_entry("R_max", "r_max", defaults.r_max, 4)
        self.add_entry("stall", "stall_limit", defaults.stall_limit, 4)

        tk.Label(self.params_frame, text="закон",
                 font=("TkDefaultFont", 8)).pack(side="left", padx=(8, 2))

        self.law_var = tk.StringVar(value=core.COOLING_NAMES[defaults.law])
        self.law_box = ttk.Combobox(
            self.params_frame, textvariable=self.law_var, width=13,
            state="readonly", font=("TkDefaultFont", 8),
            values=[core.COOLING_NAMES[law] for law in core.COOLING_LAWS])
        self.law_box.pack(side="left")

        self.progress = ttk.Progressbar(bar, length=150, maximum=3)
        self.progress.pack(side="right", padx=(8, 0))

        self.hint = tk.Label(bar, text="", anchor="e", width=24, fg="#444444")
        self.hint.pack(side="right")

        self.status = tk.Label(self.root, text="", anchor="w", bg="black",
                               fg="white", padx=6, pady=3,
                               font=("TkDefaultFont", 9, "bold"))
        self.status.pack(side="bottom", fill="x")

        side = tk.Frame(self.root, padx=6, pady=6)
        side.pack(side="right", fill="y")

        tk.Label(side, text="Температура T(k)",
                 font=("TkDefaultFont", 9, "bold")).pack(anchor="w")

        self.plot = tk.Canvas(side, bg="white", width=330, height=200,
                              highlightthickness=1, highlightbackground="#b5b5b5")
        self.plot.pack(pady=(2, 10))

        tk.Label(side, text="Показники",
                 font=("TkDefaultFont", 9, "bold")).pack(anchor="w")

        self.info = tk.Frame(side)
        self.info.pack(anchor="w", pady=(2, 10), fill="x")

        self.rows = {}
        for key, title in [("requests", "Запитів до API"),
                           ("steps", "steps_made (сервер)"),
                           ("reheats", "Повторних нагрівань"),
                           ("radius", "Поточний радіус R"),
                           ("best", "Найкращий сигнал"),
                           ("position", "Позиція агента")]:
            self.add_row(key, title)

        tk.Label(side, text="Знайдені об'єкти",
                 font=("TkDefaultFont", 9, "bold")).pack(anchor="w")

        self.found_box = tk.Listbox(side, height=5, width=32,
                                    font=("Consolas", 9))
        self.found_box.pack(anchor="w", pady=(2, 0))

        holder = tk.Frame(self.root, padx=6, pady=6)
        holder.pack(side="left", fill="both", expand=True)

        self.canvas = tk.Canvas(holder, bg="white",
                                width=100 * self.cell, height=100 * self.cell,
                                highlightthickness=1,
                                highlightbackground="#555555")
        self.canvas.pack(anchor="n")

        self.set_status("Підключення до сервера...")

    def add_entry(self, title, key, value, width):
        tk.Label(self.params_frame, text=title,
                 font=("TkDefaultFont", 8)).pack(side="left", padx=(6, 2))

        var = tk.StringVar(value=str(value))
        tk.Entry(self.params_frame, textvariable=var, width=width,
                 font=("TkDefaultFont", 8)).pack(side="left")

        self.vars[key] = var

    def add_row(self, key, title):
        line = tk.Frame(self.info)
        line.pack(fill="x")

        tk.Label(line, text=title + ":", anchor="w", width=20,
                 font=("TkDefaultFont", 8)).pack(side="left")

        value = tk.Label(line, text="—", anchor="w", font=("Consolas", 9))
        value.pack(side="left")

        self.rows[key] = value

    def read_params(self):
        params = core.Params()

        try:
            params.t_start = float(self.vars["t_start"].get().replace(",", "."))
            params.alpha = float(self.vars["alpha"].get().replace(",", "."))
            params.r_max = int(float(self.vars["r_max"].get()))
            params.stall_limit = int(float(self.vars["stall_limit"].get()))
        except ValueError:
            self.hint.config(text="хибні параметри, взято типові")
            return core.Params()

        if params.t_start <= 0:
            params.t_start = 25.0
        if params.r_max < 1:
            params.r_max = 1

        chosen = self.law_var.get()
        for law in core.COOLING_LAWS:
            if core.COOLING_NAMES[law] == chosen:
                params.law = law

        params.delta_t = params.t_start / 60.0

        return params

    def new_session(self):
        if self.busy:
            return

        self.pause()
        self.busy = True
        self.set_buttons("disabled")
        self.set_status("Підключення до сервера...")

        thread = threading.Thread(target=self.load_session, daemon=True)
        thread.start()

    def load_session(self):
        try:
            session = core.start_session(STUDENT_NAME, VARIANT)
            self.events.put({"kind": "session", "session": session})
        except Exception as error:
            self.events.put({"kind": "error", "text": str(error)})

    def apply_session(self, session):
        self.session = session
        self.annealer = core.Annealer(session, self.read_params())

        self.shown_signal = None
        self.shown_best = 0.0
        self.found_box.delete(0, "end")

        self.busy = False
        self.set_buttons("normal")
        self.draw_map()
        self.refresh()
        self.hint.config(text="сесія готова")

    def running(self):
        return self.worker is not None and self.worker.is_alive()

    def toggle(self):
        if self.running():
            self.pause()
        else:
            self.start()

    def start(self):
        if self.annealer is None or self.annealer.finished or self.busy:
            return

        self.annealer.params = self.read_params()
        self.stop_flag.clear()

        self.run_button.config(text="Пауза")
        self.step_button.config(state="disabled")
        self.reset_button.config(state="disabled")
        self.hint.config(text="пошук триває")

        self.worker = threading.Thread(target=self.search, daemon=True)
        self.worker.start()

    def pause(self):
        self.stop_flag.set()

    def search(self):
        try:
            self.annealer.run(
                limit=20000,
                should_stop=self.stop_flag.is_set,
                on_event=lambda event: self.events.put(
                    {"kind": "event", "event": event}),
            )
        except Exception as error:
            self.events.put({"kind": "error", "text": str(error)})

        self.events.put({"kind": "idle"})

    def single_step(self):
        if self.annealer is None or self.annealer.finished or self.busy:
            return
        if self.running():
            return

        self.annealer.params = self.read_params()

        def once():
            try:
                event = self.annealer.step()
                if event is not None:
                    self.events.put({"kind": "event", "event": event})
            except Exception as error:
                self.events.put({"kind": "error", "text": str(error)})

            self.events.put({"kind": "idle"})

        self.worker = threading.Thread(target=once, daemon=True)
        self.worker.start()

    def set_buttons(self, state):
        self.run_button.config(state=state)
        self.step_button.config(state=state)
        self.reset_button.config(state=state)

    def poll(self):
        redraw = False

        while True:
            try:
                message = self.events.get_nowait()
            except queue.Empty:
                break

            kind = message["kind"]

            if kind == "session":
                self.apply_session(message["session"])
            elif kind == "event":
                self.draw_event(message["event"])
                redraw = True
            elif kind == "idle":
                self.on_idle()
            elif kind == "error":
                self.hint.config(text="помилка зв'язку")
                self.set_status("Помилка: " + message["text"])
                self.busy = False
                self.set_buttons("normal")

        if redraw:
            self.refresh()

        if self.plot_dirty:
            self.draw_plot()
            self.plot_dirty = False

        self.root.after(40, self.poll)

    def on_idle(self):
        self.run_button.config(text="Старт")
        self.step_button.config(state="normal")
        self.reset_button.config(state="normal")

        if self.annealer is not None and self.annealer.finished:
            self.run_button.config(state="disabled")
            self.hint.config(text="всі об'єкти знайдено")
        else:
            self.run_button.config(state="normal")
            self.hint.config(text="пауза")

    def cell_box(self, x, y, inset=0):
        left = x * self.cell + inset
        top = y * self.cell + inset
        return left, top, left + self.cell - inset, top + self.cell - inset

    def draw_map(self):
        self.canvas.delete("all")
        self.agent_item = None

        grid = self.annealer.grid

        for y in range(self.annealer.height):
            row = grid[y]
            x = 0
            while x < self.annealer.width:
                if row[x] == 1:
                    span = x
                    while span < self.annealer.width and row[span] == 1:
                        span += 1

                    self.canvas.create_rectangle(
                        x * self.cell, y * self.cell,
                        span * self.cell, (y + 1) * self.cell,
                        fill="#2e7d32", outline="")
                    x = span
                else:
                    x += 1

        sx, sy = self.annealer.trail[0]
        self.canvas.create_rectangle(*self.cell_box(sx, sy),
                                     fill="#7f7f7f", outline="")

        self.draw_agent()
        self.plot_dirty = True

    def draw_event(self, event):
        x = event["x"]
        y = event["y"]

        self.shown_signal = event["signal"]
        if event["signal"] > self.shown_best:
            self.shown_best = event["signal"]

        color = "#9ecae1" if event["accepted"] else "#e0e0e0"
        self.canvas.create_rectangle(*self.cell_box(x, y), fill=color,
                                     outline="", tags="path")

        if event["caught"]:
            self.mark_found(x, y)
            self.found_box.insert("end", "%d.  x=%-4d y=%-4d  крок %d"
                                  % (len(self.annealer.found), x, y,
                                     self.annealer.requests))

        self.draw_agent()
        self.plot_dirty = True

    def mark_found(self, x, y):
        left, top, right, bottom = self.cell_box(x, y)
        pad = 3 * self.cell

        self.canvas.create_rectangle(left - pad, top - pad, right + pad,
                                     bottom + pad, outline="#ff9900",
                                     width=2, tags="found")
        self.canvas.create_rectangle(left, top, right, bottom,
                                     fill="#ff9900", outline="#8a4b00",
                                     tags="found")

    def draw_agent(self):
        if self.annealer is None:
            return

        box = self.cell_box(self.annealer.x, self.annealer.y)

        if self.agent_item is None:
            self.agent_item = self.canvas.create_rectangle(
                *box, fill="#d62728", outline="black", tags="agent")
        else:
            self.canvas.coords(self.agent_item, *box)
            self.canvas.tag_raise(self.agent_item)

    def draw_plot(self):
        self.plot.delete("all")

        if self.annealer is None:
            return

        log = self.annealer.temperature_log
        if len(log) < 2:
            return

        width = int(self.plot.winfo_width()) or 330
        height = int(self.plot.winfo_height()) or 200

        pad_left = 34
        pad_bottom = 18
        pad_top = 8
        pad_right = 8

        inner_w = width - pad_left - pad_right
        inner_h = height - pad_top - pad_bottom

        top_value = max(self.annealer.params.t_start, max(t for _, t in log))
        last_k = max(1, log[-1][0])

        self.plot.create_rectangle(pad_left, pad_top, width - pad_right,
                                   height - pad_bottom, outline="#b5b5b5")

        for part in range(5):
            value = top_value * part / 4.0
            y = height - pad_bottom - inner_h * part / 4.0

            self.plot.create_line(pad_left, y, width - pad_right, y,
                                  fill="#eeeeee")
            self.plot.create_text(pad_left - 4, y, text="%.0f" % value,
                                  anchor="e", font=("TkDefaultFont", 7))

        points = []
        for k, temperature in log:
            px = pad_left + inner_w * k / last_k
            py = height - pad_bottom - inner_h * temperature / top_value
            points.extend([px, py])

        self.plot.create_line(*points, fill="#1f77b4", width=1)

        for index in range(1, len(log)):
            if log[index][1] > log[index - 1][1] + 1e-9:
                px = pad_left + inner_w * log[index][0] / last_k
                self.plot.create_line(px, pad_top, px, height - pad_bottom,
                                      fill="#d62728", dash=(2, 3))

        self.plot.create_text(width - pad_right, height - pad_bottom + 9,
                              text="запитів: %d" % last_k, anchor="e",
                              font=("TkDefaultFont", 7))

    def set_status(self, text):
        self.status.config(text=text)

    def refresh(self):
        agent = self.annealer
        if agent is None:
            return

        remaining = agent.remaining if agent.remaining is not None else "—"
        signal = "—" if self.shown_signal is None else "%.4f" % self.shown_signal

        self.set_status(
            "Кроків: %d | Залишилось лисиць: %s | Сигнал: %s | Темп: %.2f"
            % (agent.steps, remaining, signal, agent.temperature))

        area = core.radius(agent.temperature, agent.params.t_start,
                           agent.params.r_max)

        self.rows["requests"].config(text=str(agent.requests))
        self.rows["steps"].config(text=str(agent.steps))
        self.rows["reheats"].config(text=str(agent.reheats))
        self.rows["radius"].config(text=str(area))
        self.rows["best"].config(text="%.4f" % self.shown_best)
        self.rows["position"].config(text="(%d, %d)" % (agent.x, agent.y))

        if agent.remaining is not None:
            self.progress.config(maximum=agent.remaining + len(agent.found))

        self.progress.config(value=len(agent.found))


def run():
    root = tk.Tk()
    FoxApp(root)
    root.mainloop()
