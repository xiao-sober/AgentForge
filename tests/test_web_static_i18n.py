import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "apps" / "web" / "frontend"


class WebStaticI18nTest(unittest.TestCase):
    def test_web_console_defaults_to_chinese(self):
        index = (FRONTEND / "index.html").read_text(encoding="utf-8")
        app = (FRONTEND / "src" / "App.tsx").read_text(encoding="utf-8")
        i18n = (FRONTEND / "src" / "i18n.ts").read_text(encoding="utf-8")

        self.assertIn('<html lang="zh-CN">', index)
        self.assertIn("正在检查本地运行状态...", index)
        self.assertIn(">English</button>", index)
        self.assertIn('localStorage.getItem("agentforge_lang")', app)
        self.assertIn('return stored === "en" || stored === "zh" ? stored : "zh";', app)
        self.assertIn('drilldown: "钻取视图"', i18n)
        self.assertIn("export function App()", app)

    def test_web_console_has_long_task_progress_ui(self):
        app = (FRONTEND / "src" / "App.tsx").read_text(encoding="utf-8")
        i18n = (FRONTEND / "src" / "i18n.ts").read_text(encoding="utf-8")
        css = (FRONTEND / "src" / "styles.css").read_text(encoding="utf-8")

        self.assertIn("function ProgressPanel", app)
        self.assertIn('progressTitle: "流程运行中"', i18n)
        self.assertIn("Thinking 模型调用可能持续数分钟", i18n)
        self.assertIn(".progress-steps", css)

    def test_web_console_has_tool_call_timeline_ui(self):
        app = (FRONTEND / "src" / "App.tsx").read_text(encoding="utf-8")
        view_model = (FRONTEND / "src" / "view-model.ts").read_text(encoding="utf-8")
        css = (FRONTEND / "src" / "styles.css").read_text(encoding="utf-8")

        self.assertIn("agentMode", app)
        self.assertIn("tool_call_timeline", view_model)
        self.assertIn("toolCallTimelineHtml", view_model)
        self.assertIn("validation-errors", view_model)
        self.assertIn(".tool-call-detail", css)
        self.assertIn(".repair-badge", css)


if __name__ == "__main__":
    unittest.main()
