"""v8.4.19：广告列表里的元素隐藏规则（baike.baidu.com##.ad）不再被当成拦截整个网站"""
import json
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

from tests.helper import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VER = "8.4.19"
AB = sys.modules["shunt.adblock"]
SC = sys.modules["shunt.schedule"]


def read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


class VersionTest(unittest.TestCase):
    def test_version(self):
        self.assertEqual(sys.modules["shunt.base"].PANEL_VERSION, VER)

    def test_changelog_top(self):
        heads = [ln for ln in read("CHANGELOG.md").splitlines() if ln.startswith("## v")]
        self.assertTrue(heads[0].startswith("## v" + VER), heads[0])


class CosmeticTest(unittest.TestCase):
    def test_cosmetic_rules_skipped(self):
        text = "\n".join([
            "baike.baidu.com##.pinzhuanWrap",
            "baike.baidu.com###J-union-wrapper",
            "mbd.baidu.com#@#.ad",
            "zhidao.baidu.com#?#div:has(> .ad)",
            "tieba.baidu.com#$#body { overflow: auto !important; }",
            "www.163.com#%#//scriptlet('abort-on-property-read', 'ad')",
            "news.qq.com#@?#.x",
            "||ads.example.com^",
            "0.0.0.0 tracker.example.org # hosts 注释",
            "plain-ad.example.cn",
        ])
        bs, be, as_, ae, skipped = server.parse_filter(text)
        blocked = bs | be
        for host in ("baike.baidu.com", "mbd.baidu.com", "zhidao.baidu.com", "tieba.baidu.com", "www.163.com", "news.qq.com"):
            self.assertNotIn(host, blocked)
        self.assertEqual(bs, {"ads.example.com"})
        self.assertEqual(be, {"tracker.example.org", "plain-ad.example.cn"})
        self.assertEqual(skipped, 7)

    def test_fetch_records_parser(self):
        with tempfile.TemporaryDirectory() as td, mock.patch.object(AB, "AB_DIR", td), \
                mock.patch.object(AB, "download", return_value="baike.baidu.com##.x\n||ad.example.com^\n"):
            m = server.ab_fetch({"id": "x", "url": "https://example.com/l.txt"})
            self.assertEqual(m["parser"], AB.AB_PARSER)
            self.assertEqual(m["count"], 1)
            with open(os.path.join(td, "x.txt")) as f:
                self.assertNotIn("baike.baidu.com", f.read())


class StaleParserTest(unittest.TestCase):
    def test_old_lists_refetched(self):
        now = int(time.time())
        with mock.patch.object(SC, "ab_meta", return_value={"a": {"updated": now, "error": ""}}):
            self.assertEqual(SC.ab_last_update(), 0)
        with mock.patch.object(SC, "ab_meta", return_value={"a": {"updated": now, "error": "", "parser": AB.AB_PARSER}}):
            self.assertEqual(SC.ab_last_update(), now)
        with mock.patch.object(SC, "ab_meta", return_value={"a": {"updated": now, "error": "下载失败"}}):
            self.assertEqual(SC.ab_last_update(), now)  # 失败的列表不触发反复重下
