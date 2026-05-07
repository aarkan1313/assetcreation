"""Headless ComfyUI runner for local/open-weights pipeline lanes.

Default CLI mode is a dry-run plan. It loads a workflow JSON, applies node
input overrides, reports node counts and output node IDs, and does not contact
ComfyUI unless --run is passed.

Runtime path:
  1. POST {"prompt": workflow, "client_id": uuid} to /prompt.
  2. Poll /history/<prompt_id> until ComfyUI records outputs.
  3. Download output files via /view into the requested output directory.

This intentionally uses only the Python standard library so every pipeline can
import it without adding a shared dependency.
"""
from __future__ import annotations

import argparse
import json
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_HOST = "http://127.0.0.1:8188"


@dataclass
class DownloadedOutput:
    node_id: str
    output_kind: str
    filename: str
    subfolder: str
    comfy_type: str
    local_path: str


@dataclass
class ComfyRunResult:
    schema: str
    workflow_path: str
    host: str
    dry_run: bool
    node_count: int
    output_node_ids: list[str]
    prompt_id: str | None
    missing_node_types: list[str]
    downloaded: list[DownloadedOutput]
    elapsed_s: float


class ComfyError(RuntimeError):
    """Raised for ComfyUI API or workflow execution failures."""


def load_workflow(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"workflow must be a JSON object: {path}")
    return data


def node_count(workflow: dict[str, Any]) -> int:
    return sum(1 for value in workflow.values() if isinstance(value, dict) and "class_type" in value)


def node_types(workflow: dict[str, Any]) -> set[str]:
    return {
        value["class_type"]
        for value in workflow.values()
        if isinstance(value, dict) and isinstance(value.get("class_type"), str)
    }


