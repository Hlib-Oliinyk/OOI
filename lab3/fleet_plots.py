from matplotlib.patches import Rectangle
from matplotlib.ticker import MaxNLocator

import fleet_core as core


def draw_field(axes, variant, genes=None, fitness=None):
    axes.clear()

    size = variant.size
    layout = variant.decode(genes) if genes is not None else []
    counts, bad = core.check_layout(size, variant.reefs, layout)

    owners = {}
    for number, shape in enumerate(layout, 1):
        for cell in core.ship_cells(*shape):
            owners.setdefault(cell, []).append(number)

    font = max(6, 13 - size // 2)

    for y in range(size):
        for x in range(size):
            cell = (x, y)

            if cell in owners:
                color = "#d62728" if cell in bad else "#000080"
            elif cell in variant.reefs:
                color = "#a0522d"
            else:
                color = "#add8e6"

            axes.add_patch(Rectangle((x - 0.5, y - 0.5), 1, 1, facecolor=color,
                                     edgecolor="white", linewidth=1.2))

            if cell in owners:
                axes.text(x, y, "/".join(str(n) for n in owners[cell]), color="white",
                          ha="center", va="center", fontsize=font, fontweight="bold")

    axes.set_xlim(-0.5, size - 0.5)
    axes.set_ylim(size - 0.5, -0.5)
    axes.set_xticks(range(size))
    axes.set_yticks(range(size))
    axes.set_aspect("equal")
    axes.tick_params(length=0)

    for side in axes.spines.values():
        side.set_visible(False)

    if genes is None:
        axes.set_title("%s: поле %dx%d, рифів %d"
                       % (variant.name, size, size, len(variant.reefs)), fontsize=10)
        return

    if fitness is None:
        fitness = core.fitness_from_counts(counts)

    axes.set_title("fitness = %g\nout_of_field=%d, on_reef=%d, overlap=%d, touch=%d"
                   % (fitness, counts["out_of_field"], counts["on_reef"],
                      counts["overlap"], counts["touch"]), fontsize=10)


def draw_ga_history(axes, best, mean):
    axes.clear()

    generations = list(range(len(best)))
    axes.plot(generations, best, color="#1f77b4", linewidth=1.6, label="найкращий")
    axes.plot(generations, mean, color="#ff7f0e", linewidth=1.4, linestyle="--",
              label="середній")

    axes.xaxis.set_major_locator(MaxNLocator(integer=True))
    axes.set_title("Еволюція fitness", fontsize=10)
    axes.set_xlabel("Покоління")
    axes.set_ylabel("Fitness")
    axes.grid(True, alpha=0.3)

    if best:
        axes.legend(loc="lower right", fontsize=8)


def draw_sa_history(energy_axes, temperature_axes, accepted_axes, levels, energies,
                    bests, temperatures, accepted):
    for axes in (energy_axes, temperature_axes, accepted_axes):
        axes.clear()
        axes.grid(True, alpha=0.3)
        axes.xaxis.set_major_locator(MaxNLocator(integer=True))

    energy_axes.plot(levels, energies, color="#ff7f0e", linewidth=1.2, label="поточна E")
    energy_axes.plot(levels, bests, color="#1f77b4", linewidth=1.6, label="найкраща E")
    energy_axes.set_title("Енергія E = -F", fontsize=9)
    energy_axes.set_ylabel("E")

    if levels:
        energy_axes.legend(loc="upper right", fontsize=7)

    temperature_axes.plot(levels, temperatures, color="#d62728", linewidth=1.4)
    temperature_axes.set_title("Температура T", fontsize=9)
    temperature_axes.set_ylabel("T")

    accepted_axes.plot(levels, accepted, color="#2ca02c", linewidth=1.4)
    accepted_axes.set_title("Частка прийнятих переходів", fontsize=9)
    accepted_axes.set_ylabel("частка")
    accepted_axes.set_ylim(-0.05, 1.05)
    accepted_axes.set_xlabel("Номер ступеня температури")


def bars(axes, labels, values, color, title, pattern):
    positions = list(range(len(labels)))
    heights = [0.0 if value is None else value for value in values]

    axes.bar(positions, heights, color=color, width=0.6)
    axes.set_xticks(positions)
    axes.set_xticklabels(labels)
    axes.set_title(title, fontsize=9)
    axes.grid(True, axis="y", alpha=0.3)

    top = max(heights) if heights else 0.0
    for position, value in zip(positions, values):
        text = "—" if value is None else pattern % value
        axes.text(position, (0.0 if value is None else value) + top * 0.02, text,
                  ha="center", va="bottom", fontsize=8)

    if top > 0:
        axes.set_ylim(0, top * 1.15)


def draw_study(figure, rows, label, steps_title):
    figure.clear()

    labels = [str(value) for value, _ in rows]
    shares = [100.0 * item["share"] for _, item in rows]
    steps = [item["steps"] for _, item in rows]
    evaluations = [item["evaluations"] for _, item in rows]

    first = figure.add_subplot(1, 3, 1)
    second = figure.add_subplot(1, 3, 2)
    third = figure.add_subplot(1, 3, 3)

    bars(first, labels, shares, "#2ca02c", "Частка успішних запусків, %", "%.0f")
    first.set_ylim(0, 115)
    bars(second, labels, steps, "#1f77b4", steps_title, "%.1f")
    bars(third, labels, evaluations, "#ff7f0e", "Сер. кількість обчислень фітнесу", "%.0f")

    for axes in (first, second, third):
        axes.set_xlabel(label)



def draw_compare(figure, rows):
    figure.clear()

    labels = [name for name, _ in rows]
    shares = [100.0 * item["share"] for _, item in rows]
    times = [None if item["time"] is None else 1000.0 * item["time"] for _, item in rows]
    evaluations = [item["evaluations"] for _, item in rows]

    first = figure.add_subplot(1, 3, 1)
    second = figure.add_subplot(1, 3, 2)
    third = figure.add_subplot(1, 3, 3)

    bars(first, labels, shares, "#2ca02c", "Частка успішних запусків, %", "%.0f")
    first.set_ylim(0, 115)
    bars(second, labels, times, "#9467bd", "Середній час роботи, мс", "%.1f")
    bars(third, labels, evaluations, "#ff7f0e", "Сер. кількість обчислень F (E)", "%.0f")

