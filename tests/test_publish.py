from __future__ import annotations

import base64
import gzip
import hashlib
import json
import shutil
import tarfile
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from zeus_plugins.publish import generate_registry_keypair, publish_registry


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _copy_schemas(repo_root: Path) -> None:
    target = repo_root / "schemas"
    target.mkdir(parents=True, exist_ok=True)
    for name in ("zeus.plugin.schema.json", "registry.metadata.schema.json"):
        shutil.copyfile(REPO_ROOT / "schemas" / name, target / name)


def _make_plugin(repo_root: Path, plugin_id: str, version: str) -> dict:
    plugin_root = repo_root / "plugins" / plugin_id
    plugin_root.mkdir(parents=True, exist_ok=True)

    manifest = {
        "schema_version": 1,
        "id": plugin_id,
        "name": plugin_id.replace("_", " ").title(),
        "version": version,
        "description": f"{plugin_id} example plugin",
        "components": {
            "client": {
                "runtime": "python",
                "entry": "client/plugin.py",
            }
        },
        "config_schema": {
            "client": {},
            "server": {},
        },
    }
    metadata = {
        "id": plugin_id,
        "name": manifest["name"],
        "version": version,
        "summary": f"{plugin_id} summary for testing publish pipeline.",
        "owner": "tests",
        "runtime": ["client"],
        "categories": ["testing"],
        "min_zeus_version": "1.0.0",
        "source_repo": "https://github.com/example/zeus-plugins",
        "license": "MIT",
    }

    _write_json(plugin_root / "zeus.plugin.json", manifest)
    _write_json(plugin_root / "metadata.json", metadata)
    (plugin_root / "README.md").write_text(f"# {manifest['name']}\n", encoding="utf-8")
    (plugin_root / "client").mkdir(parents=True, exist_ok=True)
    (plugin_root / "client" / "plugin.py").write_text(
        "from __future__ import annotations\n\n"
        "def register_tools():\n"
        "    return {\"ping\": ping}\n\n"
        "def ping(context=None):\n"
        f"    return {{\"ok\": True, \"plugin\": \"{plugin_id}\"}}\n",
        encoding="utf-8",
    )

    return {
        "id": plugin_id,
        "name": metadata["name"],
        "version": version,
        "summary": metadata["summary"],
        "owner": metadata["owner"],
        "runtime": metadata["runtime"],
        "categories": metadata["categories"],
        "min_zeus_version": metadata["min_zeus_version"],
        "source_repo": metadata["source_repo"],
        "license": metadata["license"],
        "metadata_path": f"plugins/{plugin_id}/metadata.json",
        "manifest_path": f"plugins/{plugin_id}/zeus.plugin.json",
    }


class PublishPipelineTests(unittest.TestCase):
    def test_keygen_writes_expected_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = generate_registry_keypair(Path(tmp) / "keys")
            self.assertTrue(Path(payload.private_key_pem_path).exists())
            self.assertTrue(Path(payload.public_key_pem_path).exists())
            self.assertTrue(Path(payload.private_key_base64_path).exists())
            self.assertTrue(Path(payload.public_key_base64_path).exists())
            self.assertTrue(payload.public_key_base64)
            self.assertTrue(payload.private_key_base64)

    def test_publish_registry_writes_signed_static_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            repo_root = tmp_root / "repo"
            repo_root.mkdir(parents=True, exist_ok=True)
            _copy_schemas(repo_root)
            alpha = _make_plugin(repo_root, "alpha_plugin", "1.2.3")
            _make_plugin(repo_root, "beta_plugin", "2.0.0")
            _write_json(repo_root / "index.json", [alpha, {
                "id": "beta_plugin",
                "name": "Beta Plugin",
                "version": "2.0.0",
                "summary": "beta_plugin summary for testing publish pipeline.",
                "owner": "tests",
                "runtime": ["client"],
                "categories": ["testing"],
                "min_zeus_version": "1.0.0",
                "source_repo": "https://github.com/example/zeus-plugins",
                "license": "MIT",
                "metadata_path": "plugins/beta_plugin/metadata.json",
                "manifest_path": "plugins/beta_plugin/zeus.plugin.json",
            }])

            keypair = generate_registry_keypair(tmp_root / "keys")
            result = publish_registry(
                repo_root,
                output_dir=tmp_root / "dist",
                base_url="https://plugins.example.com",
                private_key=Path(keypair.private_key_pem_path),
                plugin_ids=["alpha_plugin"],
                clean=True,
            )

            index_payload = json.loads(Path(result.index_path).read_text(encoding="utf-8"))
            self.assertEqual([entry["id"] for entry in index_payload], ["alpha_plugin"])
            self.assertEqual(len(result.plugins), 1)

            published = result.plugins[0]
            metadata = json.loads(Path(published.metadata_path).read_text(encoding="utf-8"))
            artifact_path = Path(published.artifact_path)
            artifact_bytes = artifact_path.read_bytes()

            self.assertEqual(metadata["id"], "alpha_plugin")
            self.assertEqual(metadata["version"], "1.2.3")
            self.assertEqual(metadata["artifact_url"], "https://plugins.example.com/artifacts/alpha_plugin/1.2.3/alpha_plugin-1.2.3.tgz")
            self.assertEqual(metadata["sha256"], hashlib.sha256(artifact_bytes).hexdigest())
            self.assertEqual(metadata["signature"], published.signature)

            public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(result.public_key_base64))
            public_key.verify(base64.b64decode(metadata["signature"]), artifact_bytes)

            with artifact_path.open("rb") as handle:
                with gzip.GzipFile(fileobj=handle, mode="rb") as gz:
                    with tarfile.open(fileobj=gz, mode="r:") as archive:
                        names = sorted(archive.getnames())
            self.assertIn("alpha_plugin/zeus.plugin.json", names)
            self.assertIn("alpha_plugin/client/plugin.py", names)


if __name__ == "__main__":
    unittest.main()