def _parse_override_value(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def apply_override(workflow: dict[str, Any], path: str, value: Any) -> None:
    """Apply a dotted override such as "6.inputs.text=hello".

    Numeric path segments index lists. All other segments index dictionaries.
    """
    parts = path.split(".")
    if not parts or any(part == "" for part in parts):
        raise ValueError(f"invalid override path: {path!r}")

    cur: Any = workflow
    for part in parts[:-1]:
        if isinstance(cur, list):
            cur = cur[int(part)]
        elif isinstance(cur, dict):
            if part not in cur:
                raise KeyError(f"override path {path!r} missing segment {part!r}")
            cur = cur[part]
        else:
            raise TypeError(f"cannot descend into {type(cur).__name__} for {path!r}")

    last = parts[-1]
    if isinstance(cur, list):
        cur[int(last)] = value
    elif isinstance(cur, dict):
        cur[last] = value
    else:
        raise TypeError(f"cannot set {path!r} on {type(cur).__name__}")


def apply_overrides(workflow: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    patched = json.loads(json.dumps(workflow))
    for key, value in overrides.items():
        apply_override(patched, key, value)
    return patched


def _json_request(method: str, url: str, payload: dict[str, Any] | None = None, timeout_s: float = 30.0) -> Any:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, data=body, method=method, headers=headers)
    try:
        with urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read()
    except HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            detail = str(exc)
        raise ComfyError(f"{method} {url} failed: HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise ComfyError(f"{method} {url} failed: {exc}") from exc
    if not raw:
        return None
    return json.loads(raw.decode("utf-8"))


def _multipart_form(fields: dict[str, str], files: dict[str, Path]) -> tuple[bytes, str]:
    boundary = f"----phase9-comfy-{uuid.uuid4().hex}"
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(
            (
                f"--{boundary}\r\n"
                f"Content-Disposition: form-data; name=\"{name}\"\r\n\r\n"
                f"{value}\r\n"
            ).encode("utf-8")
        )
    for name, path in files.items():
        filename = path.name
        parts.append(
            (
                f"--{boundary}\r\n"
                f"Content-Disposition: form-data; name=\"{name}\"; filename=\"{filename}\"\r\n"
                "Content-Type: application/octet-stream\r\n\r\n"
            ).encode("utf-8")
        )
        parts.append(path.read_bytes())
        parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(parts), boundary


def _multipart_request(url: str, fields: dict[str, str], files: dict[str, Path], timeout_s: float = 60.0) -> Any:
    body, boundary = _multipart_form(fields, files)
    req = Request(
        url,
        data=body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    try:
        with urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ComfyError(f"POST {url} failed: HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise ComfyError(f"POST {url} failed: {exc}") from exc
    if not raw:
        return None
    return json.loads(raw.decode("utf-8"))


def _binary_get(url: str, timeout_s: float = 60.0) -> bytes:
    try:
        with urlopen(url, timeout=timeout_s) as resp:
            return resp.read()
    except HTTPError as exc:
        raise ComfyError(f"GET {url} failed: HTTP {exc.code}") from exc
    except URLError as exc:
        raise ComfyError(f"GET {url} failed: {exc}") from exc


class ComfyRunner:
    def __init__(self, host: str = DEFAULT_HOST) -> None:
        self.host = host.rstrip("/")

    def object_info(self) -> dict[str, Any]:
        return _json_request("GET", f"{self.host}/object_info")

    def missing_node_types(self, workflow: dict[str, Any]) -> list[str]:
        info = self.object_info()
        available = set(info.keys())
        return sorted(node_types(workflow) - available)

    def submit(self, workflow: dict[str, Any]) -> str:
        payload = {"prompt": workflow, "client_id": str(uuid.uuid4())}
        result = _json_request("POST", f"{self.host}/prompt", payload)
        prompt_id = result.get("prompt_id") if isinstance(result, dict) else None
        if not prompt_id:
            raise ComfyError(f"/prompt did not return prompt_id: {result!r}")
        return str(prompt_id)

    def upload_input_file(self, file_path: Path, *, name: str | None = None, overwrite: bool = True) -> str:
        """Upload a file to ComfyUI's input store and return its Comfy name.

        ComfyUI exposes this through /upload/image even for many input-file
        workflows. The form field remains "image" because that is the API
        contract; callers should use this generic method for non-image inputs.
        """
        if not file_path.exists():
            raise FileNotFoundError(file_path)
        upload_name = name or file_path.name
        result = _multipart_request(
            f"{self.host}/upload/image",
            fields={"type": "input", "overwrite": "true" if overwrite else "false", "subfolder": ""},
            files={"image": file_path},
        )
        if isinstance(result, dict):
            return str(result.get("name") or upload_name)
        return upload_name

    def upload_image(self, image_path: Path, *, name: str | None = None, overwrite: bool = True) -> str:
        """Upload an image to ComfyUI's input store and return its Comfy name."""
        return self.upload_input_file(image_path, name=name, overwrite=overwrite)

    def history(self, prompt_id: str) -> dict[str, Any]:
        return _json_request("GET", f"{self.host}/history/{prompt_id}")

    def wait_for_history(self, prompt_id: str, *, timeout_s: float, poll_s: float) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_s
        last: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            last = self.history(prompt_id)
            item = last.get(prompt_id) if isinstance(last, dict) else None
            if isinstance(item, dict):
                status = item.get("status", {})
                completed = bool(status.get("completed")) if isinstance(status, dict) else False
                has_outputs = bool(item.get("outputs"))
                if completed or has_outputs:
                    return item
            time.sleep(poll_s)
        raise ComfyError(f"timed out waiting for prompt {prompt_id}; last history={last!r}")

    def download_outputs(
        self,
        history_item: dict[str, Any],
        *,
        output_node_ids: list[str],
        out_dir: Path,
    ) -> list[DownloadedOutput]:
        out_dir.mkdir(parents=True, exist_ok=True)
        outputs = history_item.get("outputs", {})
        downloaded: list[DownloadedOutput] = []
        for node_id in output_node_ids:
            node_outputs = outputs.get(str(node_id), {}) if isinstance(outputs, dict) else {}
            if not isinstance(node_outputs, dict):
                continue
            for output_kind, entries in node_outputs.items():
                if not isinstance(entries, list):
                    continue
                for index, entry in enumerate(entries):
                    if not isinstance(entry, dict) or "filename" not in entry:
                        continue
                    filename = str(entry["filename"])
                    subfolder = str(entry.get("subfolder", ""))
                    comfy_type = str(entry.get("type", "output"))
                    query = urlencode({"filename": filename, "subfolder": subfolder, "type": comfy_type})
                    data = _binary_get(f"{self.host}/view?{query}")
                    suffix = Path(filename).suffix or ".bin"
                    local = out_dir / f"{node_id}_{output_kind}_{index}{suffix}"
                    local.write_bytes(data)
                    downloaded.append(
                        DownloadedOutput(
                            node_id=str(node_id),
                            output_kind=str(output_kind),
                            filename=filename,
                            subfolder=subfolder,
                            comfy_type=comfy_type,
                            local_path=str(local),
                        )
                    )
        return downloaded

    def run(
        self,
        *,
        workflow_path: Path,
        overrides: dict[str, Any] | None = None,
        output_node_ids: list[str] | None = None,
        out_dir: Path | None = None,
        dry_run: bool = True,
        validate_nodes: bool = False,
        allow_missing_nodes: bool = False,
        timeout_s: float = 300.0,
        poll_s: float = 1.0,
    ) -> ComfyRunResult:
        started = time.monotonic()
        workflow = apply_overrides(load_workflow(workflow_path), overrides or {})
        output_node_ids = [str(x) for x in (output_node_ids or [])]
        missing: list[str] = []
        if validate_nodes and not dry_run:
            missing = self.missing_node_types(workflow)
            if missing and not allow_missing_nodes:
                raise ComfyError(f"workflow needs missing ComfyUI node types: {', '.join(missing)}")
        if dry_run:
            return ComfyRunResult(
                schema="comfy_runner.result.v1",
                workflow_path=str(workflow_path),
                host=self.host,
                dry_run=True,
                node_count=node_count(workflow),
                output_node_ids=output_node_ids,
                prompt_id=None,
                missing_node_types=missing,
                downloaded=[],
                elapsed_s=time.monotonic() - started,
            )

        prompt_id = self.submit(workflow)
        history_item = self.wait_for_history(prompt_id, timeout_s=timeout_s, poll_s=poll_s)
        downloaded = self.download_outputs(
            history_item,
            output_node_ids=output_node_ids,
            out_dir=out_dir or Path("comfy_outputs") / prompt_id,
        )
        return ComfyRunResult(
            schema="comfy_runner.result.v1",
            workflow_path=str(workflow_path),
            host=self.host,
            dry_run=False,
            node_count=node_count(workflow),
            output_node_ids=output_node_ids,
            prompt_id=prompt_id,
            missing_node_types=missing,
            downloaded=downloaded,
            elapsed_s=time.monotonic() - started,
        )


def _parse_override_args(raw_overrides: list[str]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for raw in raw_overrides:
        if "=" not in raw:
            raise SystemExit(f"--override must be path=value, got {raw!r}")
        key, value = raw.split("=", 1)
        parsed[key] = _parse_override_value(value)
    return parsed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workflow", type=Path, required=True)
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--override", action="append", default=[], help="Dotted override path=value")
    ap.add_argument("--output-node", action="append", default=[], help="Comfy node ID to download outputs from")
    ap.add_argument("--out-dir", type=Path, default=Path("comfy_outputs"))
    ap.add_argument("--result-out", type=Path, default=None)
    ap.add_argument("--run", action="store_true", help="Actually call ComfyUI. Omit for dry-run plan.")
    ap.add_argument("--validate-nodes", action="store_true", help="Check workflow node classes via /object_info before run")
    ap.add_argument("--allow-missing-nodes", action="store_true")
    ap.add_argument("--timeout-s", type=float, default=300.0)
    ap.add_argument("--poll-s", type=float, default=1.0)
    args = ap.parse_args()

    runner = ComfyRunner(args.host)
    result = runner.run(
        workflow_path=args.workflow,
        overrides=_parse_override_args(args.override),
        output_node_ids=args.output_node,
        out_dir=args.out_dir,
        dry_run=not args.run,
        validate_nodes=args.validate_nodes,
        allow_missing_nodes=args.allow_missing_nodes,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
    )
    payload = asdict(result)
    if args.result_out:
        args.result_out.parent.mkdir(parents=True, exist_ok=True)
        args.result_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
