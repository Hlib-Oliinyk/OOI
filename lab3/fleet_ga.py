import random

TOURNAMENT = "tournament"
ROULETTE = "roulette"

ONE_POINT = "one_point"
TWO_POINT = "two_point"

SELECTION_NAMES = {
    TOURNAMENT: "Турнірний",
    ROULETTE: "Рулетка",
}

CROSSOVER_NAMES = {
    ONE_POINT: "Одноточкове",
    TWO_POINT: "Двоточкове",
}


class GAParams:
    def __init__(self):
        self.population = 100
        self.pc = 0.9
        self.pm = 0.1
        self.tournament = 3
        self.selection = TOURNAMENT
        self.crossover = TWO_POINT
        self.elite = 2
        self.max_generations = 1000
        self.stagnation = 300
        self.restart = False
        self.local_share = 0.5

    def copy(self):
        clone = GAParams()
        clone.__dict__.update(self.__dict__)
        return clone


class GeneticAlgorithm:
    def __init__(self, variant, params=None, seed=None):
        self.variant = variant
        self.params = params if params else GAParams()
        self.random = random.Random(seed)

        self.length = variant.gene_count()

        self.population = []
        self.scores = []

        self.generation = 0
        self.evaluations = 0
        self.stall = 0
        self.restarts = 0

        self.best_genes = None
        self.best_fitness = None

        self.history_best = []
        self.history_mean = []

        self.finished = False
        self.success = False
        self.solved_generation = None
        self.solved_evaluations = None

        self.initialize()

    def evaluate(self, genes):
        self.evaluations += 1
        score = self.variant.fitness(genes)

        if score == 0 and self.solved_evaluations is None:
            self.solved_evaluations = self.evaluations

        return score

    def random_genes(self):
        return [self.random.randrange(self.variant.gene_range(i))
                for i in range(self.length)]

    def initialize(self):
        self.population = [self.random_genes() for _ in range(self.params.population)]
        self.scores = [self.evaluate(genes) for genes in self.population]
        self.remember()

    def remember(self):
        best = max(range(len(self.scores)), key=lambda i: self.scores[i])

        if self.best_fitness is None or self.scores[best] > self.best_fitness:
            self.best_fitness = self.scores[best]
            self.best_genes = list(self.population[best])
            self.stall = 0
        else:
            self.stall += 1

        self.history_best.append(self.best_fitness)
        self.history_mean.append(sum(self.scores) / len(self.scores))

    def tournament(self):
        size = max(1, min(self.params.tournament, len(self.population)))
        chosen = self.random.sample(range(len(self.population)), size)
        winner = max(chosen, key=lambda i: self.scores[i])
        return self.population[winner]

    def roulette(self):
        lowest = min(self.scores)
        shifted = [score - lowest + 1.0 for score in self.scores]
        total = sum(shifted)

        point = self.random.random() * total
        running = 0.0

        for index, value in enumerate(shifted):
            running += value
            if running >= point:
                return self.population[index]

        return self.population[-1]

    def select(self):
        if self.params.selection == ROULETTE:
            return self.roulette()

        return self.tournament()

    def crossover(self, first, second):
        if self.length < 2 or self.random.random() >= self.params.pc:
            return list(first), list(second)

        if self.params.crossover == ONE_POINT or self.length < 3:
            cut = self.random.randint(1, self.length - 1)
            return first[:cut] + second[cut:], second[:cut] + first[cut:]

        left, right = sorted(self.random.sample(range(1, self.length), 2))
        child_a = first[:left] + second[left:right] + first[right:]
        child_b = second[:left] + first[left:right] + second[right:]
        return child_a, child_b

    def mutate(self, genes):
        for index in range(self.length):
            if self.random.random() >= self.params.pm:
                continue

            genes[index] = self.new_gene(index, genes[index])

        return genes

    def new_gene(self, index, gene):
        length = self.variant.ships[index]
        close = self.variant.neighbours[length][gene]

        if close and self.random.random() < self.params.local_share:
            return self.random.choice(close)

        count = self.variant.gene_range(index)
        if count == 1:
            return gene

        value = self.random.randrange(count - 1)
        return value if value < gene else value + 1

    def step(self):
        if self.finished:
            return

        if self.best_fitness == 0:
            self.finish(True)
            return

        if self.generation >= self.params.max_generations:
            self.finish(False)
            return

        if self.stall >= self.params.stagnation:
            if not self.params.restart:
                self.finish(False)
                return

            self.restart_population()
            return

        order = sorted(range(len(self.scores)), key=lambda i: self.scores[i], reverse=True)
        elite = min(self.params.elite, len(order))

        children = [list(self.population[i]) for i in order[:elite]]
        child_scores = [self.scores[i] for i in order[:elite]]

        while len(children) < self.params.population:
            first, second = self.crossover(self.select(), self.select())

            for child in (first, second):
                if len(children) >= self.params.population:
                    break

                self.mutate(child)
                children.append(child)
                child_scores.append(self.evaluate(child))

        self.population = children
        self.scores = child_scores
        self.generation += 1
        self.remember()

        if self.best_fitness == 0:
            self.finish(True)

    def restart_population(self):
        self.restarts += 1
        self.generation += 1

        self.population = [self.random_genes() for _ in range(self.params.population)]
        self.scores = [self.evaluate(genes) for genes in self.population]

        self.remember()
        self.stall = 0

        if self.best_fitness == 0:
            self.finish(True)

    def finish(self, success):
        self.finished = True
        self.success = success

        if success and self.solved_generation is None:
            self.solved_generation = self.generation

    def run(self, should_stop=None, on_generation=None):
        if self.best_fitness == 0:
            self.finish(True)

        while not self.finished:
            if should_stop is not None and should_stop():
                break

            self.step()

            if on_generation is not None:
                on_generation(self)

        return self.success
