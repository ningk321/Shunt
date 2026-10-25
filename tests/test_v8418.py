"""v8.4.18：内嵌模块的字节码缓存（server.py 启动时不再每次重新编译约 50 万字节的内嵌源码）"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests.helper import server

assert server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VER = sys.modules["shunt.base"].PANEL_VERSION  # 版本断言在 tests/test_v8419.py
TAG = sys.implementation.cache_tag


def read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


class CodeCacheTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="shunt-cc-")
        shutil.copy(os.path.join(ROOT, "server.py"), self.dir)
        self.data = tempfile.mkdtemp(prefix="shunt-cc-data-")  # 数据目录单独放：只读测试只锁住程序目录
        with open(os.path.join(self.data, "data.json"), "w") as f:
            f.write("{}")
        self.cache = os.path.join(self.dir, "__pycache__", f"server-embedded.{TAG}.bin")

    def tearDown(self):
        os.chmod(self.dir, 0o755)
        shutil.rmtree(self.dir, ignore_errors=True)
        shutil.rmtree(self.data, ignore_errors=True)

    def run_import(self, **env):
        e = dict(os.environ, PANEL_OFFLINE="1", PANEL_DATA=os.path.join(self.data, "data.json"), MIHOMO_DIR=self.data,
                 PYTHONDONTWRITEBYTECODE="1", **env)
        if "PANEL_NO_CODE_CACHE" not in env:
            e.pop("PANEL_NO_CODE_CACHE", None)
        r = subprocess.run([sys.executable, "-c", "import server; print(server.PANEL_VERSION, server.build_config(server.load())['mode'])"],
                           cwd=self.dir, env=e, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.split(), [VER, "rule"])

    def test_written_then_reused(self):
        self.run_import()
        self.assertTrue(os.path.isfile(self.cache))
        st = os.stat(self.cache).st_mtime_ns
        self.run_import()
        self.assertEqual(os.stat(self.cache).st_mtime_ns, st)  # 命中缓存不重写

    def test_corrupt_cache_recompiled(self):
        os.makedirs(os.path.dirname(self.cache))
        with open(self.cache, "wb") as f:
            f.write(b"garbage\nnot-zlib")
        self.run_import()
        with open(self.cache, "rb") as f:
            self.assertTrue(f.readline().startswith(TAG.encode() + b" "))

    def test_stale_key_recompiled(self):
        self.run_import()
        with open(self.cache, "rb") as f:
            f.readline()
            body = f.read()
        with open(self.cache, "wb") as f:  # 源码变了（校验和不同）：缓存体再完整也不能用
            f.write(f"{TAG} 1 2\n".encode() + body)
        self.run_import()
        with open(self.cache, "rb") as f:
            self.assertNotEqual(f.readline(), f"{TAG} 1 2\n".encode())

    def test_disabled(self):
        self.run_import(PANEL_NO_CODE_CACHE="1")
        self.assertFalse(os.path.exists(self.cache))

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root 不受目录权限限制")
    def test_readonly_dir(self):
        os.chmod(self.dir, 0o555)
        self.run_import()
        self.assertFalse(os.path.exists(self.cache))
        self.assertEqual([x for x in os.listdir(self.dir) if x.endswith(".tmp")], [])

    def test_traceback_keeps_module_lines(self):
        """缓存的字节码保留 shunt/xxx.py 文件名，异常堆栈仍能显示出错的那一行"""
        self.run_import()
        e = dict(os.environ, PANEL_OFFLINE="1", PANEL_DATA=os.path.join(self.data, "data.json"), MIHOMO_DIR=self.data)
        r = subprocess.run([sys.executable, "-c", "import server, traceback\ntry:\n    server.clean_target(1)\nexcept Exception:\n    traceback.print_exc()"],
                           cwd=self.dir, env=e, capture_output=True, text=True, timeout=60)
        self.assertIn('shunt/ruletest.py', r.stderr)
        self.assertIn("t = t.strip()", r.stderr)


if __name__ == "__main__":
    unittest.main()
