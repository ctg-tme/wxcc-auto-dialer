import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import requests

DEFAULT_SEARCH_URL = "https://api.wxcc-eu2.cisco.com/search"
DEFAULT_CAPTURES_URL = "https://api.wxcc-eu2.cisco.com/v1/captures/query"
DEFAULT_START_CURSOR = "NA"

GRAPHQL_OPERATION = "GetTaskDetails"

GRAPHQL_QUERY = """
query GetTaskDetails(
  $from: Long!
  $to: Long!
  $pagination: Pagination
  $filter: TaskDetailsFilters
) {
  taskDetails(
    from: $from
    to: $to
    pagination: $pagination
    filter: $filter
  ) {
    tasks {
      id
    }
  }
}
""".strip()

LIKELY_URL_KEYS = ("mediaDownloadUrl", "downloadUrl", "fileUrl", "url")
PAGINATION_CONTAINER_KEYS = ("pagination", "pageInfo")
PAGINATION_VALUE_HINTS = ("cursor", "nextCursor", "hasNextPage")


@dataclass
class TaskBatch:
    ids: List[str]
    next_cursor: Optional[str]
    has_next: Optional[bool]


def _find_pagination_dict(node: Any) -> Optional[Dict[str, Any]]:
    if isinstance(node, dict):
        if any(key in node for key in PAGINATION_VALUE_HINTS):
            return node
        for value in node.values():
            found = _find_pagination_dict(value)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _find_pagination_dict(item)
            if found:
                return found
    return None


def extract_pagination_info(payload: Dict[str, Any]) -> Dict[str, Any]:
    details = payload.get("data", {}).get("taskDetails")
    if isinstance(details, dict):
        for key in PAGINATION_CONTAINER_KEYS:
            candidate = details.get(key)
            if isinstance(candidate, dict):
                return candidate
    extensions = payload.get("extensions")
    if extensions:
        found = _find_pagination_dict(extensions)
        if found:
            return found
    data_section = payload.get("data")
    if data_section:
        found = _find_pagination_dict(data_section)
        if found:
            return found
    return {}


def parse_epoch_ms(value: str, label: str) -> int:
    """Accept epoch milliseconds or ISO-8601 date/time strings."""
    if not value:
        raise ValueError(f"{label} value is required")
    text = value.strip()
    try:
        return int(text)
    except ValueError:
        pass
    normalized = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError as exc:  # pragma: no cover - helpful error message path
        raise ValueError(
            f"Could not parse {label} value '{value}'. "
            "Provide ISO-8601 (e.g. 2025-09-30T00:00:00Z) or epoch milliseconds."
        ) from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def load_filter(args: argparse.Namespace) -> Optional[Dict[str, Any]]:
    if args.filter_json and args.filter_file:
        raise ValueError("Specify either --filter-json or --filter-file, not both.")
    if args.filter_json:
        return json.loads(args.filter_json)
    if args.filter_file:
        with Path(args.filter_file).expanduser().open() as handle:
            return json.load(handle)
    return None


def make_session(token: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {token.strip()}",
            "Accept": "application/json",
        }
    )
    return session


def request_task_batch(
    session: requests.Session,
    search_url: str,
    from_ms: int,
    to_ms: int,
    cursor: Optional[str],
    pagination_size: Optional[int],
    filter_obj: Optional[Dict[str, Any]],
) -> TaskBatch:
    pagination: Dict[str, Any] = {}
    if cursor is not None:
        pagination["cursor"] = cursor
    if pagination_size:
        pagination["size"] = pagination_size
    variables: Dict[str, Any] = {"from": from_ms, "to": to_ms, "pagination": pagination or None}
    if filter_obj:
        variables["filter"] = filter_obj
    payload = {
        "operationName": GRAPHQL_OPERATION,
        "query": GRAPHQL_QUERY,
        "variables": variables,
    }
    response = session.post(search_url, json=payload, timeout=60)
    try:
        response.raise_for_status()
    except requests.HTTPError as http_err:
        snippet = response.text[:500]
        raise requests.HTTPError(
            f"{http_err} | body: {snippet}", response=response, request=http_err.request
        ) from None
    payload_json = response.json()
    if payload_json.get("errors"):
        raise RuntimeError(f"GraphQL search returned errors: {payload_json['errors']}")
    details = payload_json.get("data", {}).get("taskDetails")
    if not details:
        return TaskBatch(ids=[], next_cursor=None, has_next=None)
    ids = [task.get("id") for task in details.get("tasks", []) if task.get("id")]
    pagination_info = extract_pagination_info(payload_json)
    next_cursor = pagination_info.get("nextCursor") or pagination_info.get("cursor")
    has_next = pagination_info.get("hasNextPage")
    if next_cursor == cursor:
        next_cursor = None
    if has_next is False:
        next_cursor = None
    return TaskBatch(ids=ids, next_cursor=next_cursor, has_next=has_next)


