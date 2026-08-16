"""
First:

ssh -L 5001:localhost:5001 <user>@<ip>


Qwen-Image-Layered Client

Usage (CLI):
  python decompose.py decompose <image_path> --name <name> --config <json> --layers <int> --save_path <path>
  python decompose.py submit --image_path <path> --name <name> --config <json> --layers <int> --save_path <path>
  python decompose.py query <task_id>
  python decompose.py get <task_id>
  python decompose.py list

Usage (Python):
  from qwen import QwenImageLayeredClient
  client = QwenImageLayeredClient(cache_dir=".cache", server_url="http://127.0.0.1:5001")
  task_id = client.submit("image.png", layers=4, save_path="/output/dir")
  status = client.query(task_id)
  client.get(task_id)
  tasks = client.list()

Details:
- If config is None, no config param is sent; server uses its defaults
- layers can appear in both config and CLI; CLI value overrides config
- At least one of config file or layers must be provided
- Uses .cache/tasks.json to track submitted tasks and updates status after each query
- Output images saved to .cache/<name>/x.png or save_path/<name>/x.png; existing dirs are replaced with a warning
"""

import requests
import json
import shutil
import zipfile
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Union
import os
import time

import typer

cli_app = typer.Typer(help="Qwen-Image-Layered Client", rich_markup_mode=None, pretty_exceptions_enable=False)


# ============ Proxy bypass logic ============

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}

# Session for local requests (no env proxy)
_LOCAL_SESSION = None


def _get_session(url: str) -> requests.Session:
    """Return a session that bypasses proxy for local addresses."""
    global _LOCAL_SESSION

    from urllib.parse import urlparse
    parsed = urlparse(url)
    host = parsed.hostname or ""

    is_local = (
        host in LOCAL_HOSTS or
        host.startswith("127.") or
        host.startswith("192.168.") or
        host == "localhost"
    )

    if is_local:
        if _LOCAL_SESSION is None:
            _LOCAL_SESSION = requests.Session()
            _LOCAL_SESSION.trust_env = False
        return _LOCAL_SESSION
    else:
        return requests.Session()


# ============ Default config ============


class DefaultConfig:
    """Default parameter values."""

    LAYERS = 2
    POLL_INTERVAL = 2.0
    TIMEOUT = 600.0


def _load_env():
    from util.env import load_unified_env
    load_unified_env()


def _get_server_url() -> str:
    _load_env()
    url = os.environ.get("QWEN_SERVER_URL", "")
    if not url:
        print("QWEN_SERVER_URL not set. Add it to .env")
        raise typer.Exit(1)
    return url.rstrip("/")


