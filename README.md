# faktura-printer

[![CI](https://github.com/rstepanovs/faktura-printer/actions/workflows/ci.yml/badge.svg)](https://github.com/rstepanovs/faktura-printer/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/github/license/rstepanovs/faktura-printer)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)

Генератор счетов (Faktura) в PDF из JSON, повторяющий формат шведской faktura:
исполнитель, заказчик, логотип, позиции и итоги задаются во входном файле.

Суммы **не пересчитываются**: приложение печатает значения из JSON, проверяя только
структуру и типы.

Три способа использования: как **импортируемый модуль** в другом Python-проекте, как
**CLI**, как **HTTP API**. Все три — тонкие обёртки над одним и тем же публичным API
(`faktura_printer.render_pdf`).

## Установка

```bash
python3 -m venv .venv
.venv/bin/pip install -e .          # только библиотека (Invoice, render_pdf, ...)
.venv/bin/pip install -e '.[api]'   # + HTTP API (faktura-printer serve)
.venv/bin/pip install -e '.[dev]'   # + тесты (включает [api])
```

Для использования как зависимости из другого проекта — локальный путь или git,
пока репозиторий не выложен на GitHub:

```bash
pip install /path/to/faktura-printer          # или через git-URL после публикации
```

```toml
# pyproject.toml другого проекта
dependencies = ["faktura-printer @ file:///path/to/faktura-printer"]
```

WeasyPrint нужны системные библиотеки Pango/HarfBuzz (на Ubuntu обычно уже есть,
иначе `sudo apt install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0`).

## Использование как библиотека

```python
from pathlib import Path
from faktura_printer import Invoice, render_pdf

json_path = Path("invoice.json")
invoice = Invoice.model_validate_json(json_path.read_bytes())   # валидация + разбор
pdf_bytes = render_pdf(invoice, base_dir=json_path.parent)      # base_dir — где искать логотип
Path("out.pdf").write_bytes(pdf_bytes)
```

Публичный API (`from faktura_printer import ...`, стабильные имена, задокументированы
docstring'ами, пакет размечен как typed — `py.typed`):

| Имя | Описание |
|-----|----------|
| `Invoice`, `Seller`, `Buyer`, `Item`, `Totals`, `Address`, `Design` | pydantic-модели входных данных — см. «Формат JSON» ниже; можно строить программно, без JSON |
| `render_pdf(invoice, *, base_dir=None, untrusted=False)` | `Invoice` → PDF-байты |
| `render_html(invoice, *, base_dir=None, untrusted=False)` | `Invoice` → HTML-строка (для отладки вёрстки) |
| `InvoiceError` | подкласс `ValueError`: неизвестная локаль/тема, отсутствующий/неподдерживаемый логотип или файл дизайна |
| `available_locales()` | список кодов локалей, напр. `["en", "sv"]` |
| `available_themes()` | список встроенных тем, напр. `["classic", "modern"]` |
| `default_filename(invoice)` | имя файла по номеру счёта, напр. `"faktura_1138.pdf"` |

`base_dir` (`str` или `Path`) — где искать относительный `seller.logo`/`design.template`/
`design.css`; по умолчанию — текущая директория. `untrusted=True` — когда `Invoice` собран
из данных внешнего вызывающего, а не из локального файла, которому вы доверяете
(ограничения — в разделе «HTTP API» ниже, там же используется этот режим).

Полные сигнатуры и примеры — в docstring'ах (`help(faktura_printer.render_pdf)` или
IDE/type checker благодаря `py.typed`).

## CLI

```bash
# PDF рядом, имя по номеру счёта: faktura_1138.pdf
.venv/bin/faktura-printer examples/invoice_1138.json

# свой путь + промежуточный HTML для отладки вёрстки
.venv/bin/faktura-printer examples/invoice_1138.json -o out.pdf --html out.html

# JSON из stdin
cat invoice.json | .venv/bin/faktura-printer - -o out.pdf

# JSON-схема входных данных
.venv/bin/faktura-printer schema > invoice.schema.json
```

При ошибках в данных выводится список всех проблемных полей, код возврата `1`.

## HTTP API

Требует extra `[api]` (`pip install -e '.[api]'` или `'.[dev]'`).

```bash
.venv/bin/faktura-printer serve --host 127.0.0.1 --port 8000 --assets-dir assets/logos
```

| Метод | Путь        | Описание                                           |
|-------|-------------|----------------------------------------------------|
| POST  | `/invoices` | тело — invoice JSON, ответ — `application/pdf`     |
| GET   | `/health`   | `{"status": "ok"}`                                 |
| GET   | `/docs`     | Swagger UI                                         |

Ошибки валидации — `422` с описанием полей.

В API логотип (`seller.logo`) и файлы дизайна (`design.template`, `design.css`) задаются
только как `data:image/...;base64,...` (логотип) или как **имя файла** из каталога
`--assets-dir` (переменная `FAKTURA_ASSETS_DIR`). Встроенные темы (`design.theme`) доступны
без ограничений — они часть пакета, а не файлы на диске сервера. Другие файлы сервера и сеть
рендереру недоступны.

```bash
curl -X POST localhost:8000/invoices -H 'Content-Type: application/json' \
     -d "$(jq '.seller.logo = "beltandbraces.svg"' examples/invoice_1138.json)" -o faktura.pdf
```

## Формат JSON

Полный пример: `examples/invoice_1138.json`. Необязательные поля можно не указывать —
в счёте останется пустая ячейка.

| Поле | Обяз. | Описание |
|------|:-----:|----------|
| `locale` | | `sv` (по умолчанию) или `en` |
| `labels` | | переопределение отдельных подписей, напр. `{"title": "Kreditfaktura"}` |
| `design.theme` | | `classic` (по умолчанию) или `modern` — см. «Дизайн и темы» ниже |
| `design.template`, `design.css` | | путь к своему `.j2`/`.css`, полностью заменяющему встроенный |
| `seller.name` | ✓ | название компании (печатается вместо логотипа, если его нет) |
| `seller.logo` | | путь относительно JSON-файла или data URI; `.svg`, `.png`, `.jpg` |
| `seller.address` | ✓ | `care_of`, `street`, `postal_code`, `city`, `country` |
| `seller.phone`, `email`, `registered_office`, `bankgiro`, `iban`, `bic`, `org_number`, `vat_number` | | реквизиты в подвале |
| `seller.f_tax_approved` | | `true` → «Godkänd för F-skatt» |
| `buyer.name`, `buyer.address` | ✓ | заказчик |
| `invoice.number`, `date`, `due_date` | ✓ | даты в формате `YYYY-MM-DD` |
| `invoice.customer_number`, `payment_terms`, `late_interest`, `our_reference`, `your_reference`, `your_order_number`, `delivery_terms`, `delivery_method` | | |
| `items[]` | ✓ (≥1) | `article_number`, `description` ✓, `quantity`, `unit`, `unit_price`, `amount` ✓ |
| `totals` | ✓ | `net`, `excl_vat`, `vat_rate`, `vat_amount`, `total` |
| `notes` | | текст в рамке под таблицей |

**Числа.** Число в JSON (`138000.00`) форматируется по локали: `138 000,00` для `sv`,
`138,000.00` для `en`; количество и ставка НДС печатаются без лишних нулей.
Строка (`"по договору"`) выводится как есть.

## Логотип

Рекомендуемый формат — **SVG**: вектор, чёткий при печати и любом масштабе.
`assets/logos/beltandbraces.svg` получен из векторного `logo/Final file (PDF).pdf`:

```bash
pdftocairo -svg "logo/Final file (PDF).pdf" assets/logos/beltandbraces.svg
```

(затем `viewBox` обрезан по контуру рисунка, без белых полей). PNG тоже поддерживается;
EPS и PDF напрямую — нет, их нужно сконвертировать так же. Логотип вписывается в
область 62×32 мм.

## Дизайн и темы

Каждый счёт может выбрать свой дизайн — тема задаётся в самом JSON (`design.theme`),
так что один и тот же запущенный сервис рисует разным клиентам разное оформление,
ничего в коде менять не нужно.

**Встроенные темы** (`design.theme`, по умолчанию `classic`) — меняют только цвет/шрифты/
рамки, структура счёта (какие поля где стоят) одна на всех: `examples/invoice_modern_theme.json`
использует `"design": {"theme": "modern"}`. Список: `faktura_printer.available_themes()`.
Новая тема — это просто файл `src/faktura_printer/themes/<имя>.css`, скопируйте `classic.css`
или `modern.css` за основу.

**Свой шаблон и/или стили** (`design.template`, `design.css`) — путь к `.j2`/`.css`
резолвится так же, как `seller.logo` (относительно JSON-файла; в HTTP API — только имя
файла из `--assets-dir`). Каждый файл **полностью заменяет** встроенный, а не дополняет
его — если нужен свой файл, скопируйте `src/faktura_printer/themes/invoice.html.j2` и/или
CSS одной из тем как отправную точку:

```json
"design": { "template": "my_invoice.html.j2", "css": "my_invoice.css" }
```

Можно задать только `css` (оставив встроенную вёрстку) или только `template`
(унаследовав CSS темы, если ваш шаблон сам вставляет `{{ css }}` в `<style>`).

## Настройка

- Подписи и формат чисел/дат: `src/faktura_printer/locales/<код>.json`. Новый язык —
  новый файл с тем же набором ключей.
- Встроенные темы: `src/faktura_printer/themes/<имя>.css`; вёрстка — общий для всех тем
  `src/faktura_printer/themes/invoice.html.j2` (см. «Дизайн и темы» выше).

## Тесты

```bash
.venv/bin/pytest
```
