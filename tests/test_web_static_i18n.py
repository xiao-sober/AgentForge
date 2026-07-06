import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WebStaticI18nTest(unittest.TestCase):
    def test_web_console_defaults_to_chinese(self):
        index = (ROOT / "src" / "agentforge" / "web" / "static" / "index.html").read_text(encoding="utf-8")
        app = (ROOT / "src" / "agentforge" / "web" / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn('<html lang="zh-CN">', index)
        self.assertIn("正在检查本地运行状态", index)
        self.assertIn(">English</button>", index)
        self.assertIn('localStorage.getItem("agentforge_lang") || "zh"', app)
        self.assertIn('drilldown: "钻取视图"', app)

    def test_web_console_has_long_task_progress_ui(self):
        app = (ROOT / "src" / "agentforge" / "web" / "static" / "app.js").read_text(encoding="utf-8")
        css = (ROOT / "src" / "agentforge" / "web" / "static" / "app.css").read_text(encoding="utf-8")

        self.assertIn("renderLongTaskProgress", app)
        self.assertIn('progressTitle: "流程运行中"', app)
        self.assertIn('longTaskHint: "Thinking 模型调用可能持续数分钟。请保持当前页面打开，AgentForge 会继续写入 trace 和产物。"', app)
        self.assertIn(".progress-steps", css)

    def test_web_console_has_tool_call_timeline_ui(self):
        app = (ROOT / "src" / "agentforge" / "web" / "static" / "app.js").read_text(encoding="utf-8")
        css = (ROOT / "src" / "agentforge" / "web" / "static" / "app.css").read_text(encoding="utf-8")

        self.assertIn("ensureAgentModeControl", app)
        self.assertIn("tool_call_timeline", app)
        self.assertIn("toolCallTimelineHtml", app)
        self.assertIn("validation-errors", app)
        self.assertIn(".tool-call-detail", css)
        self.assertIn(".repair-badge", css)


if __name__ == "__main__":
    unittest.main()
