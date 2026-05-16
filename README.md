# ⬡ IRONMARK — Hardware Benchmark

Нативный бенчмарк для Windows. Тестирует CPU, GPU, RAM и Storage и выдаёт единый балл от 0 до 10 000.

---

## Быстрый старт

### Запуск без сборки (через Python)
1. Установи Python 3.10+ → [python.org](https://python.org)
2. Дважды кликни `run.bat`

### Собрать .exe
1. Дважды кликни `build.bat`
2. Подожди 2–3 минуты
3. Готово — `IRONMARK.exe` появится в этой же папке

---

## Что тестируется

| Компонент | Методы                                          | Вес в итоге |
|-----------|-------------------------------------------------|-------------|
| CPU       | Решето Эратосфена, Float GEMM, Bitwise XOR, Multi-core | 35% |
| GPU       | OpenCL SGEMM + Bandwidth (если pyopencl) / Tier scoring + CPU proxy | 30% |
| RAM       | Sequential Read/Write 256 MB, Latency, Copy BW | 20% |
| Storage   | Sequential Read/Write 512 MB, Random 4K IOPS   | 15% |

### Оценки

| Балл       | Класс     | Описание                  |
|------------|-----------|---------------------------|
| 9000–10000 | S         | Flagship — топовое железо |
| 7500–8999  | A         | High-End                  |
| 6000–7499  | B         | Mid-High                  |
| 4500–5999  | C         | Midrange                  |
| 3000–4499  | D         | Entry Level               |
| 0–2999     | F         | Low-End                   |

---

## Реальный GPU тест (OpenCL)

По умолчанию GPU оценивается по базе данных видеокарт (tier scoring). Для реального теста прямо на GPU:

```
pip install pyopencl
```

После этого IRONMARK автоматически запустит OpenCL SGEMM и bandwidth тест на видеокарте.

---

## Структура файлов

```
📁 папка/
    ironmark.py        — основной код
    icon.ico           — иконка приложения
    build.bat          — сборка в .exe
    run.bat            — запуск через Python
    requirements.txt   — зависимости
    README.md          — этот файл
```

---

## Зависимости

```
customtkinter, numpy, psutil, gputil, pywin32, wmi
```

Устанавливаются автоматически через `build.bat` или `run.bat`.

Опционально: `pyopencl` — для реального GPU теста.

---

## Системные требования

- Windows 10 / 11 (64-bit)
- Python 3.10+ (только для запуска через `run.bat`)
- ~500 MB свободного места (для теста Storage)
