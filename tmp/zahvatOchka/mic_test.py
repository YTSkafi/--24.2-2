import argparse
import sys
import wave
from datetime import datetime
from pathlib import Path


def record(sd, device_id, device, seconds, path):
    rate = round(device["default_samplerate"])
    remaining = rate * seconds
    with sd.RawInputStream(device=device_id, samplerate=rate, channels=1,
                           dtype="int16") as stream:
        with path.open("xb") as output, wave.open(output, "wb") as wav:
            wav.setparams((1, 2, rate, 0, "NONE", "not compressed"))
            print(f"Запись с «{device['name']}», {rate} Гц. Говорите.", flush=True)
            overflows = 0
            while remaining:
                count = min(max(1, rate // 10), remaining)
                block, overflow = stream.read(count)
                overflows += int(overflow)
                samples = memoryview(block).cast("h")
                peak = max(abs(sample) for sample in samples)
                wav.writeframesraw(b"".join(sample.to_bytes(2, "little", signed=True)
                                            for sample in samples)
                                   if sys.byteorder == "big" else block)
                remaining -= count
                print(f"\rПиковый уровень: {peak / 32768:5.0%}", end="", flush=True)
    print(f"\nЗапись сохранена: {path.resolve()}")
    if overflows:
        print(f"Блоков с потерей входных данных: {overflows}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="показать устройства записи")
    parser.add_argument("--device", type=int, help="номер устройства из списка")
    parser.add_argument("--seconds", type=int, default=5, help="длительность в секундах")
    parser.add_argument("--output", type=Path, help="путь для нового WAV-файла")
    args = parser.parse_args()
    if args.seconds <= 0:
        parser.error("--seconds должен быть положительным")
    try:
        import sounddevice as sd
    except (ImportError, OSError) as error:
        parser.exit(1, f"Для записи нужны sounddevice и PortAudio. {error}\n")

    try:
        inputs = {i: d for i, d in enumerate(sd.query_devices())
                  if d["max_input_channels"] > 0}
        if not inputs:
            parser.exit(1, "Устройства записи не найдены. Проверьте подключение микрофона.\n")
        device_id = args.device
        if args.list or device_id is None:
            for i, device in inputs.items():
                host = sd.query_hostapis(device["hostapi"])["name"]
                print(f"{i}: {device['name']} ({host})")
            if args.list:
                return
            device_id = int(input("Введите номер микрофона: "))
        if device_id not in inputs:
            parser.error("выберите номер устройства записи из списка --list")
        path = args.output or Path(datetime.now().strftime("mic_%Y%m%d_%H%M%S_%f.wav"))
        record(sd, device_id, inputs[device_id], args.seconds, path)
    except (sd.PortAudioError, OSError, ValueError, EOFError) as error:
        parser.exit(1, f"Ошибка проверки микрофона: {error}\n")
    except KeyboardInterrupt:
        parser.exit(130, "\nПроверка остановлена.\n")


if __name__ == "__main__":
    main()
