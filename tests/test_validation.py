from __future__ import annotations

import unittest
from pathlib import Path

from zeus_plugins.validation import _validate_prerequisites


class PrerequisiteValidationTests(unittest.TestCase):
    def test_new_install_options_shape_passes(self) -> None:
        manifest = {
            "prerequisites": {
                "cli": [
                    {
                        "id": "github_cli",
                        "name": "GitHub CLI",
                        "binary": "gh",
                        "required": True,
                        "why": "Needed for repository operations.",
                        "check_command": "gh --version",
                        "install_options": [
                            {
                                "type": "shell",
                                "label": "Install with Homebrew",
                                "command": "brew install gh",
                                "auto_run": True,
                                "requires_admin": False,
                                "platforms": ["darwin"],
                            },
                            {
                                "type": "open_url",
                                "label": "Open install docs",
                                "url": "https://cli.github.com/",
                            },
                        ],
                    }
                ]
            }
        }

        issues = _validate_prerequisites(manifest, Path("/tmp/plugin/zeus.plugin.json"))
        self.assertEqual(issues, [])

    def test_legacy_install_fields_still_pass(self) -> None:
        manifest = {
            "prerequisites": {
                "cli": [
                    {
                        "name": "Google Workspace CLI",
                        "binary": "gws",
                        "required": True,
                        "auto_install_commands": {
                            "darwin": "npm install -g @googleworkspace/cli",
                        },
                        "install_hint": "npm install -g @googleworkspace/cli",
                        "install_url": "https://github.com/googleworkspace/cli",
                    }
                ]
            }
        }

        issues = _validate_prerequisites(manifest, Path("/tmp/plugin/zeus.plugin.json"))
        self.assertEqual(issues, [])

    def test_invalid_auto_run_admin_shell_is_rejected(self) -> None:
        manifest = {
            "prerequisites": {
                "cli": [
                    {
                        "id": "bad_cli",
                        "name": "Bad CLI",
                        "binary": "bad",
                        "required": True,
                        "install_options": [
                            {
                                "type": "shell",
                                "label": "Install",
                                "command": "sudo installer.sh && echo done",
                                "auto_run": True,
                                "requires_admin": True,
                            }
                        ],
                    }
                ]
            }
        }

        issues = _validate_prerequisites(manifest, Path("/tmp/plugin/zeus.plugin.json"))
        self.assertGreaterEqual(len(issues), 2)
        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("cannot require admin access", messages)
        self.assertIn("single explicit command", messages)


if __name__ == "__main__":
    unittest.main()
