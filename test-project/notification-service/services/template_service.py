from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape

from notification_service.config.settings import settings

logger = logging.getLogger(__name__)

# Built-in default templates when files are not available
DEFAULT_TEMPLATES: dict[str, dict[str, str]] = {
    "workspace_invite": {
        "subject": "You've been invited to {{ workspace_name }}",
        "body": (
            "Hi {{ user_name }},\n\n"
            "{{ inviter_name }} has invited you to join the workspace "
            "'{{ workspace_name }}' with the role of {{ role }}.\n\n"
            "Click here to accept: {{ accept_url }}\n\n"
            "Best,\nThe Prism Team"
        ),
    },
    "password_reset": {
        "subject": "Reset your password",
        "body": (
            "Hi {{ user_name }},\n\n"
            "We received a request to reset your password. "
            "Click here to reset it: {{ reset_url }}\n\n"
            "If you didn't request this, you can safely ignore this email.\n\n"
            "Best,\nThe Prism Team"
        ),
    },
    "billing_alert": {
        "subject": "Billing alert for {{ tenant_name }}",
        "body": (
            "Hi {{ user_name }},\n\n"
            "Your usage for {{ tenant_name }} has reached {{ usage_percent }}% "
            "of your plan limit.\n\n"
            "Current usage: {{ current_usage }}\n"
            "Plan limit: {{ plan_limit }}\n\n"
            "Consider upgrading your plan to avoid service interruptions.\n\n"
            "Best,\nThe Prism Team"
        ),
    },
}


class TemplateService:
    """Renders notification templates using Jinja2."""

    def __init__(self, template_dir: str | None = None) -> None:
        self._template_dir = template_dir or settings.template_directory
        self._file_env: Environment | None = None
        self._string_env = Environment(autoescape=select_autoescape(["html"]))

        template_path = Path(self._template_dir)
        if template_path.is_dir():
            self._file_env = Environment(
                loader=FileSystemLoader(str(template_path)),
                autoescape=select_autoescape(["html", "xml"]),
            )
            logger.info("Loaded templates from %s", template_path)

    async def render_template(
        self,
        template_name: str,
        context: dict[str, Any],
    ) -> dict[str, str]:
        """Render a notification template with the given context.

        Returns a dict with 'subject' and 'body' keys.
        """
        # Try file-based templates first
        if self._file_env is not None:
            try:
                subject_template = self._file_env.get_template(
                    f"{template_name}_subject.txt"
                )
                body_template = self._file_env.get_template(
                    f"{template_name}_body.html"
                )
                return {
                    "subject": subject_template.render(**context),
                    "body": body_template.render(**context),
                }
            except TemplateNotFound:
                logger.debug(
                    "File template '%s' not found, falling back to defaults",
                    template_name,
                )

        # Fall back to built-in templates
        if template_name in DEFAULT_TEMPLATES:
            templates = DEFAULT_TEMPLATES[template_name]
            subject_tpl = self._string_env.from_string(templates["subject"])
            body_tpl = self._string_env.from_string(templates["body"])
            return {
                "subject": subject_tpl.render(**context),
                "body": body_tpl.render(**context),
            }

        logger.warning("Template '%s' not found, using raw values", template_name)
        return {
            "subject": context.get("subject", "Notification"),
            "body": context.get("body", ""),
        }

    def list_templates(self) -> list[str]:
        templates = list(DEFAULT_TEMPLATES.keys())
        if self._file_env and self._file_env.loader:
            try:
                file_templates = self._file_env.loader.list_templates()
                for ft in file_templates:
                    name = ft.rsplit("_", 1)[0] if "_" in ft else ft.split(".")[0]
                    if name not in templates:
                        templates.append(name)
            except Exception:
                pass
        return templates