def iterate_task_ids(
    session: requests.Session,
    search_url: str,
    from_ms: int,
    to_ms: int,
    start_cursor: Optional[str] = DEFAULT_START_CURSOR,
    pagination_size: Optional[int] = None,
    filter_obj: Optional[Dict[str, Any]] = None,
    max_tasks: Optional[int] = None,
) -> Iterable[str]:
    cursor = start_cursor
    seen = set()
    while True:
        batch = request_task_batch(session, search_url, from_ms, to_ms, cursor, pagination_size, filter_obj)
        if not batch.ids:
            break
        for task_id in batch.ids:
            if task_id not in seen:
                seen.add(task_id)
                yield task_id
                if max_tasks and len(seen) >= max_tasks:
                    return
        if not batch.next_cursor:
            break
        cursor = batch.next_cursor


def traverse_path(obj: Any, path: str) -> Optional[Any]:
    current = obj
    for raw_part in path.split("."):
        part = raw_part.strip()
        if not part:
            continue
        if isinstance(current, list):
            try:
                idx = int(part)
            except ValueError:
                return None
            if idx >= len(current):
                return None
            current = current[idx]
            continue
        if isinstance(current, dict):
            if part not in current:
                return None
            current = current[part]
            continue
        return None
    return current


def looks_like_wav(url: str) -> bool:
    lowered = url.lower()
    return ".wav" in lowered or "contentType=audio" in lowered or "format=wav" in lowered


def collect_wav_urls(payload: Any) -> List[str]:
    urls: List[str] = []

    def walk(node: Any):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in LIKELY_URL_KEYS and isinstance(value, str):
                    urls.append(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, str):
            if node.startswith("http") and looks_like_wav(node):
                urls.append(node)

    walk(payload)
    deduped: List[str] = []
    seen = set()
    for url in urls:
        if url not in seen:
            seen.add(url)
            deduped.append(url)
    return deduped


def query_capture_payload(
    session: requests.Session,
    captures_url: str,
    task_id: str,
    include_segments: bool,
) -> Dict[str, Any]:
    payload = {"query": {"taskIds": [task_id], "includeSegments": include_segments}}
    response = session.post(captures_url, json=payload, timeout=60)
    response.raise_for_status()
    return response.json()


def extract_capture_urls(
    payload: Dict[str, Any],
    capture_url_key: Optional[str],
) -> List[str]:
    if capture_url_key:
        custom_value = traverse_path(payload, capture_url_key)
        if isinstance(custom_value, str):
            return [custom_value]
        if isinstance(custom_value, Sequence):
            return [item for item in custom_value if isinstance(item, str)]
        return []
    return collect_wav_urls(payload)


