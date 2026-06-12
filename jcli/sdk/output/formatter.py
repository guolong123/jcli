import json
from typing import Any, Dict, List, Optional, Union

import yaml
from rich.console import Console
from rich.table import Table


class OutputFormatter:
    """Output formatter supporting table, JSON, and YAML formats using Rich library."""

    def __init__(self, format_type: str = "table"):
        """Initialize formatter.

        Args:
            format_type: Output format - "table", "json", or "yaml"
        """
        if format_type not in ("table", "json", "yaml"):
            raise ValueError(f"format_type must be 'table', 'json', or 'yaml', got '{format_type}'")
        self.format_type = format_type
        self.console = Console()
        self.error_console = Console(stderr=True)

    def print_table(
        self,
        headers: List[str],
        rows: List[List[Any]],
        title: Optional[str] = None,
    ) -> None:
        """Print data as a formatted table using Rich.

        Args:
            headers: Column headers
            rows: List of row data
            title: Optional table title
        """
        if self.format_type == "json":
            self.print_json([dict(zip(headers, row)) for row in rows])
            return

        if self.format_type == "yaml":
            self.print_yaml([dict(zip(headers, row)) for row in rows])
            return

        table = Table(
            title=title,
            show_header=True,
            header_style="bold cyan",
            box=None,
            show_lines=False,
            expand=False,
        )

        # Add columns with auto-width
        for header in headers:
            table.add_column(header, no_wrap=False)

        # Add rows with alternating colors
        for idx, row in enumerate(rows):
            style = "dim" if idx % 2 == 1 else None
            table.add_row(*[str(cell) for cell in row], style=style)

        self.console.print(table)

    def print_json(self, data: Union[Dict, List, Any]) -> None:
        """Print data as formatted JSON.

        When ``self.format_type`` is ``"yaml"``, delegates to
        :meth:`print_yaml` instead.

        Args:
            data: Data to format as JSON
        """
        if self.format_type == "yaml":
            self.print_yaml(data)
            return

        output = json.dumps(data, indent=2, ensure_ascii=False)
        self.console.print(output)

    def print_yaml(self, data: Union[Dict, List, Any]) -> None:
        """Print data as formatted YAML.

        Args:
            data: Data to format as YAML.  If already a string it is
                printed as-is; otherwise :func:`yaml.dump` is used.
        """
        if isinstance(data, str):
            print(data)
        else:
            output = yaml.dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)
            print(output, end="")

    def print_error(self, message: str) -> None:
        """Print error message in red to stderr.

        Args:
            message: Error message
        """
        self.error_console.print(f"[red]Error: {message}[/red]")

    def print_success(self, message: str) -> None:
        """Print success message in green.

        Args:
            message: Success message
        """
        self.console.print(f"[green]{message}[/green]")

    def print_info(self, message: str) -> None:
        """Print info message in blue.

        Args:
            message: Info message
        """
        self.console.print(f"[blue]{message}[/blue]")


def get_formatter(ctx) -> OutputFormatter:
    """Create an OutputFormatter from Click context.

    Reads ``ctx.obj["format"]`` (default ``"table"``).

    Args:
        ctx: Click context with ``ctx.obj`` dict.

    Returns:
        Configured ``OutputFormatter`` instance.
    """
    format_type = ctx.obj.get("format", "table") if ctx.obj else "table"
    return OutputFormatter(format_type=format_type)
