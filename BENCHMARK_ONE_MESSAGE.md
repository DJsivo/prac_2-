# Бенчмарк: отправка одного сообщения между сервисами

## Последний измеренный результат (orders -> notification)

Параметры запуска:
- Сеть Docker: `lab2_logistics_lab2_network`
- Количество измерений на метод: `30`
- Прогрев на метод: `5`

| Method | Min (ms) | Avg (ms) | P95 (ms) | Max (ms) |
|---|---:|---:|---:|---:|
| http | 6.27 | 8.32 | 10.76 | 11.45 |
| msgpack | 6.18 | 7.99 | 10.47 | 10.58 |
| grpc | 5.29 | 7.08 | 9.94 | 10.75 |

Самый быстрый по средней задержке: `grpc (7.08 ms)`.

## Как запустить новый тест и сохранить результат в файл

```powershell
powershell -ExecutionPolicy Bypass -File tests/run_one_message_benchmark.ps1
```

Результат сохраняется в файл:

```text
reports/benchmarks/one_message_YYYYMMDD_HHMMSS.txt
```

## Формальный замер по требованиям ЛР (полная цепочка)

Для требования "100+ вызовов, средняя, дисперсия, график" используй:

```powershell
powershell -ExecutionPolicy Bypass -File tests/run_full_chain_benchmark.ps1
```

Будут сохранены:
- `reports/performance_fullchain/full_chain_samples_*.csv`
- `reports/performance_fullchain/full_chain_summary_*.txt`
- `reports/performance_fullchain/full_chain_plot_*.png`
