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
    # --- Stage 4: billing / subscription ---
    "Pricing": ("Тарифы", "Precios", "定价"),
    "Pricing · Freemium": ("Тарифы · Freemium", "Precios · Freemium", "定价 · Freemium"),
    "Simple plans that grow with you": (
        "Простые тарифы, которые растут вместе с вами",
        "Planes simples que crecen contigo",
        "随你成长的简单方案",
    ),
    "Start free. Upgrade when you want deeper analytics and exports.": (
        "Начните бесплатно. Перейдите на Pro, когда нужна глубокая аналитика и экспорт.",
        "Empieza gratis. Mejora cuando quieras análisis y exportaciones avanzados.",
        "免费开始。需要更深入的分析和导出时再升级。",
    ),
    "Free": ("Бесплатно", "Gratis", "免费"),
    "/ forever": ("/ навсегда", "/ para siempre", "/ 永久"),
    "1 portfolio": ("1 портфель", "1 cartera", "1 个投资组合"),
    "Manual trade entry": ("Ручной ввод сделок", "Entrada manual de operaciones", "手动录入交易"),
    "Core charts & positions": ("Базовые графики и позиции", "Gráficos y posiciones básicos", "核心图表与持仓"),
    "Core charts": ("Базовые графики", "Gráficos básicos", "核心图表"),
    "Delayed quotes": ("Котировки с задержкой", "Cotizaciones con retraso", "延迟报价"),
    "Go to app": ("Перейти в приложение", "Ir a la app", "进入应用"),
    "Pro": ("Pro", "Pro", "Pro"),
    "Popular": ("Популярный", "Popular", "热门"),
    "/ month": ("/ месяц", "/ mes", "/ 月"),
    "Multiple portfolios": ("Несколько портфелей", "Múltiples carteras", "多个投资组合"),
    "Advanced analytics: risk, correlations, XIRR": (
        "Продвинутая аналитика: риск, корреляции, XIRR",
        "Análisis avanzado: riesgo, correlaciones, XIRR",
        "高级分析：风险、相关性、XIRR",
    ),
    "Advanced analytics & risk": (
        "Продвинутая аналитика и риск",
        "Análisis avanzado y riesgo",
        "高级分析与风险",
    ),
    "Excel / PDF export & yearly tax report": (
        "Экспорт в Excel/PDF и годовой налоговый отчёт",
        "Exportación a Excel/PDF e informe fiscal anual",
        "Excel/PDF 导出与年度税务报告",
    ),
    "Excel/PDF export & tax report": (
        "Экспорт в Excel/PDF и налоговый отчёт",
        "Exportación a Excel/PDF e informe fiscal",
        "Excel/PDF 导出与税务报告",
    ),
    "Event & price notifications": (
        "Уведомления о событиях и ценах",
        "Notificaciones de eventos y precios",
        "事件与价格通知",
    ),
    "Event notifications": ("Уведомления о событиях", "Notificaciones de eventos", "事件通知"),
    "Broker auto-import (later)": (
        "Автоимпорт от брокера (позже)",
        "Importación automática del bróker (más adelante)",
        "券商自动导入（稍后）",
    ),
    "Current plan": ("Текущий тариф", "Plan actual", "当前方案"),
    "Manage subscription": ("Управление подпиской", "Gestionar suscripción", "管理订阅"),
    "Upgrade to Pro": ("Перейти на Pro", "Cambiar a Pro", "升级到 Pro"),
    "Upgrade for more portfolios": (
        "Перейдите на Pro для большего числа портфелей",
        "Mejora para más carteras",
        "升级以获得更多投资组合",
    ),
    "You've reached the Free plan limit. Upgrade to Pro for unlimited portfolios.": (
        "Вы достигли лимита бесплатного тарифа. Перейдите на Pro для неограниченных портфелей.",
        "Has alcanzado el límite del plan gratuito. Mejora a Pro para carteras ilimitadas.",
        "你已达到免费方案上限。升级到 Pro 即可拥有无限投资组合。",
    ),
    "Account": ("Аккаунт", "Cuenta", "账户"),
    "Subscription": ("Подписка", "Suscripción", "订阅"),
    "Subscription · Freemium": ("Подписка · Freemium", "Suscripción · Freemium", "订阅 · Freemium"),
    "Manage your plan and unlock multi-portfolio analytics.": (
        "Управляйте тарифом и откройте аналитику по нескольким портфелям.",
        "Gestiona tu plan y desbloquea el análisis de varias carteras.",
        "管理方案，解锁多投资组合分析。",
    ),
    "Active": ("Активна", "Activa", "已激活"),
    "Cancel your Pro subscription?": (
        "Отменить подписку Pro?",
        "¿Cancelar tu suscripción Pro?",
        "取消你的 Pro 订阅？",
    ),
    "Cancel subscription": ("Отменить подписку", "Cancelar suscripción", "取消订阅"),
    "Confirm payment · Freemium": (
        "Подтверждение оплаты · Freemium",
        "Confirmar pago · Freemium",
        "确认支付 · Freemium",
    ),
    "Test checkout": ("Тестовая оплата", "Pago de prueba", "测试结账"),
    "Cancel": ("Отмена", "Cancelar", "取消"),
    # --- Stage 5: tax report + export ---
    "Tax report": ("Налоговый отчёт", "Informe fiscal", "税务报告"),
    "Realized gains": ("Реализованная прибыль", "Ganancias realizadas", "已实现收益"),
    "Closed positions matched FIFO — proceeds minus cost, per currency.": (
        "Закрытые позиции по методу FIFO — выручка минус себестоимость, по валютам.",
        "Posiciones cerradas con FIFO — ingresos menos coste, por divisa.",
        "按 FIFO 匹配的已平仓——收入减成本，按货币分组。",
    ),
    "Export CSV": ("Экспорт CSV", "Exportar CSV", "导出 CSV"),
    "Export Excel": ("Экспорт Excel", "Exportar Excel", "导出 Excel"),
    "Back": ("Назад", "Volver", "返回"),
    "Realized gain": ("Реализованная прибыль", "Ganancia realizada", "已实现收益"),
    "Closed lots": ("Закрытые лоты", "Lotes cerrados", "已平仓批次"),
    "Acquired": ("Куплено", "Comprado", "买入"),
    "Disposed": ("Продано", "Vendido", "卖出"),
    "Cost": ("Себестоимость", "Coste", "成本"),
    "Proceeds": ("Выручка", "Ingresos", "收入"),
    "Gain": ("Прибыль", "Ganancia", "收益"),
    "Days": ("Дней", "Días", "天数"),
    "No realized gains yet": (
        "Реализованной прибыли пока нет",
        "Aún no hay ganancias realizadas",
        "暂无已实现收益",
    ),
    "Sell some holdings to see a realized-gains tax report here.": (
        "Продайте часть позиций, чтобы увидеть здесь налоговый отчёт.",
        "Vende algunas posiciones para ver aquí un informe fiscal.",
        "卖出部分持仓即可在此查看税务报告。",
    ),
    "Back to portfolio": ("Назад к портфелю", "Volver a la cartera", "返回投资组合"),
    "That's a Pro feature. Upgrade to unlock tax reports and exports.": (
        "Это функция Pro. Перейдите на Pro, чтобы открыть налоговые отчёты и экспорт.",
        "Es una función Pro. Mejora a Pro para desbloquear informes y exportaciones.",
        "这是 Pro 功能。升级到 Pro 即可使用税务报告和导出。",
    ),
    # --- Stage 5: notifications ---
    "Notifications": ("Уведомления", "Notificaciones", "通知"),
    "Mark all read": ("Отметить все прочитанными", "Marcar todo como leído", "全部标为已读"),
    "Preferences": ("Настройки", "Preferencias", "偏好设置"),
    "No notifications yet": ("Уведомлений пока нет", "Aún no hay notificaciones", "暂无通知"),
    "Portfolio digests and alerts will show up here.": (
        "Здесь появятся дайджесты и оповещения по портфелю.",
        "Aquí aparecerán resúmenes y alertas de tu cartera.",
        "投资组合摘要和提醒将显示在此处。",
    ),
    "Previous": ("Предыдущая", "Anterior", "上一页"),
    "Next": ("Следующая", "Siguiente", "下一页"),
    "Notification preferences": (
        "Настройки уведомлений",
        "Preferencias de notificaciones",
        "通知偏好",
    ),
    "Choose how you'd like to hear from us.": (
        "Выберите, как вам удобнее получать уведомления.",
        "Elige cómo prefieres que te contactemos.",
        "选择你希望接收通知的方式。",
    ),
    "Save": ("Сохранить", "Guardar", "保存"),
    "Preferences saved.": ("Настройки сохранены.", "Preferencias guardadas.", "偏好已保存。"),
    "Your portfolio digest": (
        "Дайджест по вашему портфелю",
        "Resumen de tu cartera",
        "你的投资组合摘要",
    ),
    "Email me portfolio digests & alerts": (
        "Присылать дайджесты и оповещения на email",
        "Enviarme resúmenes y alertas por correo",
        "通过邮件向我发送摘要和提醒",
    ),
    "Confirm your Pro upgrade": (
        "Подтвердите переход на Pro",
        "Confirma tu mejora a Pro",
        "确认升级到 Pro",
    ),
    "Pay & activate Pro (test)": (
        "Оплатить и активировать Pro (тест)",
        "Pagar y activar Pro (prueba)",
        "支付并激活 Pro（测试）",
    ),
    "Your Free plan is limited to %(limit)s portfolio(s). Upgrade to Pro for "
    "unlimited portfolios.": (
        "Бесплатный тариф ограничен %(limit)s портфелем(ями). Перейдите на Pro "
        "для неограниченного числа портфелей.",
        "Tu plan gratuito está limitado a %(limit)s cartera(s). Mejora a Pro para "
        "carteras ilimitadas.",
        "免费方案限 %(limit)s 个投资组合。升级到 Pro 可拥有无限投资组合。",
    ),
    "Portfolio created.": ("Портфель создан.", "Cartera creada.", "投资组合已创建。"),
    "You're on Pro now — thank you!": (
        "Теперь у вас Pro — спасибо!",
        "Ya tienes Pro — ¡gracias!",
        "你已升级到 Pro——谢谢！",
    ),
    "Your subscription was cancelled.": (
        "Ваша подписка отменена.",
        "Tu suscripción ha sido cancelada.",
        "你的订阅已取消。",
    ),
    # --- Stage 3.5 fixes: auth pages (reset / verification) ---
    "Password reset": ("Сброс пароля", "Restablecer contraseña", "重置密码"),
    "Reset your password": ("Сбросьте пароль", "Restablece tu contraseña", "重置你的密码"),
    "Enter your email and we'll send reset instructions.": (
        "Введите email — мы отправим инструкции для сброса.",
        "Introduce tu email y te enviaremos instrucciones de restablecimiento.",
        "输入你的邮箱，我们会发送重置说明。",
    ),
    "Send reset email": ("Отправить письмо", "Enviar correo", "发送重置邮件"),
    "Back to log in": ("Назад ко входу", "Volver a iniciar sesión", "返回登录"),
    "Log out · Freemium": ("Выход · Freemium", "Cerrar sesión · Freemium", "退出 · Freemium"),
    "Are you sure you want to log out?": (
        "Вы уверены, что хотите выйти?",
        "¿Seguro que quieres cerrar sesión?",
        "确定要退出吗？",
    ),
    "Check your email · Freemium": (
        "Проверьте почту · Freemium",
        "Revisa tu correo · Freemium",
        "查收邮件 · Freemium",
    ),
    "Check your email": ("Проверьте почту", "Revisa tu correo", "查收邮件"),
    "Set a new password · Freemium": (
        "Новый пароль · Freemium",
        "Nueva contraseña · Freemium",
        "设置新密码 · Freemium",
    ),
    "Invalid link": ("Недействительная ссылка", "Enlace no válido", "链接无效"),
    "Set a new password": ("Установите новый пароль", "Establece una nueva contraseña", "设置新密码"),
    "Change password": ("Изменить пароль", "Cambiar contraseña", "修改密码"),
    "Password changed · Freemium": (
        "Пароль изменён · Freemium",
        "Contraseña cambiada · Freemium",
        "密码已修改 · Freemium",
    ),
    "Password changed": ("Пароль изменён", "Contraseña cambiada", "密码已修改"),
    "Your password has been changed. You can now log in.": (
        "Ваш пароль изменён. Теперь вы можете войти.",
        "Tu contraseña ha sido cambiada. Ya puedes iniciar sesión.",
        "你的密码已修改，现在可以登录了。",
    ),
    "Verify your email · Freemium": (
        "Подтвердите email · Freemium",
        "Verifica tu correo · Freemium",
        "验证邮箱 · Freemium",
    ),
    "Almost there": ("Почти готово", "Casi listo", "就差一步"),
    "Verify your email": ("Подтвердите email", "Verifica tu correo", "验证你的邮箱"),
    "Confirm email · Freemium": (
        "Подтверждение email · Freemium",
        "Confirmar correo · Freemium",
        "确认邮箱 · Freemium",
    ),
    "Confirm your email": ("Подтвердите ваш email", "Confirma tu correo", "确认你的邮箱"),
    "Confirm": ("Подтвердить", "Confirmar", "确认"),
    "This email is already confirmed by a different account.": (
        "Этот email уже подтверждён другим аккаунтом.",
        "Este correo ya está confirmado por otra cuenta.",
        "该邮箱已被另一个账户确认。",
    ),
    # --- blocktrans with variables (keep %(name)s placeholders intact) ---
    "We've sent you a link to reset your password. If it doesn't arrive in a few "
    "minutes, check your spam folder.": (
        "Мы отправили ссылку для сброса пароля. Если письмо не пришло за несколько "
        "минут, проверьте папку «Спам».",
        "Te hemos enviado un enlace para restablecer tu contraseña. Si no llega en "
        "unos minutos, revisa tu carpeta de spam.",
        "我们已向你发送重置密码的链接。如果几分钟内没有收到，请检查垃圾邮件箱。",
    ),
    "This password reset link is invalid or has already been used. Please "
    '<a href="%(reset_url)s">request a new one</a>.': (
        "Ссылка для сброса пароля недействительна или уже использована. "
        'Пожалуйста, <a href="%(reset_url)s">запросите новую</a>.',
        "El enlace de restablecimiento no es válido o ya se ha usado. "
        'Por favor, <a href="%(reset_url)s">solicita uno nuevo</a>.',
        '该重置密码链接无效或已被使用。请<a href="%(reset_url)s">重新申请</a>。',
    ),
    "We've sent you a verification link. Follow it to finish signing up. If it "
    "doesn't arrive in a few minutes, check your spam folder.": (
        "Мы отправили ссылку для подтверждения. Перейдите по ней, чтобы завершить "
        "регистрацию. Если письмо не пришло за несколько минут, проверьте папку «Спам».",
        "Te hemos enviado un enlace de verificación. Síguelo para terminar el "
        "registro. Si no llega en unos minutos, revisa tu carpeta de spam.",
        "我们已向你发送验证链接。点击它即可完成注册。如果几分钟内没有收到，请检查垃圾邮件箱。",
    ),
    "Confirm that %(email)s is your email address.": (
        "Подтвердите, что %(email)s — ваш адрес электронной почты.",
        "Confirma que %(email)s es tu dirección de correo.",
        "确认 %(email)s 是你的邮箱地址。",
    ),
    "This confirmation link expired or is invalid. Please "
    '<a href="%(email_url)s">request a new one</a>.': (
        "Ссылка для подтверждения недействительна или устарела. "
        'Пожалуйста, <a href="%(email_url)s">запросите новую</a>.',
        "El enlace de confirmación caducó o no es válido. "
        'Por favor, <a href="%(email_url)s">solicita uno nuevo</a>.',
        '该确认链接已过期或无效。请<a href="%(email_url)s">重新申请</a>。',
    ),
    "Renews / valid until %(date)s.": (
        "Продление / действует до %(date)s.",
        "Se renueva / válido hasta %(date)s.",
        "续订 / 有效期至 %(date)s。",
    ),
    "This is a simulated checkout (dev provider) — no real payment is taken. "
    "Amount: %(amount)s %(currency)s.": (
        "Это имитация оплаты (dev-провайдер) — реальные деньги не списываются. "
        "Сумма: %(amount)s %(currency)s.",
        "Este es un pago simulado (proveedor dev) — no se cobra dinero real. "
        "Importe: %(amount)s %(currency)s.",
        "这是模拟结账（dev 提供方）——不会真实扣款。金额：%(amount)s %(currency)s。",
    ),
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
    "%(count)s lot": (
        "%(count)s lots",
        {
            "ru": ("%(count)s лот", "%(count)s лота", "%(count)s лотов"),
            "es": ("%(count)s lote", "%(count)s lotes"),
            "zh_Hans": ("%(count)s 个批次",),
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
