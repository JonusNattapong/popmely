import unittest
import popmely
from popmely.server import mcp

class TestPopmelyMCPServer(unittest.TestCase):
    def test_version(self):
        self.assertEqual(popmely.__version__, "3.1.0")

    def test_server_initialized(self):
        self.assertIsNotNone(mcp)
        self.assertEqual(mcp.name, "popmely-mt5-trading")

if __name__ == "__main__":
    unittest.main()