def decompose(
    image_path: str,
    layers: int = 2,
    config: dict = None,
    save_path: str = None,
    name: str = None,
    timeout: float = 600.0,
    poll_interval: float = 2.0,
    verbose: bool = True,
) -> List[str]:
    """One-call layer decomposition, no class instantiation needed.

    Only requires `pip install requests`:
        from decompose import decompose
        paths = decompose("character.png", layers=3)

    Server URL read from QWEN_SERVER_URL env var (via .env).

    Args:
        image_path: Input image path
        layers: Number of layers (2-10), default 2
        config: Extra config dict; layers param overrides its layers field
        save_path: Output directory, default <image_parent>/decomposed/
        name: Output subdirectory name, default image filename without extension
        timeout: Timeout in seconds, default 600
        poll_interval: Poll interval in seconds, default 2
        verbose: Print progress, default True

    Returns:
        List of output image paths, e.g. ["out/char_d0.png", "out/char_d1.png"]

    Raises:
        ValueError: Bad params or server error
        ConnectionError: Cannot reach server
        TimeoutError: Task timed out
    """
    import requests as _req, json as _json, zipfile as _zip, shutil as _sh, time as _t
    import mimetypes as _mt
    from pathlib import Path as _P

    img = _P(image_path)
    if not img.exists():
        raise ValueError(f"Image not found: {image_path}")
    if not (2 <= layers <= 10):
        raise ValueError(f"layers must be 2-10, got: {layers}")

    base_url = _get_server_url()
    task_name = name or img.stem
    mime_type = _mt.guess_type(str(img))[0] or "application/octet-stream"

    # Build config
    cfg = dict(config) if config else {}
    cfg["layers"] = layers

    _log = lambda msg: print(msg) if verbose else None

    def _safe_json(resp, context=""):
        """Parse JSON safely, print raw response on failure."""
        try:
            return resp.json()
        except _json.JSONDecodeError:
            raw = resp.text[:500] if resp.text else "(empty)"
            print(f"\n[ERROR] JSON parse failed in {context}")
            print(f"[ERROR] Status: {resp.status_code}")
            print(f"[ERROR] Response:\n{raw}")
            raise ValueError(f"Server returned non-JSON (status={resp.status_code}): {raw[:200]}")

    _log(f"Submitting {img.name} ({mime_type}) -> {base_url} (layers={layers})")
    try:
        with open(img, "rb") as f:
            resp = _get_session(base_url).post(
                f"{base_url}/submit",
                files={"image": (img.name, f, mime_type)},
                data={"name": task_name, "config": _json.dumps(cfg)},
            )
        result = _safe_json(resp, "submit")
        if "error" in result:
            raise ValueError(f"Server error: {result['error']}")
        task_id = result["task_id"]
        _log(f"task_id = {task_id}")
    except _req.exceptions.ConnectionError:
        raise ConnectionError(f"Cannot connect to {base_url}, check if server is reachable")

    # poll
    start = _t.time()
    last_status = None
    while True:
        if _t.time() - start > timeout:
            raise TimeoutError(f"Task {task_id} timed out ({timeout}s)")
        try:
            poll_resp = _get_session(base_url).get(f"{base_url}/query/{task_id}")
            status = _safe_json(poll_resp, f"query/{task_id}").get("status", "unknown")
        except requests.exceptions.ConnectionError:
            raise ConnectionError("Connection lost during polling")
        if status != last_status:
            _log(f"status: {status}")
            last_status = status
        if status == "completed":
            break
        if status == "failed":
            raise ValueError(f"Task failed: {task_id}")
        _t.sleep(poll_interval)

    # download & extract
    _log("Downloading results...")
    base_dir = _P(save_path) if save_path else img.parent / "decomposed"
    out_dir = base_dir / task_name
    if out_dir.exists():
        _sh.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    resp = _get_session(base_url).get(f"{base_url}/get/{task_id}")
    if "application/zip" not in resp.headers.get("content-type", ""):
        err = _safe_json(resp, f"get/{task_id}") if resp.headers.get("content-type", "").startswith("application/json") else {"error": resp.text[:200]}
        raise ValueError(f"Download failed: {err.get('error', resp.text[:200])}")

    zip_path = out_dir / "result.zip"
    zip_path.write_bytes(resp.content)
    with _zip.ZipFile(zip_path, "r") as zf:
        zf.extractall(out_dir)
    zip_path.unlink()

    # Rename: 1.png -> <name>_d0.png, 2.png -> <name>_d1.png
    for idx, old in enumerate(sorted(out_dir.glob("*.png"))):
        old.rename(out_dir / f"{task_name}_d{idx}.png")

    paths = sorted(str(p) for p in out_dir.glob("*.png"))
    _log(f"Done! {len(paths)} layers -> {out_dir}")
    for p in paths:
        _log(f"  - {_P(p).name}")
    return paths


# Save reference before CLI command shadows the name
_decompose_standalone = decompose


