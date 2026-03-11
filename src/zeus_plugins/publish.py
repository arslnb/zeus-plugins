from __future__ import annotations

import base64
import gzip
import hashlib
import io
import json
import shutil
import tarfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
    load_pem_private_key,
)

from zeus_plugins.validation import Issue, validate_plugin_folder, validate_registry


_ARTIFACT_PREFIX = "artifacts"
_METADATA_PREFIX = "plugins"
_SKIP_NAMES = {".DS_Store"}
_SKIP_PARTS = {"__pycache__"}


@dataclass(frozen=True)
class RegistryKeypair:
    private_key_pem_path: str
    public_key_pem_path: str
    private_key_base64_path: str
    public_key_base64_path: str
    private_key_base64: str
    public_key_base64: str


@dataclass(frozen=True)
class PublishedPlugin:
    id: str
    version: str
    artifact_url: str
    artifact_path: str
    metadata_path: str
    sha256: str
    signature: str


@dataclass(frozen=True)
class PublishResult:
    output_dir: str
    index_path: str
    public_key_base64: str
    public_key_base64_path: str
    public_key_pem_path: str
    plugins: list[PublishedPlugin]


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _format_issues(issues: list[Issue]) -> str:
    return "\n".join(f"[{issue.code}] {issue.path}: {issue.message}" for issue in issues)


def _load_private_key(value: str | Path) -> Ed25519PrivateKey:
    if isinstance(value, Path):
        raw = value.read_bytes()
        text = raw.decode("utf-8", errors="ignore").strip()
    else:
        candidate_path = Path(str(value)).expanduser()
        if candidate_path.exists():
            raw = candidate_path.read_bytes()
            text = raw.decode("utf-8", errors="ignore").strip()
        else:
            raw = str(value).encode("utf-8")
            text = str(value).strip()

    if text.startswith("-----BEGIN"):
        loaded = load_pem_private_key(raw, password=None)
        if not isinstance(loaded, Ed25519PrivateKey):
            raise RuntimeError("registry private key must be Ed25519")
        return loaded

    try:
        private_bytes = base64.b64decode(text)
        return Ed25519PrivateKey.from_private_bytes(private_bytes)
    except Exception as exc:  # pragma: no cover - exercised via CLI/manual misuse
        raise RuntimeError("registry private key must be raw base64 bytes or PEM") from exc


def _public_key_material(private_key: Ed25519PrivateKey) -> tuple[str, bytes]:
    public_key = private_key.public_key()
    public_key_raw = public_key.public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw)
    public_key_pem = public_key.public_bytes(encoding=Encoding.PEM, format=PublicFormat.SubjectPublicKeyInfo)
    return base64.b64encode(public_key_raw).decode("utf-8"), public_key_pem


def generate_registry_keypair(output_dir: Path, *, force: bool = False) -> RegistryKeypair:
    output_root = output_dir.expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_pem_path = output_root / "ed25519-private.pem"
    public_pem_path = output_root / "ed25519-public.pem"
    private_b64_path = output_root / "ed25519-private.b64"
    public_b64_path = output_root / "ed25519-public.b64"
    paths = [private_pem_path, public_pem_path, private_b64_path, public_b64_path]
    if not force:
        existing = [path for path in paths if path.exists()]
        if existing:
            joined = ", ".join(str(path) for path in existing)
            raise RuntimeError(f"refusing to overwrite existing key files: {joined}")

    private_raw = private_key.private_bytes(
        encoding=Encoding.Raw,
        format=PrivateFormat.Raw,
        encryption_algorithm=NoEncryption(),
    )
    public_raw = public_key.public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw)
    private_pem = private_key.private_bytes(
        encoding=Encoding.PEM,
        format=PrivateFormat.PKCS8,
        encryption_algorithm=NoEncryption(),
    )
    public_pem = public_key.public_bytes(encoding=Encoding.PEM, format=PublicFormat.SubjectPublicKeyInfo)

    private_pem_path.write_bytes(private_pem)
    public_pem_path.write_bytes(public_pem)
    private_b64_path.write_text(base64.b64encode(private_raw).decode("utf-8") + "\n", encoding="utf-8")
    public_b64_path.write_text(base64.b64encode(public_raw).decode("utf-8") + "\n", encoding="utf-8")

    return RegistryKeypair(
        private_key_pem_path=str(private_pem_path),
        public_key_pem_path=str(public_pem_path),
        private_key_base64_path=str(private_b64_path),
        public_key_base64_path=str(public_b64_path),
        private_key_base64=base64.b64encode(private_raw).decode("utf-8"),
        public_key_base64=base64.b64encode(public_raw).decode("utf-8"),
    )


def _approved_entries(repo_root: Path) -> list[dict[str, Any]]:
    payload = _load_json(repo_root / "index.json")
    if not isinstance(payload, list):
        raise RuntimeError("index.json must be an array")
    return [entry for entry in payload if isinstance(entry, dict)]


def _selected_entries(repo_root: Path, plugin_ids: list[str] | None) -> list[dict[str, Any]]:
    entries = _approved_entries(repo_root)
    if not plugin_ids:
        return entries

    wanted = {plugin_id.strip() for plugin_id in plugin_ids if plugin_id.strip()}
    selected = [entry for entry in entries if str(entry.get("id") or "").strip() in wanted]
    found = {str(entry.get("id") or "").strip() for entry in selected}
    missing = sorted(wanted - found)
    if missing:
        raise RuntimeError(f"plugin ids not found in index.json: {', '.join(missing)}")
    return selected


