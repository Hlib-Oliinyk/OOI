import math
import random

GEOMETRIC = "geometric"
LINEAR = "linear"
LOGARITHMIC = "logarithmic"

COOLING_LAWS = [GEOMETRIC, LINEAR, LOGARITHMIC]

COOLING_NAMES = {
    GEOMETRIC: "Геометричний",
    LINEAR: "Лінійний",
    LOGARITHMIC: "Логарифмічний",
}


def cooling(law, t_start, t_current, k, alpha, delta_t):
    if law == LINEAR:
        return t_start - k * delta_t

    if law == LOGARITHMIC:
        return t_start / math.log(1.0 + k)

    return t_current * alpha


def acceptance(delta_e, t_current):
    if delta_e <= 0.0:
        return 1.0

    if t_current <= 0.0:
        return 0.0

    power = -delta_e / t_current
    if power < -700.0:
        return 0.0

    return math.exp(power)


class SAParams:
    def __init__(self):
        self.t_start = 5.0
        self.t_min = 0.01
        self.alpha = 0.95
        self.law = GEOMETRIC
        self.delta_t = 0.05
        self.iterations = 100
        self.max_evaluations = 200000
        self.local_share = 0.5

    def copy(self):
        clone = SAParams()
        clone.__dict__.update(self.__dict__)
        return clone


class SimulatedAnnealing:
    def __init__(self, variant, params=None, seed=None):
        self.variant = variant
        self.params = params if params else SAParams()
        self.random = random.Random(seed)

        self.length = variant.gene_count()

        self.temperature = self.params.t_start
        self.level = 0
        self.evaluations = 0

        self.genes = [self.random.randrange(variant.gene_range(i))
                      for i in range(self.length)]
        self.energy = self.evaluate(self.genes)

        self.best_genes = list(self.genes)
        self.best_energy = self.energy

        self.history_level = []
        self.history_temperature = []
        self.history_energy = []
        self.history_best = []
        self.history_accepted = []

        self.finished = False
        self.success = False
        self.solved_level = None
        self.solved_evaluations = None

        if self.energy == 0:
            self.solved_evaluations = self.evaluations

    def evaluate(self, genes):
        self.evaluations += 1
        return -self.variant.fitness(genes)

    def neighbour(self):
        genes = list(self.genes)
        index = self.random.randrange(self.length)

        length = self.variant.ships[index]
        close = self.variant.neighbours[length][genes[index]]

        if close and self.random.random() < self.params.local_share:
            genes[index] = self.random.choice(close)
            return genes

        count = self.variant.gene_range(index)
        if count > 1:
            value = self.random.randrange(count - 1)
            genes[index] = value if value < genes[index] else value + 1

        return genes

    def cool(self):
        self.level += 1

        value = cooling(self.params.law, self.params.t_start, self.temperature,
                        self.level, self.params.alpha, self.params.delta_t)

        if value > self.params.t_start:
            value = self.params.t_start

        self.temperature = value

    def step(self):
        if self.finished:
            return

        if self.best_energy == 0:
            self.finish(True)
            return

        if self.temperature < self.params.t_min:
            self.finish(False)
            return

        if self.evaluations >= self.params.max_evaluations:
            self.finish(False)
            return

        accepted = 0
        tried = 0

        for _ in range(self.params.iterations):
            candidate = self.neighbour()
            energy = self.evaluate(candidate)
            tried += 1

            delta_e = energy - self.energy
            probability = acceptance(delta_e, self.temperature)

            if probability >= 1.0 or self.random.random() < probability:
                self.genes = candidate
                self.energy = energy
                accepted += 1

            if self.energy < self.best_energy:
                self.best_energy = self.energy
                self.best_genes = list(self.genes)

            if self.best_energy == 0:
                self.solved_evaluations = self.evaluations
                break

            if self.evaluations >= self.params.max_evaluations:
                break

        self.history_level.append(self.level)
        self.history_temperature.append(self.temperature)
        self.history_energy.append(self.energy)
        self.history_best.append(self.best_energy)
        self.history_accepted.append(accepted / tried if tried else 0.0)

        if self.best_energy == 0:
            self.finish(True)
            return

        self.cool()

    def finish(self, success):
        self.finished = True
        self.success = success

        if success and self.solved_level is None:
            self.solved_level = self.level

    def best_fitness(self):
        return -self.best_energy

    def run(self, should_stop=None, on_level=None):
        if self.best_energy == 0:
            self.finish(True)

        while not self.finished:
            if should_stop is not None and should_stop():
                break

            self.step()

            if on_level is not None:
                on_level(self)

        return self.success
