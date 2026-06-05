#!/usr/bin/env python
"""Build .po + .mo catalogs without GNU gettext (Windows-friendly).

The standard ``makemessages``/``compilemessages`` need the GNU gettext binaries,
which aren't always installed on Windows. This script is the project's stand-in:
the source-of-truth translations live in ``TRANSLATIONS`` / ``PLURALS`` below and
it writes ``locale/<code>/LC_MESSAGES/django.po`` and ``.mo`` with polib.

Run from the project root:

    python bin/build_translations.py

To add a string: wrap it in {% trans %}/{% blocktrans %} (or _()), add its msgid
here with translations, and re-run. Keep msgids byte-identical to the templates
(blocktrans uses ``trimmed`` so multi-line text collapses to single spaces).
"""
from __future__ import annotations

import pathlib

import polib

LOCALE_DIR = pathlib.Path(__file__).resolve().parent.parent / "locale"
LANGS = ("ru", "es", "zh_Hans")

PLURAL_FORMS = {
    "ru": "nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && n%10<=4 && "
    "(n%100<12 || n%100>14) ? 1 : 2);",
    "es": "nplurals=2; plural=(n != 1);",
    "zh_Hans": "nplurals=1; plural=0;",
}

# msgid -> (ru, es, zh_Hans)
TRANSLATIONS: dict[str, tuple[str, str, str]] = {
    # --- base.html: nav / footer / controls ---
    "Skip to content": ("Перейти к содержимому", "Saltar al contenido", "跳到内容"),
    "Main navigation": ("Основная навигация", "Navegación principal", "主导航"),
    "Portfolios": ("Портфели", "Carteras", "投资组合"),
    "Log in": ("Войти", "Iniciar sesión", "登录"),
    "Get started": ("Начать", "Empezar", "开始使用"),
    "Language": ("Язык", "Idioma", "语言"),
    "Toggle dark theme": ("Переключить тёмную тему", "Cambiar tema oscuro", "切换深色主题"),
    "Log out": ("Выйти", "Cerrar sesión", "退出"),
    "Track. Analyse. Grow your portfolio.": (
        "Отслеживайте. Анализируйте. Растите портфель.",
        "Controla. Analiza. Haz crecer tu cartera.",
        "记录、分析、增长你的投资组合。",
    ),
    # --- language names (settings.LANGUAGES) ---
    "English": ("Английский", "Inglés", "英语"),
    "Russian": ("Русский", "Ruso", "俄语"),
    "Spanish": ("Испанский", "Español", "西班牙语"),
    "Simplified Chinese": ("Китайский (упрощённый)", "Chino simplificado", "简体中文"),
    # --- home.html ---
    "Freemium · Stop wrestling with spreadsheets": (
        "Freemium · Хватит мучиться с таблицами",
        "Freemium · Deja de pelear con hojas de cálculo",
        "Freemium · 告别繁琐的表格",
    ),
    "Personal investment tracker": (
        "Личный трекер инвестиций",
        "Rastreador de inversiones personal",
        "个人投资追踪器",
    ),
    "Your whole portfolio,<br>finally in one clear view.": (
        "Весь ваш портфель<br>наконец в одном понятном виде.",
        "Toda tu cartera,<br>por fin en una vista clara.",
        "你的整个投资组合，<br>终于一目了然。",
    ),
    "Log your trades, connect quotes from MOEX and global markets, and see real "
    "returns, allocation and risk — without another fragile Excel sheet.": (
        "Вносите сделки, подключайте котировки MOEX и мировых рынков и видьте "
        "реальную доходность, распределение и риск — без очередной хрупкой таблицы Excel.",
        "Registra tus operaciones, conecta cotizaciones de MOEX y los mercados "
        "globales, y observa rendimientos, distribución y riesgo reales — sin otra "
        "frágil hoja de Excel.",
        "记录交易，接入 MOEX 和全球市场的报价，查看真实的收益、配置与风险——"
        "无需再依赖脆弱的 Excel 表格。",
    ),
    "Go to my portfolios": ("Перейти к портфелям", "Ir a mis carteras", "前往我的投资组合"),
    "Create free account": ("Создать бесплатный аккаунт", "Crear cuenta gratis", "创建免费账户"),
    "Free plan: 1 portfolio, manual entry, core charts.": (
        "Бесплатный план: 1 портфель, ручной ввод, базовые графики.",
        "Plan gratuito: 1 cartera, entrada manual, gráficos básicos.",
        "免费方案：1 个投资组合、手动录入、基础图表。",
    ),
    "True returns": ("Реальная доходность", "Rendimientos reales", "真实收益"),
    "Time-weighted and money-weighted performance computed with exact decimal math.": (
        "Доходность, взвешенная по времени и по деньгам, с точными десятичными расчётами.",
        "Rendimiento ponderado por tiempo y por dinero, con cálculo decimal exacto.",
        "采用精确的十进制运算，计算时间加权和资金加权收益。",
    ),
    "Allocation & risk": ("Распределение и риск", "Distribución y riesgo", "配置与风险"),
    "Diversification by holding, asset class, market and currency — see "
    "concentration at a glance.": (
        "Диверсификация по позиции, классу актива, рынку и валюте — концентрация "
        "видна с первого взгляда.",
        "Diversificación por posición, clase de activo, mercado y divisa — observa "
        "la concentración de un vistazo.",
        "按持仓、资产类别、市场和货币进行分散——一眼看清集中度。",
    ),
    "Two markets": ("Два рынка", "Dos mercados", "两个市场"),
    "Russian (MOEX) and international tickers in one base-currency view.": (
        "Российские (MOEX) и зарубежные тикеры в одном виде в базовой валюте.",
        "Tickers rusos (MOEX) e internacionales en una vista en moneda base.",
        "俄罗斯（MOEX）和国际标的，统一以基准货币呈现。",
    ),
    "Own your data": ("Ваши данные — ваши", "Tus datos son tuyos", "数据归你所有"),
    "Manual entry first. Export to Excel/PDF and a yearly tax report on Pro.": (
        "Сначала ручной ввод. Экспорт в Excel/PDF и годовой налоговый отчёт в Pro.",
        "Primero entrada manual. Exporta a Excel/PDF e informe fiscal anual en Pro.",
        "先手动录入。Pro 版支持导出 Excel/PDF 和年度税务报告。",
    ),
    # --- signup.html ---
    "Create account · Freemium": ("Создать аккаунт · Freemium", "Crear cuenta · Freemium", "创建账户 · Freemium"),
    "Start tracking your portfolio — free.": (
        "Начните отслеживать портфель — бесплатно.",
        "Empieza a seguir tu cartera — gratis.",
        "开始追踪你的投资组合——免费。",
    ),
    "Stop wrestling with spreadsheets. Log your trades and see real value, "
    "returns and allocation across Russian and global markets.": (
        "Хватит мучиться с таблицами. Вносите сделки и видьте реальную стоимость, "
        "доходность и распределение по российским и мировым рынкам.",
        "Deja de pelear con hojas de cálculo. Registra tus operaciones y observa "
        "el valor, los rendimientos y la distribución reales en los mercados ruso y globales.",
        "告别繁琐的表格。记录交易，查看俄罗斯及全球市场的真实价值、收益与配置。",
    ),
    "1 portfolio, unlimited manual trades": (
        "1 портфель, неограниченный ручной ввод сделок",
        "1 cartera, operaciones manuales ilimitadas",
        "1 个投资组合，无限手动交易",
    ),
    "Live MOEX & international quotes": (
        "Котировки MOEX и международные в реальном времени",
        "Cotizaciones de MOEX e internacionales en vivo",
        "MOEX 与国际实时报价",
    ),
    "Allocation, returns & money-weighted XIRR": (
        "Распределение, доходность и XIRR (взвешенная по деньгам)",
        "Distribución, rendimientos y XIRR ponderada por dinero",
        "配置、收益与资金加权 XIRR",
    ),
    "No card required": ("Карта не нужна", "Sin tarjeta", "无需绑卡"),
    "Create your account": ("Создайте аккаунт", "Crea tu cuenta", "创建你的账户"),
    "Create account": ("Создать аккаунт", "Crear cuenta", "创建账户"),
    "Already have an account?": ("Уже есть аккаунт?", "¿Ya tienes una cuenta?", "已有账户？"),
    # --- login.html ---
    "Log in · Freemium": ("Войти · Freemium", "Iniciar sesión · Freemium", "登录 · Freemium"),
    "Forgot password?": ("Забыли пароль?", "¿Olvidaste tu contraseña?", "忘记密码？"),
    "New here?": ("Впервые здесь?", "¿Nuevo por aquí?", "第一次来？"),
    "Create an account": ("Создать аккаунт", "Crear una cuenta", "创建账户"),
    # --- portfolio_list.html ---
    "Portfolios · Freemium": ("Портфели · Freemium", "Carteras · Freemium", "投资组合 · Freemium"),
    "Your account": ("Ваш аккаунт", "Tu cuenta", "你的账户"),
    "Track your investments and log trades by hand.": (
        "Отслеживайте инвестиции и вносите сделки вручную.",
        "Sigue tus inversiones y registra operaciones a mano.",
        "追踪你的投资，手动记录交易。",
    ),
    "+ New portfolio": ("+ Новый портфель", "+ Nueva cartera", "+ 新建投资组合"),
    "Total value": ("Общая стоимость", "Valor total", "总价值"),
    "Invested (cost basis)": ("Вложено (себестоимость)", "Invertido (coste)", "投入（成本）"),
    "Unrealised P&L": ("Нереализованная прибыль/убыток", "P&L no realizado", "未实现盈亏"),
    "Return": ("Доходность", "Rendimiento", "收益率"),
    "market value": ("рыночная стоимость", "valor de mercado", "市值"),
    "invested · add prices to value": (
        "вложено · добавьте цены для оценки",
        "invertido · añade precios para valorar",
        "已投入 · 添加价格以估值",
    ),
    "no trades yet": ("сделок пока нет", "aún sin operaciones", "尚无交易"),
    "No portfolios yet": ("Портфелей пока нет", "Aún no hay carteras", "还没有投资组合"),
    "Create your first portfolio to stop wrestling with spreadsheets.": (
        "Создайте первый портфель, чтобы перестать мучиться с таблицами.",
        "Crea tu primera cartera y deja de pelear con hojas de cálculo.",
        "创建你的第一个投资组合，告别繁琐的表格。",
    ),
    "Create a portfolio": ("Создать портфель", "Crear una cartera", "创建投资组合"),
    "Browse the asset catalogue →": (
        "Открыть каталог активов →",
        "Explorar el catálogo de activos →",
        "浏览资产目录 →",
    ),
    # --- portfolio_detail.html ---
    "Portfolio": ("Портфель", "Cartera", "投资组合"),
    "+ Add trade": ("+ Добавить сделку", "+ Añadir operación", "+ 添加交易"),
    "↻ Refresh prices": ("↻ Обновить цены", "↻ Actualizar precios", "↻ 刷新价格"),
    "Edit": ("Изменить", "Editar", "编辑"),
    "Delete": ("Удалить", "Eliminar", "删除"),
    "Market value": ("Рыночная стоимость", "Valor de mercado", "市值"),
    "Return · XIRR": ("Доходность · XIRR", "Rendimiento · XIRR", "收益率 · XIRR"),
    "Allocation": ("Распределение", "Distribución", "配置"),
    "by market value": ("по рыночной стоимости", "por valor de mercado", "按市值"),
    "by invested capital": ("по вложенному капиталу", "por capital invertido", "按投入资金"),
    "Invested capital over time": (
        "Вложенный капитал во времени",
        "Capital invertido a lo largo del tiempo",
        "投入资金随时间变化",
    ),
    "Cumulative invested capital over time": (
        "Накопленный вложенный капитал во времени",
        "Capital invertido acumulado a lo largo del tiempo",
        "累计投入资金随时间变化",
    ),
    "Positions": ("Позиции", "Posiciones", "持仓"),
    "Asset": ("Актив", "Activo", "资产"),
    "Market": ("Рынок", "Mercado", "市场"),
    "Quantity": ("Количество", "Cantidad", "数量"),
    "Avg cost": ("Средняя цена", "Coste medio", "平均成本"),
    "Price": ("Цена", "Precio", "价格"),
    "P&L": ("Прибыль/убыток", "P&L", "盈亏"),
    "No open positions": ("Нет открытых позиций", "Sin posiciones abiertas", "没有持仓"),
    "Add a buy trade to see your positions here.": (
        "Добавьте сделку покупки, чтобы увидеть позиции здесь.",
        "Añade una operación de compra para ver tus posiciones aquí.",
        "添加一笔买入交易即可在此查看持仓。",
    ),
    "Add a trade": ("Добавить сделку", "Añadir operación", "添加交易"),
    "Recent transactions": ("Последние сделки", "Operaciones recientes", "近期交易"),
    "Date": ("Дата", "Fecha", "日期"),
    "Type": ("Тип", "Tipo", "类型"),
    "Qty": ("Кол-во", "Cant.", "数量"),
    "Fee": ("Комиссия", "Comisión", "费用"),
    "edit": ("изменить", "editar", "编辑"),
    "delete": ("удалить", "eliminar", "删除"),
    "No transactions logged yet.": (
        "Сделок пока не внесено.",
        "Aún no se han registrado operaciones.",
        "尚未记录任何交易。",
    ),
    # --- views.py allocation axis titles ---
    "By holding": ("По позициям", "Por posición", "按持仓"),
    "By asset class": ("По классу активов", "Por clase de activo", "按资产类别"),
    "By market": ("По рынку", "Por mercado", "按市场"),
    "By currency": ("По валюте", "Por divisa", "按货币"),
    # --- blocktrans with variables (keep %(name)s placeholders intact) ---
    "XIRR %(x)s": ("XIRR %(x)s", "XIRR %(x)s", "XIRR %(x)s"),
    "Base-currency totals need FX rates for: %(cur)s. Per-asset figures below are "
    "exact in each asset's own currency.": (
        "Итоги в базовой валюте требуют курсов для: %(cur)s. Показатели по активам "
        "ниже точны в собственной валюте каждого актива.",
        "Los totales en moneda base necesitan tipos de cambio para: %(cur)s. Las "
        "cifras por activo más abajo son exactas en la moneda de cada activo.",
        "基准货币合计需要以下货币的汇率：%(cur)s。下方各资产数字以各自货币计算，精确无误。",
    ),
    "Allocation excludes positions in %(cur)s — no FX rate to %(base)s yet.": (
        "Распределение исключает позиции в %(cur)s — пока нет курса к %(base)s.",
        "La distribución excluye posiciones en %(cur)s — aún sin tipo de cambio a %(base)s.",
        "配置已排除 %(cur)s 计价的持仓——尚无到 %(base)s 的汇率。",
    ),
    "Prices as of %(d)s UTC.": (
        "Цены на %(d)s UTC.",
        "Precios al %(d)s UTC.",
        "价格截至 %(d)s UTC。",
    ),
    "No quote yet for: %(tickers)s — click <strong>Refresh prices</strong> to fetch.": (
        "Пока нет котировки для: %(tickers)s — нажмите <strong>Обновить цены</strong>.",
        "Aún sin cotización para: %(tickers)s — pulsa <strong>Actualizar precios</strong>.",
        "尚无报价：%(tickers)s——点击<strong>刷新价格</strong>获取。",
    ),
}