class QwenImageLayeredClient:
    """Qwen-Image-Layered API client."""

    def __init__(self, cache_dir: Union[str, Path] = None, server_url: str = None):
        """Initialize client.

        Args:
            cache_dir: Cache directory, default <module_dir>/.cache
            server_url: Server URL. Falls back to QWEN_SERVER_URL env var. Must be set.
        """
        if cache_dir is None:
            self.cache_dir = Path(__file__).parent / ".cache"
        else:
            self.cache_dir = Path(cache_dir)

        self.server_url = server_url or _get_server_url()
        self.tasks_file = self.cache_dir / "tasks.json"

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        print(f"QWEN SERVER URL: {self.server_url}")

        # Connection check
        self._check_connection()

    def _check_connection(self):
        """Check if server is reachable."""
        try:
            resp = _get_session(self.server_url).get(f"{self.server_url}/", timeout=5)
            print(f"Server connected: {self.server_url}")
        except requests.exceptions.ConnectionError:
            print(f"Cannot connect to {self.server_url}")
            print("Hint: Check if SSH port forwarding is set up:")
            print("  ssh -L 5001:localhost:5001 <user>@<server-ip>")
        except requests.exceptions.Timeout:
            print(f"Connection timeout: {self.server_url}")
        except Exception as e:
            print(f"Connection error: {e}")

    def _parse_response(self, response: requests.Response, context: str = "") -> dict:
        """Parse JSON response safely with detailed error info."""
        try:
            return response.json()
        except json.JSONDecodeError as e:
            # Print raw response for debugging
            raw_text = response.text[:500] if response.text else "(empty)"
            status_code = response.status_code
            print(f"\nJSON parse error in {context}")
            print(f"Status: {status_code}")
            print(f"Response preview:\n{raw_text}")
            raise ValueError(
                f"Server returned non-JSON response (status={status_code}). "
                f"First 200 chars: {raw_text[:200]}"
            ) from e

    def _load_tasks(self) -> Dict:
        if self.tasks_file.exists():
            return json.loads(self.tasks_file.read_text())
        return {}

    def _save_tasks(self, tasks: Dict):
        self.tasks_file.write_text(json.dumps(tasks, indent=2, ensure_ascii=False))

    def submit(
        self,
        image_path: Union[str, Path],
        name: Optional[str] = None,
        config: Optional[Union[str, Path, Dict]] = None,
        layers: Optional[int] = None,
        save_path: Optional[Union[str, Path]] = None,
    ) -> str:
        """Submit an image processing task.

        Args:
            image_path: Input image path
            name: Task name, default image filename
            config: Config as JSON file path or dict
            layers: Number of layers (2-10), overrides config
            save_path: Output save path

        Returns:
            task_id: Task ID
        """
        image_path = Path(image_path)

        if config is None and layers is None:
            raise ValueError("At least one of config or layers is required")

        if not image_path.exists():
            raise ValueError(f"Image not found: {image_path}")

        if layers is not None and not (2 <= layers <= 10):
            raise ValueError(f"layers must be 2-10, got: {layers}")

        final_config = {}
        if config is not None:
            if isinstance(config, dict):
                final_config = config.copy()
            else:
                config_path = Path(config)
                if not config_path.exists():
                    raise ValueError(f"Config file not found: {config}")
                final_config = json.loads(config_path.read_text())

        if layers is not None:
            final_config["layers"] = layers

        if "layers" in final_config and not (2 <= final_config["layers"] <= 10):
            raise ValueError(f"layers must be 2-10, got: {final_config['layers']}")

        task_name = name or image_path.stem

        import mimetypes
        mime_type = mimetypes.guess_type(str(image_path))[0] or "application/octet-stream"

        try:
            with open(image_path, "rb") as f:
                files = {"image": (image_path.name, f, mime_type)}
                data = {
                    "name": task_name,
                    "config": json.dumps(final_config) if final_config else None,
                }
                response = _get_session(self.server_url).post(
                    f"{self.server_url}/submit",
                    files=files,
                    data=data,
                )

            result = self._parse_response(response, "submit")

            if "error" in result:
                raise ValueError(f"Server error: {result['error']}")

            tasks = self._load_tasks()
            tasks[result["task_id"]] = {
                "name": task_name,
                "image_path": str(image_path.absolute()),
                "config": final_config,
                "created_at": datetime.now().isoformat(),
                "status": "queued",
                "downloaded": False,
                "save_path": str(Path(save_path).absolute()) if save_path else None,
            }
            self._save_tasks(tasks)

            return result["task_id"]

        except requests.exceptions.ConnectionError:
            raise ConnectionError("Cannot connect to server, check SSH port forwarding")

    def query(self, task_id: str) -> Dict:
        """Query task status and update local record."""
        try:
            response = _get_session(self.server_url).get(
                f"{self.server_url}/query/{task_id}"
            )
            result = self._parse_response(response, f"query/{task_id}")

            tasks = self._load_tasks()
            if task_id in tasks:
                tasks[task_id].update({
                    "status": result.get("status"),
                    "start_time": result.get("start_time"),
                    "end_time": result.get("end_time"),
                    "layers_count": result.get("layers_count"),
                    "error": result.get("error"),
                })
                tasks[task_id] = {k: v for k, v in tasks[task_id].items() if v is not None}
                self._save_tasks(tasks)

            return result

        except requests.exceptions.ConnectionError:
            raise ConnectionError("Cannot connect to server")

    def get(self, task_id: str) -> Optional[Path]:
        """Download results to local.

        Returns:
            Output directory path, or None if task not completed.
        """
        tasks = self._load_tasks()

        if task_id not in tasks:
            try:
                result = self.query(task_id)
                if result.get("status") == "not_found":
                    raise ValueError("Task not found on server")
                tasks = self._load_tasks()
            except ConnectionError:
                raise

        task_record = tasks.get(task_id, {})
        task_name = task_record.get("name", task_id[:8])
        save_path = task_record.get("save_path")
        image_path = task_record.get("image_path")

        try:
            status = self.query(task_id)

            if status.get("status") != "completed":
                return None

            if save_path:
                base_dir = Path(save_path)
            else:
                base_dir = Path(image_path).parent / "decomposed"
            output_dir = base_dir / task_name
            if output_dir.exists():
                print(f"Warning: directory {output_dir} exists, removing...")
                shutil.rmtree(output_dir)
            output_dir.mkdir(parents=True)

            response = _get_session(self.server_url).get(
                f"{self.server_url}/get/{task_id}"
            )

            content_type = response.headers.get("content-type", "")
            if "application/zip" in content_type:
                zip_path = output_dir / "result.zip"
                zip_path.write_bytes(response.content)

                with zipfile.ZipFile(zip_path, "r") as zf:
                    zf.extractall(output_dir)
                zip_path.unlink()

                # Rename: 1.png -> <name>_d0.png, 2.png -> <name>_d1.png
                png_files = sorted(output_dir.glob("*.png"))
                for idx, old_file in enumerate(png_files):
                    old_file.rename(output_dir / f"{task_name}_d{idx}.png")

                tasks = self._load_tasks()
                tasks[task_id]["downloaded"] = True
                tasks[task_id]["output_dir"] = str(output_dir)
                self._save_tasks(tasks)

                return output_dir
            else:
                error = self._parse_response(response, f"get/{task_id}")
                raise ValueError(f"Download failed: {error.get('error', 'Unknown error')}")

        except requests.exceptions.ConnectionError:
            raise ConnectionError("Cannot connect to server")

    def list(self) -> Dict[str, Dict]:
        """List all locally recorded tasks."""
        return self._load_tasks()

    def list_images(self, task_id: str) -> List[Path]:
        """Get output image paths for a task."""
        tasks = self._load_tasks()
        if task_id not in tasks:
            return []

        output_dir = tasks[task_id].get("output_dir")
        if not output_dir:
            return []

        output_path = Path(output_dir)
        if not output_path.exists():
            return []

        return sorted(output_path.glob("*.png"))

    def decompose(
        self,
        image_path: Union[str, Path],
        name: Optional[str] = None,
        config: Optional[Union[str, Path, Dict]] = None,
        layers: Optional[int] = None,
        save_path: Optional[Union[str, Path]] = None,
        poll_interval: float = DefaultConfig.POLL_INTERVAL,
        timeout: float = DefaultConfig.TIMEOUT,
        verbose: bool = True,
    ) -> Optional[Path]:
        """Blocking layer decomposition: auto submit -> poll -> get."""
        task_id = self.submit(image_path, name, config, layers, save_path)
        if verbose:
            print(f"Task submitted: {task_id}")

        start_time = time.time()
        last_status = None

        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                raise TimeoutError(f"Task {task_id} timed out after {timeout}s")

            result = self.query(task_id)
            status = result.get("status", "unknown")

            if verbose and status != last_status:
                print(f"Status: {status}")
                last_status = status

            if status == "completed":
                break
            elif status == "failed":
                raise ValueError(f"Task failed: {result.get('error', 'Unknown error')}")
            else:
                time.sleep(poll_interval)

        if verbose:
            print("Downloading results...")

        output_dir = self.get(task_id)

        if verbose and output_dir:
            print(f"Done! Output: {output_dir}")
            for f in sorted(output_dir.glob("*.png")):
                print(f"  - {f.name}")

        return output_dir


