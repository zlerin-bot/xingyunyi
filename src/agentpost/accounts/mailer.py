from __future__ import annotations

import smtplib
from email.message import EmailMessage

from agentpost.config import Settings


class EmailDeliveryError(RuntimeError):
    pass


def deliver_verification_code(
    settings: Settings,
    *,
    email: str,
    code: str,
    purpose: str,
) -> None:
    if settings.email_delivery_mode == "test":
        return
    if not settings.smtp_host or not settings.smtp_from_address:
        raise EmailDeliveryError("SMTP delivery is not configured")
    message = EmailMessage()
    message["Subject"] = "星云驿邮箱验证码"
    message["From"] = settings.smtp_from_address
    message["To"] = email
    action = "注册" if purpose == "register" else "账户恢复"
    message.set_content(
        f"你正在进行星云驿{action}。验证码：{code}\n\n"
        "验证码将在短时间后失效。若非本人操作，请忽略本邮件。"
    )
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as client:
            if settings.smtp_starttls:
                client.starttls()
            if settings.smtp_username:
                password = (
                    settings.smtp_password.get_secret_value() if settings.smtp_password else ""
                )
                client.login(settings.smtp_username, password)
            client.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise EmailDeliveryError("Verification email could not be delivered") from exc
