"""Keep novice instructions aligned with the shipped version and visible UI."""
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class UserGuideTests(unittest.TestCase):
    def setUp(self):
        self.readme = (ROOT / 'README.md').read_text(encoding='utf-8-sig')
        self.agents = (ROOT / 'AGENTS.md').read_text(encoding='utf-8-sig')

    def test_direct_program_and_optional_installer_match_the_desktop_release(self):
        config = json.loads((ROOT / 'apps/desktop/src-tauri/tauri.conf.json').read_text(encoding='utf-8-sig'))
        filename = f"{config['productName']}_{config['version']}_x64-setup.exe"
        self.assertIn(filename, self.readme)
        self.assertIn(f"{config['productName']}.exe", self.readme)
        self.assertIn('`D:\\pdf分割\\StudyNote`', self.readme)
        self.assertIn('`D:\\pdf分割\\StudyNote\\installers`', self.readme)
        self.assertNotIn('D:\\StudyNote', self.readme)
        self.assertIn('studynote-backend.exe', self.readme)
        self.assertNotIn('本机安装文件就在 **`D:\\pdf分割`', self.readme)
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

    def test_project_work_and_release_paths_stay_in_the_requested_folder(self):
        self.assertIn('只在 `D:\\pdf分割` 文件夹及其子目录内工作', self.agents)
        self.assertIn('不得在其他目录另建或修改项目文件', self.agents)
        self.assertIn('只在 `D:\\pdf分割` 文件夹及其子目录内工作', self.readme)
        workflow = (ROOT / '.github/workflows/windows.yml').read_text(encoding='utf-8-sig')
        self.assertIn("Join-Path $env:GITHUB_WORKSPACE 'StudyNote'", workflow)
        self.assertNotIn('RUNNER_TEMP', workflow)
        self.assertIn('/StudyNote/', (ROOT / '.gitignore').read_text(encoding='utf-8-sig'))


if __name__ == '__main__':
    unittest.main()