# ============ CLI Commands ============

_default_client = None


def _get_client() -> QwenImageLayeredClient:
    global _default_client
    if _default_client is None:
        _default_client = QwenImageLayeredClient()
    return _default_client


@cli_app.command()
def submit(
    image_path: Path = typer.Option(..., "--image_path", help="Input image path"),
    name: Optional[str] = typer.Option(None, "--name", help="Task name, default image filename"),
    config: Optional[Path] = typer.Option(None, "--config", help="Config file path (JSON)"),
    layers: Optional[int] = typer.Option(None, "--layers", help="Number of layers"),
    save_path: Optional[Path] = typer.Option(None, "--save_path", help="Output save path"),
):
    """Submit an image processing task."""
    client = _get_client()
    try:
        task_id = client.submit(image_path, name, config, layers, save_path)
        typer.echo(f"Task submitted successfully!")
        typer.echo(f"  Task ID:  {task_id}")
        typer.echo(f"  Name:     {name or image_path.stem}")
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except ConnectionError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@cli_app.command()
def query(task_id: str):
    """Query task status and update local record."""
    client = _get_client()
    try:
        result = client.query(task_id)

        typer.echo(f"Task ID: {task_id}")
        typer.echo(f"Status:  {result.get('status', 'unknown')}")

        if result.get("name"):
            typer.echo(f"Name:    {result['name']}")
        if result.get("start_time"):
            typer.echo(f"Started: {result['start_time']}")
        if result.get("end_time"):
            typer.echo(f"Ended:   {result['end_time']}")
        if result.get("layers_count"):
            typer.echo(f"Layers:  {result['layers_count']}")
        if result.get("error"):
            typer.echo(f"Error:   {result['error']}", err=True)

    except ConnectionError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@cli_app.command()
