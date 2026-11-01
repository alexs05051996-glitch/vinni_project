"""Шаблоны сообщений бота."""


def start_help() -> str:
    return (
        "Привет! Я бот сервиса ВИННИ 🤖\n\n"
        "Чтобы привязать аккаунт, получите код в личном кабинете на сайте и отправьте:\n"
        "<code>/start ВАШ_КОД</code>"
    )


def link_success() -> str:
    return "✅ Аккаунт привязан! Теперь вы будете получать уведомления об окончании подписки."


def link_invalid() -> str:
    return "❌ Код недействителен или истёк. Получите новый код в личном кабинете."


def unlinked() -> str:
    return "Аккаунт отвязан. Уведомления больше не приходят."


def report_header(total: int) -> str:
    return f"📊 <b>Отчёт ВИННИ</b>\n\n👥 Всего пользователей в панели: {total}\n"


def top_traffic_header() -> str:
    return "\n🏆 <b>Топ-5 по трафику:</b>"


def top_traffic_line(idx: int, username: str, traffic: str) -> str:
    return f"{idx}. <code>{username}</code> — {traffic}"


def suspicious_header(count: int, threshold: int) -> str:
    return (
        f"\n🚨 <b>Подозрительные аккаунты: {count}</b>\n"
        f"Признак: более {threshold} уникальных IP за последние 24 часа."
    )


def suspicious_line(username: str, remnawave_id: int, unique_ips: int) -> str:
    return f"• <code>{username}</code> (id {remnawave_id}) — {unique_ips} IP"


def ban_ok(username: str, remnawave_id: int) -> str:
    return f"✅ Пользователь <code>{username}</code> (id {remnawave_id}) заблокирован (disable)."


def ban_error(reason: str) -> str:
    return f"⚠️ Не удалось забанить: {reason}"
