from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

from agentpost.config import Settings


class EmailDeliveryError(RuntimeError):
    pass


def _send_message(settings: Settings, message: EmailMessage) -> None:
    if settings.email_delivery_mode == "test":
        return
    if not settings.smtp_host or not settings.smtp_from_address:
        raise EmailDeliveryError("SMTP delivery is not configured")
    try:
        context = ssl.create_default_context()
        if settings.smtp_ssl:
            connection = smtplib.SMTP_SSL(
                settings.smtp_host,
                settings.smtp_port,
                timeout=10,
                context=context,
            )
        else:
            connection = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)
        with connection as client:
            if settings.smtp_starttls:
                client.starttls(context=context)
            if settings.smtp_username:
                password = (
                    settings.smtp_password.get_secret_value() if settings.smtp_password else ""
                )
                client.login(settings.smtp_username, password)
            client.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise EmailDeliveryError("Email could not be delivered") from exc


def deliver_verification_code(
    settings: Settings,
    *,
    email: str,
    code: str,
    purpose: str,
) -> None:
    if not settings.smtp_host or not settings.smtp_from_address:
        if settings.email_delivery_mode == "test":
            return
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
    _send_message(settings, message)


def deliver_organization_invitation(
    settings: Settings,
    *,
    email: str,
    organization_name: str,
    verification_uri: str,
) -> None:
    if not settings.smtp_host or not settings.smtp_from_address:
        if settings.email_delivery_mode == "test":
            return
        raise EmailDeliveryError("SMTP delivery is not configured")
    message = EmailMessage()
    message["Subject"] = f"邀请你加入星云驿组织：{organization_name}"
    message["From"] = settings.smtp_from_address
    message["To"] = email
    message.set_content(
        f"你被邀请加入星云驿中的“{organization_name}”。\n\n"
        f"请登录与你收到邀请相同的邮箱账户后打开：\n{verification_uri}\n\n"
        "邀请有时效且只能使用一次。若非本人预期，请忽略本邮件。"
    )
    _send_message(settings, message)