# msgid -> (msgid_plural, {lang: (form0, form1, form2...)})
PLURALS: dict[str, tuple[str, dict[str, tuple[str, ...]]]] = {
    "%(count)s portfolio": (
        "%(count)s portfolios",
        {
            "ru": ("%(count)s портфель", "%(count)s портфеля", "%(count)s портфелей"),
            "es": ("%(count)s cartera", "%(count)s carteras"),
            "zh_Hans": ("%(count)s 个投资组合",),
        },
    ),
    "%(count)s trade": (
        "%(count)s trades",
        {
            "ru": ("%(count)s сделка", "%(count)s сделки", "%(count)s сделок"),
            "es": ("%(count)s operación", "%(count)s operaciones"),
            "zh_Hans": ("%(count)s 笔交易",),
        },
    ),
}


def build_catalog(lang: str) -> None:
    idx = LANGS.index(lang)
    po = polib.POFile(check_for_duplicates=True)
    po.metadata = {
        "Project-Id-Version": "freemium 0.1",
        "Report-Msgid-Bugs-To": "",
        "MIME-Version": "1.0",
        "Content-Type": "text/plain; charset=utf-8",
        "Content-Transfer-Encoding": "8bit",
        "Language": lang.replace("_", "-"),
        "Plural-Forms": PLURAL_FORMS[lang],
    }

    for msgid, forms in TRANSLATIONS.items():
        po.append(polib.POEntry(msgid=msgid, msgstr=forms[idx]))

    for msgid, (plural, by_lang) in PLURALS.items():
        po.append(
            polib.POEntry(
                msgid=msgid,
                msgid_plural=plural,
                msgstr_plural=dict(enumerate(by_lang[lang])),
            )
        )

    out_dir = LOCALE_DIR / lang / "LC_MESSAGES"
    out_dir.mkdir(parents=True, exist_ok=True)
    po.save(str(out_dir / "django.po"))
    po.save_as_mofile(str(out_dir / "django.mo"))
    print(f"  {lang}: {len(po)} entries -> {out_dir}")


def main() -> None:
    print(f"Building catalogs in {LOCALE_DIR}")
    for lang in LANGS:
        build_catalog(lang)
    print("Done.")


if __name__ == "__main__":
    main()
