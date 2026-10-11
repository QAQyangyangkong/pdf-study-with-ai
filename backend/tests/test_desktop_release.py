"""Verify standalone release staging with real files, without launching a GUI."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/release/stage_desktop.py"
SPEC = importlib.util.spec_from_file_location("stage_desktop", SCRIPT)
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class DesktopReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "构建输出"
        self.source.mkdir()
        self.desktop = self.source / "studynote-desktop.exe"
        self.backend = self.source / "studynote-backend.exe"
        self.desktop.write_bytes(b"desktop\x00\xff-binary")
        self.backend.write_bytes(b"backend\x00\x80-binary")
        self.readme = self.root / "README.md"
        self.readme.write_text(
            "# StudyNote\n\n## 普通用户使用教程\n\n双击 StudyNote.exe。\n"
            "点击先离线使用。\n\n## 开发者说明：环境与启动\n\npnpm dev\n",
            encoding="utf-8")
        self.output = self.root / "StudyNote"

    def tearDown(self):
        self.temporary.cleanup()

    def installer(self):
        installer = self.source / "StudyNote_0.2.0_x64-setup.exe"
        installer.write_bytes(b"installer\x00\xff-content")
        return installer

    def test_portable_renames_exact_binaries_writes_bom_guide_and_preserves_unrelated_files(self):
        (self.source / "study.sqlite3").write_bytes(b"private database")
        (self.source / "api-key.dpapi").write_bytes(b"private encrypted key")
        (self.source / "source.py").write_text("source", encoding="utf-8")
        self.output.mkdir()
        unrelated = self.output / "我的资料.txt"
        unrelated.write_bytes(b"existing user file")
        result = release.stage_portable(self.source, self.output, self.readme)
        self.assertEqual(result, (self.output / "StudyNote.exe").resolve())
        self.assertEqual(result.read_bytes(), self.desktop.read_bytes())
        self.assertEqual((self.output / "studynote-backend.exe").read_bytes(), self.backend.read_bytes())
        self.assertEqual(unrelated.read_bytes(), b"existing user file")
        self.assertEqual({path.name for path in self.output.iterdir()},
                         {"StudyNote.exe", "studynote-backend.exe", "使用说明.txt", "我的资料.txt"})
        guide = (self.output / "使用说明.txt").read_bytes()
        self.assertTrue(guide.startswith(b"\xef\xbb\xbf"))
        text = guide.decode("utf-8-sig")
        self.assertIn("点击先离线使用", text)
        self.assertNotIn("开发者说明", text)
        self.assertNotIn("pnpm", text)
        self.assertTrue(self.desktop.exists())
        self.assertTrue(self.backend.exists())

    def test_missing_backend_never_creates_or_replaces_partial_output(self):
        self.backend.unlink()
        with self.assertRaisesRegex(ValueError, "后台程序"):
            release.stage_portable(self.source, self.output, self.readme)
        self.assertFalse(self.output.exists())
        self.output.mkdir()
        existing = self.output / "StudyNote.exe"
        existing.write_bytes(b"previous complete release")
        unrelated = self.output / "资料.txt"
        unrelated.write_bytes(b"keep me")
        with self.assertRaisesRegex(ValueError, "后台程序"):
            release.stage_portable(self.source, self.output, self.readme)
        self.assertEqual(existing.read_bytes(), b"previous complete release")
        self.assertEqual(unrelated.read_bytes(), b"keep me")
        self.assertEqual({file.name for file in self.output.iterdir()}, {"StudyNote.exe", "资料.txt"})

    def test_invalid_guide_is_rejected_before_writing_binaries(self):
        self.readme.write_text("## 开发者说明：环境与启动\nOnly development content", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "分界"):
            release.stage_portable(self.source, self.output, self.readme)
        self.assertFalse(self.output.exists())
        self.assertEqual(self.desktop.read_bytes(), b"desktop\x00\xff-binary")

    def test_installer_verified_copy_removes_only_input_file(self):
        source = self.installer()
        contents = source.read_bytes()
        output = self.output / "installers"
        output.mkdir(parents=True)
        unrelated = output / "历史说明.txt"
        unrelated.write_bytes(b"preserve unrelated file")
        result = release.stage_installer(source, output)
        self.assertEqual(result, (output / source.name).resolve())
        self.assertEqual(result.read_bytes(), contents)
        self.assertFalse(source.exists())
        self.assertTrue(self.source.is_dir())
        self.assertTrue(self.desktop.exists())
        self.assertTrue(self.backend.exists())
        self.assertEqual(unrelated.read_bytes(), b"preserve unrelated file")
        self.assertEqual({path.name for path in output.iterdir()}, {source.name, unrelated.name})

    def test_installer_inputs_must_match_both_delivered_files_without_modifying_them(self):
        release.stage_portable(self.source, self.output, self.readme)
        # The bundler may read its backend from a different directory than the GUI.
        backend_input = self.root / "external-bin.exe"
        backend_input.write_bytes(self.backend.read_bytes())
        expected = {path.name: path.read_bytes() for path in self.output.iterdir()}
        self.assertEqual(release.verify_portable(self.desktop, backend_input, self.output),
                         (self.output / "StudyNote.exe").resolve())
        for source in (self.desktop, backend_input):
            with self.subTest(source=source.name):
                original = source.read_bytes()
                source.write_bytes(bytes([original[0] ^ 1]) + original[1:])
                with self.assertRaisesRegex(RuntimeError, "不一致"):
                    release.verify_portable(self.desktop, backend_input, self.output)
                source.write_bytes(original)
        backend_input.unlink()
        with self.assertRaisesRegex(ValueError, "安装包输入程序"):
            release.verify_portable(self.desktop, backend_input, self.output)
        self.assertEqual({path.name: path.read_bytes() for path in self.output.iterdir()}, expected)

    def test_installer_copy_or_verification_failure_preserves_original_and_unrelated_files(self):
        source = self.installer()
        contents = source.read_bytes()
        output = self.output / "installers"
        output.mkdir(parents=True)
        previous = output / source.name
        previous.write_bytes(b"previous installer")
        unrelated = output / "资料.txt"
        unrelated.write_bytes(b"keep")

        def failed_copy(original, destination):
            Path(destination).write_bytes(b"incomplete copy")
            raise OSError("simulated copy failure")

        with patch.object(release.shutil, "copyfile", side_effect=failed_copy):
            with self.assertRaisesRegex(OSError, "simulated copy failure"):
                release.stage_installer(source, output)
        self.assertEqual(source.read_bytes(), contents)
        self.assertEqual(previous.read_bytes(), b"previous installer")
        with patch.object(release, "_same_bytes", side_effect=[True, False]):
            with self.assertRaisesRegex(RuntimeError, "校验失败"):
                release.stage_installer(source, output)
        self.assertEqual(source.read_bytes(), contents)
        self.assertEqual(unrelated.read_bytes(), b"keep")
        self.assertFalse(list(output.glob(".studynote-stage-*")))
        with self.assertRaisesRegex(ValueError, "唯一的原文件"):
            release.stage_installer(source, self.source)
        self.assertEqual(source.read_bytes(), contents)

    def test_cli_prints_absolute_path_and_returns_nonzero_for_missing_inputs(self):
        environment = {**os.environ, "PYTHONUTF8": "1"}
        command = [sys.executable, str(SCRIPT)]
        portable_args = ["portable", "--source", str(self.source), "--output", str(self.output),
                         "--readme", str(self.readme)]
        success = subprocess.run(command + portable_args, capture_output=True, text=True,
                                 encoding="utf-8", env=environment)
        self.assertEqual(success.returncode, 0, success.stderr)
        self.assertEqual(success.stdout.strip(), str((self.output / "StudyNote.exe").resolve()))
        verify_args = ["verify", "--desktop", str(self.desktop), "--backend", str(self.backend),
                       "--output", str(self.output)]
        verified = subprocess.run(command + verify_args, capture_output=True, text=True,
                                  encoding="utf-8", env=environment)
        self.assertEqual(verified.returncode, 0, verified.stderr)
        self.backend.write_bytes(b"new unverified backend")
        mismatch = subprocess.run(command + verify_args, capture_output=True, text=True,
                                  encoding="utf-8", env=environment)
        self.assertNotEqual(mismatch.returncode, 0)
        self.assertIn("不一致", mismatch.stderr)
        self.backend.unlink()
        missing_backend = subprocess.run(command + portable_args, capture_output=True, text=True,
                                         encoding="utf-8", env=environment)
        self.assertNotEqual(missing_backend.returncode, 0)
        self.assertIn("发布失败", missing_backend.stderr)
        self.assertIn("后台程序", missing_backend.stderr)
        self.assertEqual(missing_backend.stdout, "")
        missing_installer = subprocess.run(
            command + ["installer", "--source", str(self.source / "missing.exe"),
                       "--output", str(self.output / "installers")],
            capture_output=True, text=True, encoding="utf-8", env=environment)
        self.assertNotEqual(missing_installer.returncode, 0)
        self.assertIn("缺少安装包", missing_installer.stderr)
        self.assertFalse((self.output / "installers").exists())


if __name__ == "__main__":
    unittest.main()
