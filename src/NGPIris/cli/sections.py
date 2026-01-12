from collections.abc import Callable
from typing import Any

import click


class SectionedGroup(click.Group):
    """
    A click.Group that prints commands grouped into sections.
    """

    def format_commands(
        self,
        ctx : click.Context,
        formatter: click.HelpFormatter
    ) -> None:
        """
        Format commands such that commands are grouped in sections.
        """
        # Collect all visible commands
        commands = []
        for name in self.list_commands(ctx):
            cmd = self.get_command(ctx, name)
            if cmd is None or cmd.hidden:
                continue
            commands.append((name, cmd))

        if not commands:
            return

        # Group by `section` attribute, defaulting to "Commands"
        sections = {}
        for name, cmd in commands:
            section_name = getattr(cmd, "section", "Commands")
            sections.setdefault(section_name, []).append((name, cmd))

        # Render each section
        for section_name, items in sections.items():
            with formatter.section(section_name):
                rows = []
                for name, cmd in items:
                    rows.append((name, cmd.get_short_help_str()))
                formatter.write_dl(rows)

    def command( # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        *args,
        **kwargs
    ) -> Callable[[Callable[..., Any]], click.Command] | click.Command:
        """
        Override Group.command to accept a 'section' kwarg.

            @cli.command(section="User Commands")
            def add():
                ...
        """
        section = kwargs.pop("section", None)

        def decorator(f: Callable) -> click.Command:
            cmd = super(SectionedGroup, self).command(*args, **kwargs)(f)
            if section is not None:
                cmd.section = section # pyright: ignore[reportAttributeAccessIssue]
            return cmd

        return decorator
