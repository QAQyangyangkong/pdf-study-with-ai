"""Keep novice instructions aligned with the shipped version and visible UI."""
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class UserGuideTests(unittest.TestCase):
    def setUp(self):
        self.readme = (ROOT / 'README.md').read_text(encoding='utf-8-sig')
        self.agents = (ROOT / 'AGENTS.md').read_text(encoding='utf-8-sig')

    def test_installation_filename_matches_the_desktop_release(self):
        config = json.loads((ROOT / 'apps/desktop/src-tauri/tauri.conf.json').read_text(encoding='utf-8-sig'))
        filename = f"{config['productName']}_{config['version']}_x64-setup.exe"
        self.assertIn(filename, self.readme)
        self.assertIn('开始菜单', self.readme)
        self.assertIn('nsis', config['bundle']['targets'])

    def test_instructions_use_controls_that_exist_in_the_ui(self):
        controls = {
            'features/onboarding/index.tsx': ['先离线使用'],
            'features/library/index.tsx': ['导入教材', '课程名称', '确认导入', '阅读与分章'],
            'features/reader/index.tsx': ['章节名称', '起始页', '结束页', '拆分并提取文字', '核对提取文字', '生成章节笔记'],
            'features/notes/index.tsx': ['新建笔记', '笔记标题', '富文本', '保存笔记', '知识主题', '搜索笔记'],
            'features/ai-settings/index.tsx': ['API Key', '保存配置', '验证已保存的主模型'],
            'features/backup/index.tsx': ['选择导出位置', '创建完整备份', '当前资料保存位置'],
            'app/App.tsx': ['我的教材', '我的笔记', '知识体系', 'AI 与模型', '备份与导出', '确认生成', '使用缓存'],
        }
        for relative, labels in controls.items():
            source = (ROOT / 'apps/desktop/src' / relative).read_text(encoding='utf-8-sig')
            for label in labels:
                with self.subTest(control=label, source=relative):
                    self.assertIn(label, source, 'The guide refers to a control no longer present in the UI.')
                    self.assertIn(label, self.readme, 'The beginner guide is missing a required control.')

    def test_beginner_instructions_precede_and_exclude_development_commands(self):
        start = self.readme.index('## 普通用户使用教程')
        development = self.readme.index('## 开发者说明：环境与启动')
        self.assertLess(start, development)
        beginner = self.readme[start:development]
        for command in ('pnpm ', 'python -m venv', '.venv\\Scripts'):
            self.assertNotIn(command, beginner)
        self.assertIn('每次改完内容，也要再点一次保存', beginner)
        self.assertIn('包含封面和目录', beginner)
        self.assertIn('一键恢复', beginner)

    def test_readme_and_agent_rules_require_immediate_documentation_updates(self):
        for document in (self.readme, self.agents):
            self.assertIn('每一步修改', document)
            self.assertIn('实时同步', document)
            self.assertIn('README', document)
        self.assertIn('普通人', self.agents)
        self.assertIn('实际界面中的按钮名称', self.agents)


if __name__ == '__main__':
    unittest.main()
