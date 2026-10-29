import sys
import time

import fleet_core as core
import fleet_ga as ga
import fleet_sa as sa

POPULATION_VALUES = [20, 50, 100, 200]
MUTATION_VALUES = [0.02, 0.1, 0.2, 0.4]
ALPHA_VALUES = [0.8, 0.9, 0.95, 0.99]

STUDY_RUNS = 10
COMPARE_RUNS = 10


def mean(values):
    return sum(values) / len(values) if values else None


def run_ga(variant, params, seed):
    started = time.perf_counter()

    algorithm = ga.GeneticAlgorithm(variant, params, seed)
    algorithm.run()

    elapsed = time.perf_counter() - started

    return {
        "success": algorithm.success,
        "steps": algorithm.solved_generation if algorithm.success else algorithm.generation,
        "evaluations": (algorithm.solved_evaluations if algorithm.success
                        else algorithm.evaluations),
        "time": elapsed,
        "best": algorithm.best_fitness,
    }


def run_sa(variant, params, seed):
    started = time.perf_counter()

    algorithm = sa.SimulatedAnnealing(variant, params, seed)
    algorithm.run()

    elapsed = time.perf_counter() - started

    return {
        "success": algorithm.success,
        "steps": algorithm.solved_level if algorithm.success else algorithm.level,
        "evaluations": (algorithm.solved_evaluations if algorithm.success
                        else algorithm.evaluations),
        "time": elapsed,
        "best": algorithm.best_fitness(),
    }


def summary(results):
    good = [result for result in results if result["success"]]

    return {
        "runs": len(results),
        "success": len(good),
        "share": len(good) / len(results) if results else 0.0,
        "steps": mean([result["steps"] for result in good]),
        "evaluations": mean([result["evaluations"] for result in good]),
        "time": mean([result["time"] for result in results]),
        "best": mean([result["best"] for result in results]),
    }


def study(variant, runner, base, attribute, values, runs, progress=None, done=0, total=0,
          title="", should_stop=None):
    rows = []

    for value in values:
        params = base.copy()
        setattr(params, attribute, value)

        results = []
        for seed in range(runs):
            if should_stop is not None and should_stop():
                return rows, done

            results.append(runner(variant, params, seed))
            done += 1

            if progress is not None:
                progress(done, total, "%s = %s, запуск %d/%d" % (title, value, seed + 1, runs))

        rows.append((value, summary(results)))

    return rows, done


def compare(variant, ga_params, sa_params, runs, progress=None, done=0, total=0,
            should_stop=None):
    rows = []

    for name, runner, params in (("ГА", run_ga, ga_params), ("SA", run_sa, sa_params)):
        results = []

        for seed in range(runs):
            if should_stop is not None and should_stop():
                return rows, done

            results.append(runner(variant, params, seed))
            done += 1

            if progress is not None:
                progress(done, total, "%s, запуск %d/%d" % (name, seed + 1, runs))

        rows.append((name, summary(results)))

    return rows, done


def run_all(variant, ga_params, sa_params, population_values=None, mutation_values=None,
            alpha_values=None, study_runs=STUDY_RUNS, compare_runs=COMPARE_RUNS,
            progress=None, should_stop=None):
    population_values = population_values or POPULATION_VALUES
    mutation_values = mutation_values or MUTATION_VALUES
    alpha_values = alpha_values or ALPHA_VALUES

    total = (study_runs * (len(population_values) + len(mutation_values) + len(alpha_values))
             + 2 * compare_runs)
    done = 0

    report = {}

    report["population"], done = study(variant, run_ga, ga_params, "population",
                                       population_values, study_runs, progress, done, total,
                                       "M", should_stop)
    report["mutation"], done = study(variant, run_ga, ga_params, "pm", mutation_values,
                                     study_runs, progress, done, total, "pm", should_stop)
    report["alpha"], done = study(variant, run_sa, sa_params, "alpha", alpha_values,
                                  study_runs, progress, done, total, "alpha", should_stop)
    report["compare"], done = compare(variant, ga_params, sa_params, compare_runs, progress,
                                      done, total, should_stop)

    return report


def number(value, pattern):
    return "—" if value is None else pattern % value


def study_table(rows, label, steps_label, evaluations_label):
    header = [label, "успішних", "частка, %", steps_label, evaluations_label,
              "сер. час, с"]
    lines = [header]

    for value, item in rows:
        lines.append([
            str(value),
            "%d/%d" % (item["success"], item["runs"]),
            "%.0f" % (100.0 * item["share"]),
            number(item["steps"], "%.1f"),
            number(item["evaluations"], "%.0f"),
            number(item["time"], "%.3f"),
        ])

    return lines


def compare_table(rows):
    header = ["алгоритм", "успішних", "частка, %", "сер. час, с",
              "сер. обчислень F (E)", "сер. поколінь / ступенів T"]
    lines = [header]

    for name, item in rows:
        lines.append([
            name,
            "%d/%d" % (item["success"], item["runs"]),
            "%.0f" % (100.0 * item["share"]),
            number(item["time"], "%.3f"),
            number(item["evaluations"], "%.0f"),
            number(item["steps"], "%.1f"),
        ])

    return lines


def tables(report):
    return [
        ("Вплив розміру популяції M (ГА)",
         study_table(report.get("population", []), "M", "сер. поколінь",
                     "сер. обчислень F")),
        ("Вплив ймовірності мутації pm (ГА)",
         study_table(report.get("mutation", []), "pm", "сер. поколінь",
                     "сер. обчислень F")),
        ("Вплив швидкості охолодження alpha (SA)",
         study_table(report.get("alpha", []), "alpha", "сер. ступенів T",
                     "сер. обчислень E")),
        ("Порівняння ГА та SA", compare_table(report.get("compare", []))),
    ]


def format_table(lines):
    widths = [max(len(line[column]) for line in lines) for column in range(len(lines[0]))]
    text = []

    for index, line in enumerate(lines):
        text.append("  ".join(cell.ljust(widths[column]) for column, cell in enumerate(line)))
        if index == 0:
            text.append("  ".join("-" * width for width in widths))

    return "\n".join(text)


def tab_separated(report):
    blocks = []

    for title, lines in tables(report):
        blocks.append(title)
        blocks.extend("\t".join(line) for line in lines)
        blocks.append("")

    return "\n".join(blocks)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "variant05.json"
    variant = core.load_variant(path)

    def progress(done, total, text):
        sys.stdout.write("\r[%3d/%3d] %-40s" % (done, total, text))
        sys.stdout.flush()

    report = run_all(variant, ga.GAParams(), sa.SAParams(), progress=progress)
    sys.stdout.write("\n\n")

    print("Варіант: %s, поле %dx%d, кораблі %s, рифів %d\n"
          % (variant.name, variant.size, variant.size, variant.ships, len(variant.reefs)))

    for title, lines in tables(report):
        print(title)
        print(format_table(lines))
        print()


if __name__ == "__main__":
    main()
