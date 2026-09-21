import logging
import re
from pathlib import Path

from markitdown import MarkItDown, UnsupportedFormatException

from .cache import ExtractionCache
from .models import FileEvidence

logger = logging.getLogger(__name__)


PAGE_MARKER = re.compile(r"(?=<!--\s*(?:Page|Slide)(?:Break| number)?\s*:?\s*\d*)", re.I)


class TextExtractor:
    def __init__(
        self,
        max_chars: int = 12_000,
        max_pages: int = 5,
        cache_enabled: bool = True,
        refresh_cache: bool = False,
    ) -> None:
        self._converter = MarkItDown(enable_plugins=False)
        self._max_chars = max_chars
        self._max_pages = max_pages
        self.cache = ExtractionCache(
            enabled=cache_enabled,
            refresh=refresh_cache,
            max_pages=max_pages,
            max_chars=max_chars,
        )

    def extract(self, path: Path) -> FileEvidence:
        logger.info("[EXTRACT] start path=%s size=%d", path, path.stat().st_size)
        if cached := self.cache.get(path):
            logger.info("[EXTRACT] cache_hit path=%s chars=%d", path, len(cached.content))
            return cached
        try:
            content = self._converter.convert_local(path).markdown.strip()
            extraction = "markitdown"
        except UnsupportedFormatException:
            content = path.name
            extraction = "filename_unsupported"
        except Exception as error:
            logger.warning(
                "[EXTRACT] conversion_failed path=%s error_type=%s",
                path,
                type(error).__name__,
            )
            content = path.name
            extraction = "filename_conversion_error"

        content = limit_pages(content, self._max_pages)[: self._max_chars] or path.name
        evidence = FileEvidence(path=path, content=content, extraction=extraction)
        self.cache.put(evidence)
        logger.info(
            "[EXTRACT] complete path=%s method=%s chars=%d",
            path,
            extraction,
            len(content),
        )
        return evidence

    def flush(self) -> None:
        self.cache.flush()


def limit_pages(content: str, max_pages: int) -> str:
    form_feed_pages = content.split("\f")
    if len(form_feed_pages) > 1:
        return "\n\n".join(form_feed_pages[:max_pages]).strip()
    marked_pages = PAGE_MARKER.split(content)
    if len(marked_pages) > 1:
        prefix = marked_pages[0] if not marked_pages[0].strip() else ""
        return (prefix + "".join(marked_pages[1 : max_pages + 1])).strip()
    return content