def download_file(
    download_session: requests.Session,
    url: str,
    destination: Path,
    overwrite: bool,
) -> None:
    if destination.exists() and not overwrite:
        print(f"[skip] {destination} already exists.")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    with download_session.get(url, stream=True, timeout=120) as response:
        response.raise_for_status()
        with destination.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    handle.write(chunk)
    print(f"[downloaded] {destination}")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch WXCC interaction WAV files via search + capture endpoints."
    )
    parser.add_argument(
        "--from",
        dest="from_value",
        required=True,
        help="Start of the range (epoch ms or ISO-8601).",
    )
    parser.add_argument(
        "--to",
        dest="to_value",
        required=True,
        help="End of the range (epoch ms or ISO-8601).",
    )
    parser.add_argument(
        "--token",
        help="Access token. If omitted, WXCC_ACCESS_TOKEN env var is used.",
    )
    parser.add_argument(
        "--search-url",
        default=DEFAULT_SEARCH_URL,
        help=f"GraphQL search endpoint. Default: {DEFAULT_SEARCH_URL}",
    )
    parser.add_argument(
        "--captures-url",
        default=DEFAULT_CAPTURES_URL,
        help=f"Capture query endpoint. Default: {DEFAULT_CAPTURES_URL}",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        help="Optional pagination size (if supported by the API).",
    )
    parser.add_argument(
        "--filter-json",
        help="TaskDetails filter JSON literal.",
    )
    parser.add_argument(
        "--filter-file",
        help="Path to a JSON file with TaskDetails filters.",
    )
    parser.add_argument(
        "--output-dir",
        default="audio/downloads",
        help="Directory to save WAV files (defaults to audio/downloads).",
    )
    parser.add_argument(
        "--capture-url-key",
        help="Dot-separated path (e.g. captures.0.url) to extract download URLs explicitly.",
    )
    parser.add_argument(
        "--include-segments",
        action="store_true",
        help="Pass includeSegments=true to the capture query.",
    )
    parser.add_argument(
        "--max-tasks",
        type=int,
        help="Stop after processing this many task ids.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite WAV files if they already exist.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List which files would be downloaded without performing downloads.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = parse_args(argv)
        from_ms = parse_epoch_ms(args.from_value, "--from")
        to_ms = parse_epoch_ms(args.to_value, "--to")
        token = args.token or os.getenv("WXCC_ACCESS_TOKEN")
        if not token:
            raise ValueError("Provide an access token with --token or WXCC_ACCESS_TOKEN env var.")
        filter_obj = load_filter(args)
    except Exception as exc:  # pragma: no cover - CLI validation path
        print(f"[error] {exc}", file=sys.stderr)
        return 2

    session = make_session(token)
    download_session = requests.Session()
    output_dir = Path(args.output_dir).expanduser()
    total_downloaded = 0
    total_missing = 0
    task_generator = iterate_task_ids(
        session=session,
        search_url=args.search_url,
        from_ms=from_ms,
        to_ms=to_ms,
        pagination_size=args.page_size,
        filter_obj=filter_obj,
        max_tasks=args.max_tasks,
    )

    for task_id in task_generator:
        print(f"[task] {task_id}")
        try:
            payload = query_capture_payload(
                session=session,
                captures_url=args.captures_url,
                task_id=task_id,
                include_segments=args.include_segments,
            )
        except requests.HTTPError as http_err:
            total_missing += 1
            print(f"[error] Capture query failed for {task_id}: {http_err}", file=sys.stderr)
            continue
        except requests.RequestException as req_err:
            total_missing += 1
            print(f"[error] Network issue for {task_id}: {req_err}", file=sys.stderr)
            continue

        urls = extract_capture_urls(payload, args.capture_url_key)
        if not urls:
            total_missing += 1
            print(f"[warn] No WAV URL found for {task_id}.", file=sys.stderr)
            continue

        for idx, url in enumerate(urls):
            suffix = "" if len(urls) == 1 else f"_{idx+1}"
            destination = output_dir / f"{task_id}{suffix}.wav"
            if args.dry_run:
                print(f"[dry-run] Would download {url} -> {destination}")
                continue
            try:
                download_file(download_session, url, destination, args.overwrite)
                total_downloaded += 1
            except requests.HTTPError as http_err:
                total_missing += 1
                print(f"[error] Download failed for {task_id}: {http_err}", file=sys.stderr)
            except requests.RequestException as req_err:
                total_missing += 1
                print(f"[error] Download error for {task_id}: {req_err}", file=sys.stderr)

    print(
        f"[done] Downloaded {total_downloaded} file(s). "
        f"{'Some files were skipped.' if total_missing else 'All requested files downloaded.'}"
    )
    return 0 if total_missing == 0 or args.dry_run else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
