"""State-of-the-art console and container log formatter."""

from __future__ import annotations

import logging
import os
from datetime import datetime

# ANSI Color Escape Codes
_RESET = '\033[0m'
_BOLD = '\033[1m'
_DIM = '\033[2m'

_COLORS = {
    'DEBUG': '\033[36m',  # Cyan
    'INFO': '\033[32m',  # Green
    'WARNING': '\033[33m',  # Yellow
    'ERROR': '\033[31m',  # Red
    'CRITICAL': '\033[1;31m',  # Bold Red
}

_SUBSYSTEM_COLOR = '\033[35m'  # Magenta
_CONTEXT_COLOR = '\033[34m'  # Blue
_TIME_COLOR = '\033[90m'  # Dark Gray


class ConsoleLogFormatter(logging.Formatter):
    """Clean, high-visibility log formatter tailored for docker logs and console terminals."""

    def __init__(self, use_colors: bool | None = None) -> None:
        super().__init__()
        if use_colors is None:
            # Auto-enable colors unless explicitly disabled by NO_COLOR
            self.use_colors = os.getenv('NO_COLOR') is None
        else:
            self.use_colors = use_colors

    def format(self, record: logging.LogRecord) -> str:
        # Format UTC/local timestamp as YYYY-MM-DD HH:MM:SS
        record_time = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')

        # Log Level
        levelname = record.levelname
        level_padded = f'{levelname:<5}'

        # Context (match_id, library_name, request_id)
        subsystem = getattr(record, 'subsystem', record.name)
        match_id = getattr(record, 'match_id', None)
        library_name = getattr(record, 'library_name', None)

        context_tag = ''
        if match_id:
            context_tag = f':{match_id[:8]}'
        elif library_name:
            context_tag = f':{library_name}'

        subsystem_badge = f'[{subsystem}{context_tag}]'

        # Format message and interpolate arguments
        message = record.getMessage()

        # Handle exception tracebacks if present
        exc_text = ''
        if record.exc_info:
            exc_text = '\n' + self.formatException(record.exc_info)
        elif record.stack_info:
            exc_text = '\n' + self.formatStack(record.stack_info)

        if self.use_colors:
            color = _COLORS.get(levelname, '')
            context_part = f'{_CONTEXT_COLOR}{context_tag}{_RESET}' if context_tag else ''
            formatted = (
                f'{_TIME_COLOR}{record_time}{_RESET} '
                f'{color}[{level_padded}]{_RESET} '
                f'{_SUBSYSTEM_COLOR}[{subsystem}{_RESET}'
                f'{context_part}'
                f'{_SUBSYSTEM_COLOR}]{_RESET} '
                f'{message}{exc_text}'
            )
        else:
            formatted = f'{record_time} [{level_padded}] {subsystem_badge} {message}{exc_text}'

        return formatted
