"""Temporary media isolation and guaranteed cleanup for pipeline jobs.

Enforces ADR 0004 ("Never persist media: temp files scrubbed on success and failure;
crashed job leaves nothing behind").
"""
from __future__ import annotations

import gc
import logging
import re
import shutil
import tempfile
import uuid
from pathlib import Path
from types import TracebackType

logger = logging.getLogger(__name__)

# Valid save_id characters (alphanumeric, hyphen, underscore) to prevent path traversal
_SAVE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")


def get_base_media_dir() -> Path:
    """Return the base temporary directory for ClayBank job media.

    Returns:
        Path: Base directory path under system temporary directory.
    """
    return Path(tempfile.gettempdir()) / "claybank"


class IsolatedJobMedia:
    """Asynchronous context manager providing an isolated temporary directory for a job.

    Creates a unique directory under tempfile.gettempdir()/claybank/job_{save_id}_{uuid}.
    Guarantees recursive cleanup of all media and temporary files upon block exit,
    whether the block exits normally, raises an exception, times out, or is cancelled.

    Args:
        save_id: The unique identifier of the save being processed.
        base_dir: Optional base directory override (defaults to get_base_media_dir()).

    Raises:
        ValueError: If save_id contains invalid characters or path traversal components.
    """

    def __init__(self, save_id: str, base_dir: Path | None = None) -> None:
        if not save_id or not isinstance(save_id, str):
            raise ValueError("save_id must be a non-empty string")
        if not _SAVE_ID_PATTERN.match(save_id):
            raise ValueError(
                f"Invalid save_id '{save_id}': must contain only alphanumeric, hyphen, or underscore characters"
            )

        self.save_id: str = save_id
        self.token: str = uuid.uuid4().hex
        root: Path = base_dir if base_dir is not None else get_base_media_dir()
        self.dir: Path = root / f"job_{self.save_id}_{self.token}"

    def create_temp_file(self, filename: str | None = None, suffix: str = "") -> Path:
        """Create and return a safe file path inside the isolated job directory.

        Args:
            filename: Optional explicit file name. Must remain within self.dir.
            suffix: File extension/suffix if filename is not specified (e.g. '.mp3').

        Returns:
            Path: Absolute path to the file inside self.dir.

        Raises:
            ValueError: If filename attempts path traversal outside self.dir.
            RuntimeError: If called before entering the context manager.
        """
        if not self.dir.exists():
            raise RuntimeError("Cannot create temporary file before entering IsolatedJobMedia context")

        if filename:
            target = (self.dir / filename).resolve()
            # Enforce path containment within self.dir
            try:
                target.relative_to(self.dir.resolve())
            except ValueError:
                raise ValueError(f"Path traversal detected: '{filename}' escapes isolated job directory")
            return target

        generated_name = f"media_{uuid.uuid4().hex}{suffix}"
        return self.dir / generated_name

    def cleanup(self) -> None:
        """Recursively remove the isolated directory and all temporary contents.

        Handles file locking (common on Windows) by forcing garbage collection
        and retrying with ignore_errors=True. Logs a warning on deferred cleanup.
        """
        if not self.dir.exists():
            return

        try:
            shutil.rmtree(self.dir, ignore_errors=False)
        except (PermissionError, OSError) as err:
            # On Windows, open handles can lock files temporarily. Collect garbage and retry.
            gc.collect()
            try:
                shutil.rmtree(self.dir, ignore_errors=True)
            except Exception as retry_err:
                logger.warning(
                    "Deferred cleanup of isolated directory %s: initial err=%s, retry err=%s",
                    self.dir,
                    err,
                    retry_err,
                )
            else:
                if self.dir.exists():
                    logger.warning("Deferred cleanup of isolated directory %s: %s", self.dir, err)

    async def __aenter__(self) -> Path:
        """Create the isolated job directory and return its path.

        Returns:
            Path: The created directory path.
        """
        self.dir.mkdir(parents=True, exist_ok=True)
        return self.dir

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        """Scrub all temporary media on context exit.

        Ensures cleanup executes during normal exit, exceptions, cancellations, and timeouts.
        Does not suppress any exceptions.
        """
        self.cleanup()
        return None
