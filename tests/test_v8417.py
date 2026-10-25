"""v8.4.17：接口入参类型回归测试：字段传了数字 / 列表等非字符串，或规则测试目标清洗后为空时，应给出原因，不再是未处理异常的 500「内部错误」"""
import unittest

from tests.helper import server
from tests.test_v1012 import ApiCase

assert server


class RuleTestEmptyTargetTest(ApiCase):
    def test_empty_after_clean_400(self):
        for b in ({}, {"target": ""}, {"target": "http://"}, {"target": "https:///path"}):
            code, j = self.call("POST", "/api/ruletest", b)
            self.assertEqual(code, 400, (b, j))
            self.assertIn("域名或 IP", j["message"])


class NonStringFieldsTest(ApiCase):
    CASES = (
        ("POST", "/api/subs", {"name": 123, "url": []}),
        ("POST", "/api/nodes", {"links": 5}),
        ("POST", "/api/dnsquery", {"name": 123, "type": 1}),
        ("POST", "/api/backup/delete", {"name": 123}),
        ("POST", "/api/health/unhide", {"node_id": 123}),
    )

    def test_no_500(self):
        for m, p, b in self.CASES:
            code, j = self.call(m, p, b)
            self.assertNotEqual(j.get("message"), "内部错误", (p, b, code, j))  # 业务失败可以是 500（reply），但不能是未处理异常


if __name__ == "__main__":
    unittest.main()
