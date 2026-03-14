"""Polling trigger: checks a source for changes at intervals."""

import hashlib
import logging
import requests
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class PollingTrigger:
    """Polls GitHub issues or a URL for changes. Fires callback with new data."""

    def __init__(self, config: Dict[str, Any], callback: Callable[[Dict[str, Any]], None]):
        self.source = config.get("source", "generic")
        self.interval_minutes = max(1, int(config.get("interval_minutes", 5)))
        self.repo = config.get("repo", "")
        self.url = config.get("url", "")
        self.callback = callback
        self._last_seen_ids: set = set()
        self._last_hash: Optional[str] = None

    def fire(self) -> None:
        """Called by the runner's scheduler loop. Check for changes and fire callback if found."""
        if self.source == "github_issues":
            self._poll_github_issues()
        elif self.source == "url_check":
            self._poll_url()
        else:
            self._poll_generic_url()

    def _poll_github_issues(self) -> None:
        if not self.repo:
            return
        api_url = f"https://api.github.com/repos/{self.repo}/issues?state=open&sort=created&direction=desc&per_page=10"
        try:
            resp = requests.get(api_url, timeout=30, headers={"Accept": "application/vnd.github.v3+json"})
            resp.raise_for_status()
            issues: List[Dict] = resp.json()
        except Exception as e:
            logger.warning("GitHub poll failed for %s: %s", self.repo, e)
            return

        for issue in issues:
            issue_id = issue.get("number", 0)
            if issue_id and issue_id not in self._last_seen_ids:
                if self._last_seen_ids:
                    self.callback({
                        "data": f"Title: {issue.get('title', '')}\nBody: {(issue.get('body') or '')[:500]}",
                        "title": issue.get("title", ""),
                        "body": (issue.get("body") or "")[:500],
                        "url": issue.get("html_url", ""),
                        "repo": self.repo,
                        "source": "github_issues",
                    })
                self._last_seen_ids.add(issue_id)

    def _poll_url(self) -> None:
        if not self.url:
            return
        try:
            resp = requests.get(self.url, timeout=30)
            content_hash = hashlib.md5(resp.text.encode()).hexdigest()
        except Exception as e:
            logger.warning("URL poll failed for %s: %s", self.url, e)
            return

        # First successful fetch: always fire once so polling/url_check/generic
        # agents have an initial run, then only fire on changes thereafter.
        if self._last_hash is None:
            self._last_hash = content_hash
            self.callback({
                "data": resp.text[:1000],
                "url": self.url,
                "source": "url_check",
            })
            return

        if content_hash != self._last_hash:
            self._last_hash = content_hash
            self.callback({
                "data": resp.text[:1000],
                "url": self.url,
                "source": "url_check",
            })

    def _poll_generic_url(self) -> None:
        if self.url:
            self._poll_url()