def get(task_id: str):
    """Download results to local."""
    client = _get_client()
    try:
        output_dir = client.get(task_id)

        if output_dir is None:
            status = client.query(task_id)
            typer.echo(f"Task not completed. Current status: {status.get('status')}")
            if status.get("status") == "failed":
                typer.echo(f"Error: {status.get('error')}", err=True)
            return

        typer.echo(f"Results saved to: {output_dir}")
        for f in sorted(output_dir.glob("*.png")):
            typer.echo(f"  - {f.name}")

    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except ConnectionError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@cli_app.command()
def decompose(
    image_path: Path = typer.Argument(help="Input image path"),
    name: Optional[str] = typer.Option(None, "--name", help="Task name, default image filename"),
    config: Optional[Path] = typer.Option(None, "--config", help="Config file path (JSON)"),
    layers: Optional[int] = typer.Option(None, "--layers", help="Number of layers"),
    save_path: Optional[Path] = typer.Option(None, "--save_path", help="Output save path"),
    timeout: float = typer.Option(DefaultConfig.TIMEOUT, "--timeout", help="Timeout in seconds"),
):
    """Blocking layer decomposition: auto submit, poll, download."""
    client = _get_client()
    try:
        output_dir = client.decompose(
            image_path,
            name,
            config,
            layers,
            save_path,
            timeout=timeout,
            verbose=True,
        )

        if not output_dir:
            typer.echo("Failed to get results", err=True)
            raise typer.Exit(1)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except ConnectionError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except TimeoutError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@cli_app.command(name="list")
def list_tasks():
    """List all locally recorded tasks."""
    client = _get_client()
    tasks = client.list()

    if not tasks:
        typer.echo("No tasks recorded.")
        return

    typer.echo(f"{'STATUS':<12} {'TASK_ID':<10} {'NAME':<20} {'DOWNLOADED'}")
    typer.echo("-" * 60)

    for task_id, record in tasks.items():
        status = record.get("status", "unknown")
        name = record.get("name", "unnamed")[:18]
        downloaded = "Yes" if record.get("downloaded") else "No"
        typer.echo(f"{status:<12} {task_id[:8]:<10} {name:<20} {downloaded}")


def cmd_decompose(
    image_path: Path = typer.Argument(help="Input image path"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Output name, default image filename"),
    layers: int = typer.Option(DefaultConfig.LAYERS, "--layers", "-l", help="Number of layers (2-10)"),
    save_path: Optional[Path] = typer.Option(None, "--save-path", "-s", help="Output directory"),
    timeout: float = typer.Option(DefaultConfig.TIMEOUT, "--timeout", "-t", help="Timeout in seconds"),
):
    """Layer decomposition: auto submit, poll, download."""
    try:
        paths = _decompose_standalone(
            image_path=str(image_path),
            layers=layers,
            name=name,
            save_path=str(save_path) if save_path else None,
            timeout=timeout,
        )
    except (ValueError, ConnectionError, TimeoutError) as e:
        print(f"Error: {e}")
        raise typer.Exit(1)


if __name__ == "__main__":
    cli_app()