def _validate_publish_inputs(repo_root: Path, entries: list[dict[str, Any]], *, full_registry: bool) -> None:
    if full_registry:
        issues = validate_registry(repo_root)
        if issues:
            raise RuntimeError(_format_issues(issues))
        return

    issues: list[Issue] = []
    for entry in entries:
        manifest_path = str(entry.get("manifest_path") or "").strip()
        if not manifest_path:
            issues.append(Issue(code="INDEX", message="manifest_path is required", path="index.json"))
            continue
        plugin_dir = (repo_root / manifest_path).parent
        issues.extend(validate_plugin_folder(repo_root, plugin_dir))
    if issues:
        raise RuntimeError(_format_issues(issues))


def _iter_plugin_files(plugin_dir: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(plugin_dir.rglob("*")):
        rel_parts = set(path.relative_to(plugin_dir).parts)
        if rel_parts & _SKIP_PARTS:
            continue
        if path.name in _SKIP_NAMES:
            continue
        if path.is_dir():
            continue
        if path.suffix == ".pyc":
            continue
        if path.is_symlink():
            raise RuntimeError(f"plugin packaging does not allow symlinks: {path}")
        files.append(path)
    return files


def _build_plugin_artifact(plugin_id: str, plugin_dir: Path) -> bytes:
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0) as gzip_file:
        with tarfile.open(fileobj=gzip_file, mode="w") as archive:
            root_prefix = PurePosixPath(plugin_id)
            for source_path in _iter_plugin_files(plugin_dir):
                relative = source_path.relative_to(plugin_dir).as_posix()
                arcname = str(root_prefix / relative)
                stat = source_path.stat()
                tarinfo = tarfile.TarInfo(name=arcname)
                tarinfo.size = stat.st_size
                tarinfo.mtime = 0
                tarinfo.uid = 0
                tarinfo.gid = 0
                tarinfo.uname = ""
                tarinfo.gname = ""
                tarinfo.mode = 0o755 if (stat.st_mode & 0o111) else 0o644
                with source_path.open("rb") as handle:
                    archive.addfile(tarinfo, handle)
    return buffer.getvalue()


def publish_registry(
    repo_root: Path,
    *,
    output_dir: Path,
    base_url: str,
    private_key: str | Path,
    plugin_ids: list[str] | None = None,
    clean: bool = False,
) -> PublishResult:
    registry_root = repo_root.expanduser().resolve()
    destination = output_dir.expanduser().resolve()
    normalized_base_url = str(base_url or "").strip().rstrip("/")
    if not normalized_base_url.startswith(("http://", "https://")):
        raise RuntimeError("base_url must start with http:// or https://")

    selected_entries = _selected_entries(registry_root, plugin_ids)
    _validate_publish_inputs(registry_root, selected_entries, full_registry=not plugin_ids)

    if clean and destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)

    signing_key = _load_private_key(private_key)
    public_key_b64, public_key_pem = _public_key_material(signing_key)
    public_key_b64_path = destination / "registry-public-key.b64"
    public_key_pem_path = destination / "registry-public-key.pem"
    public_key_b64_path.write_text(public_key_b64 + "\n", encoding="utf-8")
    public_key_pem_path.write_bytes(public_key_pem)

    published_plugins: list[PublishedPlugin] = []
    published_index: list[dict[str, Any]] = []
    published_at = datetime.now(timezone.utc).isoformat()

    for entry in selected_entries:
        plugin_id = str(entry.get("id") or "").strip()
        manifest_path = registry_root / str(entry.get("manifest_path") or "").strip()
        metadata_path = registry_root / str(entry.get("metadata_path") or "").strip()
        plugin_dir = manifest_path.parent
        metadata = _load_json(metadata_path)
        manifest = _load_json(manifest_path)
        version = str(metadata.get("version") or manifest.get("version") or "").strip()
        if not version:
            raise RuntimeError(f"plugin '{plugin_id}' is missing version")

        artifact_bytes = _build_plugin_artifact(plugin_id, plugin_dir)
        sha256 = hashlib.sha256(artifact_bytes).hexdigest()
        signature = base64.b64encode(signing_key.sign(artifact_bytes)).decode("utf-8")

        artifact_relative = Path(_ARTIFACT_PREFIX) / plugin_id / version / f"{plugin_id}-{version}.tgz"
        artifact_path = destination / artifact_relative
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_bytes(artifact_bytes)

        metadata_relative = Path(_METADATA_PREFIX) / plugin_id / f"{version}.json"
        published_metadata = dict(metadata)
        published_metadata.update(
            {
                "artifact_url": f"{normalized_base_url}/{artifact_relative.as_posix()}",
                "sha256": sha256,
                "signature": signature,
                "published_at": published_at,
            }
        )
        _write_json(destination / metadata_relative, published_metadata)
        published_plugins.append(
            PublishedPlugin(
                id=plugin_id,
                version=version,
                artifact_url=published_metadata["artifact_url"],
                artifact_path=str(artifact_path),
                metadata_path=str(destination / metadata_relative),
                sha256=sha256,
                signature=signature,
            )
        )
        published_index.append(dict(entry))

    _write_json(destination / "index.json", published_index)

    return PublishResult(
        output_dir=str(destination),
        index_path=str(destination / "index.json"),
        public_key_base64=public_key_b64,
        public_key_base64_path=str(public_key_b64_path),
        public_key_pem_path=str(public_key_pem_path),
        plugins=published_plugins,
    )


def registry_keypair_to_json(payload: RegistryKeypair) -> dict[str, Any]:
    return asdict(payload)


def publish_result_to_json(payload: PublishResult) -> dict[str, Any]:
    serialized = asdict(payload)
    serialized["plugins"] = [asdict(item) for item in payload.plugins]
    return serialized
