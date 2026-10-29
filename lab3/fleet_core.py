import io
import json
import os

HORIZONTAL = "H"
VERTICAL = "V"

ORIENTATION_NAMES = {
    HORIZONTAL: "горизонтально",
    VERTICAL: "вертикально",
}

W_OUT = 10
W_REEF = 10
W_OVERLAP = 4
W_TOUCH = 1

RULE_NAMES = {
    "out_of_field": "2. Корабель виходить за межі поля",
    "on_reef": "3. Корабель стоїть на рифі",
    "overlap": "4. Кораблі перетинаються",
    "touch": "5. Кораблі торкаються стороною або кутом",
}


def ship_cells(length, x, y, orientation):
    if orientation == HORIZONTAL:
        return tuple((x + i, y) for i in range(length))

    return tuple((x, y + i) for i in range(length))


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def check_data(data):
    problems = []

    if not isinstance(data, dict):
        return ["Файл має містити JSON-об'єкт з полями field_size, ships, reefs."]

    for key in ("field_size", "ships", "reefs"):
        if key not in data:
            problems.append("Відсутнє поле \"%s\"." % key)

    if problems:
        return problems

    size = data["field_size"]
    ships = data["ships"]
    reefs = data["reefs"]

    if not is_int(size) or size < 1:
        problems.append("field_size має бути додатним цілим числом, отримано %r." % (size,))
        return problems

    if not isinstance(ships, list) or not ships:
        problems.append("ships має бути непорожнім списком довжин кораблів.")
    else:
        for index, length in enumerate(ships):
            if not is_int(length) or length < 1:
                problems.append("Корабель №%d: довжина %r не є додатним цілим числом."
                                % (index + 1, length))
            elif length > size:
                problems.append("Корабель №%d: довжина %d більша за розмір поля %d."
                                % (index + 1, length, size))

    if not isinstance(reefs, list):
        problems.append("reefs має бути списком координат [x, y].")
    else:
        seen = set()
        for index, reef in enumerate(reefs):
            if (not isinstance(reef, list) or len(reef) != 2
                    or not is_int(reef[0]) or not is_int(reef[1])):
                problems.append("Риф №%d: %r не є парою цілих чисел [x, y]."
                                % (index + 1, reef))
                continue

            x, y = reef
            if not (0 <= x < size and 0 <= y < size):
                problems.append("Риф №%d: (%d, %d) поза межами поля %dx%d."
                                % (index + 1, x, y, size, size))
            elif (x, y) in seen:
                problems.append("Риф №%d: (%d, %d) повторюється." % (index + 1, x, y))

            seen.add((x, y))

    return problems


class Variant:
    def __init__(self, size, ships, reefs, name=""):
        self.size = size
        self.ships = list(ships)
        self.reefs = set(reefs)
        self.name = name

        self.shapes = []
        self.cells = []
        self.placements = {}
        self.neighbours = {}
        self.pair_cache = {}

        for length in sorted(set(self.ships)):
            self.build_placements(length)

        missing = [length for length in sorted(set(self.ships))
                   if not self.placements[length]]
        if missing:
            raise ValueError("Для кораблів довжини %s немає жодного допустимого положення."
                             % ", ".join(str(length) for length in missing))

    def inside(self, x, y):
        return 0 <= x < self.size and 0 <= y < self.size

    def build_placements(self, length):
        ids = []
        orientations = [HORIZONTAL, VERTICAL] if length > 1 else [HORIZONTAL]

        for orientation in orientations:
            for y in range(self.size):
                for x in range(self.size):
                    cells = ship_cells(length, x, y, orientation)

                    if all(self.inside(a, b) and (a, b) not in self.reefs
                           for a, b in cells):
                        ids.append(len(self.shapes))
                        self.shapes.append((length, x, y, orientation))
                        self.cells.append(cells)

        self.placements[length] = ids

        near = []
        for i, own in enumerate(ids):
            _, x, y, _ = self.shapes[own]
            close = []

            for j, other in enumerate(ids):
                if i == j:
                    continue

                _, ox, oy, _ = self.shapes[other]
                if abs(ox - x) <= 1 and abs(oy - y) <= 1:
                    close.append(j)

            near.append(close)

        self.neighbours[length] = near

    def gene_count(self):
        return len(self.ships)

    def gene_range(self, index):
        return len(self.placements[self.ships[index]])

    def placement_id(self, index, gene):
        return self.placements[self.ships[index]][gene]

    def decode(self, genes):
        return [self.shapes[self.placement_id(i, gene)] for i, gene in enumerate(genes)]

    def pair_counts(self, first, second):
        key = (first, second) if first < second else (second, first)

        if key in self.pair_cache:
            return self.pair_cache[key]

        overlap = 0
        touch = 0

        for a in self.cells[first]:
            for b in self.cells[second]:
                if a == b:
                    overlap += 1
                elif abs(a[0] - b[0]) <= 1 and abs(a[1] - b[1]) <= 1:
                    touch += 1

        self.pair_cache[key] = (overlap, touch)
        return overlap, touch

    def counts(self, genes):
        ids = [self.placement_id(i, gene) for i, gene in enumerate(genes)]

        overlap = 0
        touch = 0

        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                o, t = self.pair_counts(ids[i], ids[j])
                overlap += o
                touch += t

        return {"out_of_field": 0, "on_reef": 0, "overlap": overlap, "touch": touch}

    def fitness(self, genes):
        return fitness_from_counts(self.counts(genes))


