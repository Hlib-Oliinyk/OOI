import json
import math
import threading
import urllib.request

BASE_URL = "https://ooi-lab1.up.railway.app"


def fetch_json(path):
    for attempt in range(5):
        try:
            with urllib.request.urlopen(BASE_URL + path, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception:
            if attempt == 4:
                raise
    return None


def get_config():
    return fetch_json("/api/config")


def get_pulse():
    return fetch_json("/api/pulse")


def get_sensor(step):
    return fetch_json("/api/sensor?step=%d" % step)


def average_signals(signals):
    count = len(signals)
    length = len(signals[0])

    result = [0.0] * length

    for signal in signals:
        for i in range(length):
            result[i] += signal[i]

    for i in range(length):
        result[i] /= count

    return result


def cross_correlation(signal, template):
    n = len(signal)
    m = len(template)

    shifts = n - m + 1
    result = [0.0] * shifts

    for k in range(shifts):
        total = 0.0

        for j in range(m):
            total += signal[k + j] * template[j]

        result[k] = total

    return result


def pearson(a, b):
    n = len(a)

    mean_a = sum(a) / n
    mean_b = sum(b) / n

    num = 0.0
    sq_a = 0.0
    sq_b = 0.0

    for i in range(n):
        da = a[i] - mean_a
        db = b[i] - mean_b

        num += da * db

        sq_a += da * da
        sq_b += db * db

    denom = math.sqrt(sq_a * sq_b)
    if denom == 0.0:
        return 0.0

    return num / denom


def argmax(values):
    best_index = 0
    best_value = values[0]

    for i in range(1, len(values)):
        if values[i] > best_value:
            best_value = values[i]
            best_index = i

    return best_index, best_value


def mean(values):
    return sum(values) / len(values)


def rms(values):
    total = 0.0
    for value in values:
        total += value * value

    return math.sqrt(total / len(values))


def std(values):
    m = mean(values)
    total = 0.0

    for value in values:
        total += (value - m) ** 2

    return math.sqrt(total / len(values))


def shift_to_delay(k, sample_rate):
    return k / sample_rate


def shift_to_depth(k, sample_rate, sound_speed):
    return (k / sample_rate) * sound_speed / 2.0


def pulse_duration(template_length, sample_rate):
    return template_length / sample_rate


def depth_resolution(sample_rate, sound_speed):
    return shift_to_depth(1, sample_rate, sound_speed)


def max_measurable_depth(signal_length, template_length, sample_rate, sound_speed):
    return shift_to_depth(signal_length - template_length, sample_rate, sound_speed)


def multiplications_per_step(signal_length, template_length):
    return (signal_length - template_length + 1) * template_length


def measure_step(step, template, sample_rate, sound_speed, repeats=1):
    signals = [get_sensor(step) for _ in range(repeats)]
    signal = signals[0] if repeats == 1 else average_signals(signals)

    correlation = cross_correlation(signal, template)
    k_max, peak = argmax(correlation)
    background = rms(correlation)
    return {
        "step": step,
        "repeats": repeats,
        "signal": signal,
        "correlation": correlation,
        "k_max": k_max,
        "peak": peak,
        "snr": peak / background if background > 0 else 0.0,
        "noise": std(signal),
        "delay": shift_to_delay(k_max, sample_rate),
        "depth": shift_to_depth(k_max, sample_rate, sound_speed),
    }


def smoothness(depths):
    if len(depths) < 2:
        return 0.0

    total = 0.0
    for i in range(1, len(depths)):
        total += abs(depths[i] - depths[i - 1])

    return total / (len(depths) - 1)


def fetch_signals(step, count):
    if count == 1:
        return [get_sensor(step)]

    results = [None] * count
    errors = []

    def worker(index):
        try:
            results[index] = get_sensor(step)
        except Exception as error:
            errors.append(error)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    if errors:
        raise errors[0]

    return results


def analyse(signal, template, sample_rate, sound_speed):
    correlation = cross_correlation(signal, template)
    k_max, peak = argmax(correlation)
    background = rms(correlation)

    return {
        "signal": signal,
        "correlation": correlation,
        "k_max": k_max,
        "peak": peak,
        "snr": peak / background if background > 0 else 0.0,
        "noise": std(signal),
        "delay": shift_to_delay(k_max, sample_rate),
        "depth": shift_to_depth(k_max, sample_rate, sound_speed),
    }


def measure_pair(step, template, sample_rate, sound_speed, repeats):
    signals = fetch_signals(step, repeats)

    single = analyse(signals[0], template, sample_rate, sound_speed)
    single["step"] = step
    single["repeats"] = 1

    averaged = analyse(average_signals(signals), template, sample_rate, sound_speed)
    averaged["step"] = step
    averaged["repeats"] = repeats

    return single, averaged
