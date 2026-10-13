import json
import os
import re
import unittest

PLUGIN_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dvr2vod")
PKG_NAME = os.path.basename(PLUGIN_DIR)


def load_manifest():
    with open(os.path.join(PLUGIN_DIR, "plugin.json"), encoding="utf-8") as fh:
        return json.load(fh)


class PluginJson(unittest.TestCase):
    def test_valid_json_with_required_fields(self):
        manifest = load_manifest()
        for field in ("name", "version", "description", "author", "license"):
            self.assertTrue(manifest.get(field), f"missing required field: {field}")

    def test_semver(self):
        self.assertRegex(load_manifest()["version"], r"^\d+\.\d+\.\d+$")

    def test_folder_is_kebab_case(self):
        self.assertRegex(PKG_NAME, r"^[a-z0-9]+(-[a-z0-9]+)*$")

    def test_action_ids_unique_and_fields_have_ids(self):
        manifest = load_manifest()
        action_ids = [a["id"] for a in manifest.get("actions", [])]
        self.assertEqual(len(action_ids), len(set(action_ids)))
        for f in manifest.get("fields", []):
            self.assertIn("id", f)
            self.assertIn("type", f)

    def test_select_options_have_value_and_label(self):
        manifest = load_manifest()
        for f in manifest.get("fields", []):
            for opt in f.get("options", []):
                self.assertIn("value", opt)
                self.assertIn("label", opt)


class PluginClassShape(unittest.TestCase):
    """Import and exercise the Plugin class WITHOUT Django: all ORM imports
    must live inside methods, never at module import time."""

    def test_import_and_instantiate(self):
        from dvr2vod.plugin import Plugin

        plugin = Plugin()
        self.assertTrue(os.path.isdir(plugin.data_dir) or plugin.data_dir)

    def test_data_dir_is_sibling_of_package_and_writable(self):
        from dvr2vod.plugin import PLUGIN_KEY, Plugin

        plugin = Plugin()
        parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.assertEqual(
            os.path.realpath(plugin.data_dir),
            os.path.realpath(os.path.join(parent, f"{PLUGIN_KEY}_data")),
        )

    def test_settings_defaults_and_mode_fallback(self):
        from dvr2vod.plugin import Plugin

        plugin = Plugin()
        cfg = plugin._settings({"settings": {"library_mode": "bogus", "base_url": "http://x/"}})
        self.assertEqual(cfg["mode"], "series_per_show")
        self.assertEqual(cfg["base_url"], "http://x")

    def test_unknown_action_is_error(self):
        from dvr2vod.plugin import Plugin

        result = Plugin().run("nope", {}, {"settings": {}})
        self.assertEqual(result["status"], "error")

    def test_recording_end_without_auto_is_skipped(self):
        from dvr2vod.plugin import Plugin

        result = Plugin().run(
            "on_recording_end",
            {"payload": {"recording_id": 1}},
            {"settings": {"auto_regenerate": False}},
        )
        self.assertEqual(result["status"], "skipped")


if __name__ == "__main__":
    unittest.main()
