import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studynote.ai.credentials import KeyStore
from studynote.ai.legacy_dpapi import _crypt


class MemoryBackend:
    def __init__(self):
        self.values = {}

    def read(self, target):
        return self.values.get(target)

    def write(self, target, secret):
        self.values[target] = secret

    def delete(self, target):
        self.values.pop(target, None)


class CredentialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.backend = MemoryBackend()
        self.keys = KeyStore(self.root, self.backend)

    def tearDown(self):
        self.temp.cleanup()

    def test_workspace_identity_is_stable_and_isolated(self):
        self.keys.save("test-key")
        self.assertEqual(KeyStore(self.root / '.', self.backend).load(), "test-key")
        other = KeyStore(self.root / 'restored', self.backend)
        self.assertFalse(other.is_configured())
        self.assertNotEqual(self.keys.target, other.target)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_migration_removes_legacy_file_only_after_system_write_succeeds(self):
        self.keys.path.write_bytes(b'legacy-placeholder')
        with patch('studynote.ai.credentials._crypt', return_value=b'legacy-key'):
            with patch.object(self.backend, 'write', side_effect=RuntimeError('store unavailable')):
                with self.assertRaises(RuntimeError):
                    self.keys.load()
            self.assertTrue(self.keys.path.exists())
            self.assertEqual(self.keys.load(), 'legacy-key')
        self.assertFalse(self.keys.path.exists())
        self.assertEqual(self.keys.load(), 'legacy-key')

    def test_invalid_or_oversized_keys_leave_existing_credential_unchanged(self):
        self.keys.save('previous-key')
        for key in ['', 'contains whitespace', 'a' * 2561]:
            with self.assertRaises(ValueError):
                self.keys.save(key)
        self.assertEqual(self.keys.load(), 'previous-key')

    def test_delete_does_not_touch_other_workspaces(self):
        other = KeyStore(self.root / 'other', self.backend)
        self.keys.save('first-key');other.save('second-key')
        self.keys.delete();self.keys.delete()
        self.assertFalse(self.keys.is_configured())
        self.assertEqual(other.load(), 'second-key')

    @unittest.skipUnless(os.name == 'nt', 'Windows DPAPI migration')
    def test_actual_dpapi_file_migrates_to_windows_credential_manager(self):
        keys = KeyStore(self.root)
        try:
            keys.path.write_bytes(_crypt(b'legacy-windows-test-key'))
            self.assertTrue(keys.is_configured())
            self.assertEqual(keys.load(), 'legacy-windows-test-key')
            self.assertFalse(keys.path.exists())
            self.assertEqual(KeyStore(self.root).load(), 'legacy-windows-test-key')
        finally:
            keys.delete()
