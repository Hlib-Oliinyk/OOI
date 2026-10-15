import json
import math
import random
import urllib.error
import urllib.request

BASE_URL = "https://ooi-lab2.up.railway.app"

GEOMETRIC = "geometric"
LINEAR = "linear"
LOGARITHMIC = "logarithmic"

COOLING_LAWS = [GEOMETRIC, LINEAR, LOGARITHMIC]

COOLING_NAMES = {
    GEOMETRIC: "Геометричний",
    LINEAR: "Лінійний",
    LOGARITHMIC: "Логарифмічний",
}


def post_json(path, payload):
    data = json.dumps(payload).encode("utf-8")

    for attempt in range(5):
        request = urllib.request.Request(
            BASE_URL + path, data=data,
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError:
            raise
        except Exception:
            if attempt == 4:
                raise

    return None


def start_session(student_name, variant_number):
    return post_json("/api/start", {
        "student_name": student_name,
        "variant_number": variant_number,
    })


def send_move(session_id, x, y):
    return post_json("/api/move", {
        "session_id": session_id,
        "target_position": {"x": int(x), "y": int(y)},
    })


def cooling(law, t_start, t_current, k, alpha, delta_t):
    if law == LINEAR:
        return t_start - k * delta_t

    if law == LOGARITHMIC:
        return t_start / math.log(1.0 + k)

    return t_current * alpha


def radius(t_current, t_start, r_max):
    value = int(round(r_max * t_current / t_start))

    if value < 1:
        return 1
    if value > r_max:
        return r_max

    return value


def acceptance(delta_e, t_current):
    if delta_e <= 0.0:
        return 1.0

    if t_current <= 0.0:
        return 0.0

    power = -delta_e / t_current
    if power < -700.0:
        return 0.0

    return math.exp(power)


class Params:
    def __init__(self):
        self.t_start = 25.0
        self.t_min = 0.05
        self.alpha = 0.90
        self.delta_t = 0.5
        self.law = GEOMETRIC
        self.r_max = 45
        self.stall_limit = 40
        self.attempts = 80

    def copy(self):
        clone = Params()
        clone.__dict__.update(self.__dict__)
        return clone


class Annealer:
    def __init__(self, session, params=None, seed=None):
        self.session_id = session["session_id"]
        self.grid = session["map"]
        self.width = session["map_size"]["width"]
        self.height = session["map_size"]["height"]

        self.params = params if params else Params()
        self.random = random.Random(seed)

        self.x = session["start_position"]["x"]
        self.y = session["start_position"]["y"]

        if not self.free(self.x, self.y):
            self.x, self.y = self.nearest_free(self.x, self.y)

        self.temperature = self.params.t_start
        self.signal = None
        self.best_signal = -1.0
        self.best_position = (self.x, self.y)

        self.iteration = 0
        self.stall = 0
        self.steps = 0
        self.requests = 0
        self.cache_hits = 0
        self.reheats = 0
        self.remaining = None
        self.finished = False

        self.cache = {}
        self.trail = [(self.x, self.y)]
        self.found = []
        self.temperature_log = [(0, self.temperature)]

    def inside(self, x, y):
        return 0 <= x < self.width and 0 <= y < self.height

    def free(self, x, y):
        return self.inside(x, y) and self.grid[y][x] == 0

    def nearest_free(self, x, y):
        for area in range(1, max(self.width, self.height)):
            for dy in range(-area, area + 1):
                for dx in range(-area, area + 1):
                    if self.free(x + dx, y + dy):
                        return x + dx, y + dy

        return x, y

    def cool(self):
        self.iteration += 1

        value = cooling(self.params.law, self.params.t_start, self.temperature,
                        self.iteration, self.params.alpha, self.params.delta_t)

        if value > self.params.t_start:
            value = self.params.t_start
        if value < self.params.t_min:
            value = self.params.t_min

        self.temperature = value
        self.temperature_log.append((self.requests, self.temperature))

    def reheat(self):
        self.temperature = self.params.t_start
        self.iteration = 0
        self.stall = 0
        self.reheats += 1
        self.temperature_log.append((self.requests, self.temperature))

    def pick_candidate(self, area):
        known = None

        for _ in range(self.params.attempts):
            dx = self.random.randint(-area, area)
            dy = self.random.randint(-area, area)

            if dx == 0 and dy == 0:
                continue

            if dx * dx + dy * dy > area * area:
                continue

            x = self.x + dx
            y = self.y + dy

            if not self.free(x, y):
                continue

            if (x, y) not in self.cache:
                return x, y

            if known is None:
                known = (x, y)

        return known

    def probe(self, x, y):
        if (x, y) in self.cache:
            self.cache_hits += 1
            return self.cache[(x, y)], False

        answer = send_move(self.session_id, x, y)

        self.requests += 1
        self.steps = answer["steps_made"]
        self.remaining = answer["remaining_foxes"]

        signal = answer["signal_level"]
        self.cache[(x, y)] = signal

        return signal, bool(answer["fox_caught"])

    def catch(self, x, y):
        self.found.append((x, y))

        self.cache = {}
        self.best_signal = -1.0
        self.best_position = (x, y)
        self.signal = None

        if self.remaining == 0:
            self.finished = True
        else:
            self.reheat()

    def start(self):
        signal, caught = self.probe(self.x, self.y)

        event = {"x": self.x, "y": self.y, "signal": signal,
                 "accepted": True, "caught": caught, "radius": 0,
                 "delta": 0.0, "probability": 1.0}

        if caught:
            self.catch(self.x, self.y)
            return event

        self.signal = signal
        self.best_signal = signal
        self.best_position = (self.x, self.y)

        return event

    def step(self):
        if self.finished:
            return None

        if self.signal is None:
            return self.start()

        area = radius(self.temperature, self.params.t_start, self.params.r_max)
        candidate = self.pick_candidate(area)

        if candidate is None:
            self.cool()
            return None

        x, y = candidate
        signal, caught = self.probe(x, y)

        delta_e = self.signal - signal
        probability = acceptance(delta_e, self.temperature)
        accepted = probability >= 1.0 or self.random.random() < probability

        if accepted:
            self.x = x
            self.y = y
            self.signal = signal
            self.trail.append((x, y))

        if signal > self.best_signal:
            self.best_signal = signal
            self.best_position = (x, y)
            self.stall = 0
        else:
            self.stall += 1

        event = {"x": x, "y": y, "signal": signal, "accepted": accepted,
                 "caught": caught, "radius": area, "delta": delta_e,
                 "probability": probability}

        if caught:
            self.x = x
            self.y = y
            self.trail.append((x, y))
            self.catch(x, y)
            return event

        self.cool()

        if self.stall >= self.params.stall_limit:
            self.jump_to_best()
            self.reheat()

        return event

    def jump_to_best(self):
        x, y = self.best_position

        if (x, y) in self.cache:
            self.x = x
            self.y = y
            self.signal = self.cache[(x, y)]
            self.trail.append((x, y))

    def run(self, limit=100000, should_stop=None, on_event=None):
        while not self.finished and self.requests < limit:
            if should_stop is not None and should_stop():
                break

            event = self.step()

            if event is not None and on_event is not None:
                on_event(event)

        return self.finished