def fitness_from_counts(counts):
    return -(W_OUT * counts["out_of_field"] + W_REEF * counts["on_reef"]
             + W_OVERLAP * counts["overlap"] + W_TOUCH * counts["touch"])


def check_layout(size, reefs, layout):
    reefs = set(reefs)
    cells = [ship_cells(*shape) for shape in layout]

    counts = {"out_of_field": 0, "on_reef": 0, "overlap": 0, "touch": 0}
    bad = set()

    for own in cells:
        for x, y in own:
            if not (0 <= x < size and 0 <= y < size):
                counts["out_of_field"] += 1
            elif (x, y) in reefs:
                counts["on_reef"] += 1
                bad.add((x, y))

    for i in range(len(cells)):
        for j in range(i + 1, len(cells)):
            for a in cells[i]:
                for b in cells[j]:
                    if a == b:
                        counts["overlap"] += 1
                        bad.add(a)
                    elif abs(a[0] - b[0]) <= 1 and abs(a[1] - b[1]) <= 1:
                        counts["touch"] += 1
                        bad.add(a)
                        bad.add(b)

    return counts, bad


def load_variant(path):
    with io.open(path, encoding="utf-8") as handle:
        try:
            data = json.load(handle)
        except ValueError as error:
            raise ValueError("Файл не є коректним JSON: %s" % error)

    problems = check_data(data)
    if problems:
        raise ValueError("\n".join(problems))

    reefs = [tuple(reef) for reef in data["reefs"]]
    name = os.path.basename(path)

    return Variant(data["field_size"], data["ships"], reefs, name)


def describe(variant, genes, fitness=None):
    layout = variant.decode(genes)
    counts, _ = check_layout(variant.size, variant.reefs, layout)

    if fitness is None:
        fitness = fitness_from_counts(counts)

    lines = []
    lines.append("%-4s %-8s %-14s %s" % ("№", "довжина", "перша клітинка", "орієнтація"))

    for index, (length, x, y, orientation) in enumerate(layout):
        name = ORIENTATION_NAMES[orientation] if length > 1 else "— (1 клітинка)"
        start = "(%d, %d)" % (x, y)
        lines.append("%-4d %-8d %-14s %s" % (index + 1, length, start, name))

    lines.append("")
    lines.append("Фітнес F = %g" % fitness)

    if fitness == 0:
        lines.append("Розстановка правильна: усі правила виконано.")
    else:
        lines.append("Правильну розстановку не знайдено. Порушені правила:")
        for key in ("out_of_field", "on_reef", "overlap", "touch"):
            if counts[key]:
                lines.append("  %s — %d" % (RULE_NAMES[key], counts[key]))

    return "\n".join(lines)
