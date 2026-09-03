#!/usr/bin/env python3
"""render_instruction_block.py 회귀 테스트. 표준 라이브러리만 쓴다.
실행: python scripts/test_render_instruction_block.py
"""

from __future__ import annotations

import unittest

from render_instruction_block import render

AGENTS = ["claude", "codex", "gemini", "antigravity"]
PLATFORMS = ["windows", "macos"]


class RenderInstructionBlockTest(unittest.TestCase):
    def test_paths_match_agent_home(self):
        block = render("codex", "windows", r"C:\Users\example\.codex")
        self.assertIn(r"C:\Users\example\.codex\tts-summary.txt", block)
        self.assertIn(r"C:\Users\example\.codex\hooks-windows\play-tts-briefing.ps1", block)
        block = render("codex", "macos", "~/.codex")
        self.assertIn("~/.codex/hooks-macos/play-tts-briefing.sh", block)
        block = render("claude", "macos", "~/.claude")
        self.assertIn("~/.claude/hooks/play-tts-briefing.sh", block)

    def test_korean_block_states_contracts(self):
        """순서, 일회용 파일, 통지 추종, 직접 호출 금지가 빠지면 안 된다."""
        for agent in AGENTS:
            for platform in PLATFORMS:
                with self.subTest(agent=agent, platform=platform):
                    block = render(agent, platform, "~/.codex")
                    self.assertIn("먼저 쓰고", block)
                    self.assertIn("턴마다 새로 만든다", block)
                    self.assertIn("삭제", block)
                    self.assertIn("[tts-config]", block)
                    self.assertIn("직접 호출하지 않는다", block)

    def test_english_block_states_contracts(self):
        for agent in AGENTS:
            for platform in PLATFORMS:
                with self.subTest(agent=agent, platform=platform):
                    block = render(agent, platform, "~/.codex", language="English")
                    self.assertIn("summary in English", block)
                    self.assertIn("Write the summary file first", block)
                    self.assertIn("Create the file fresh every turn", block)
                    self.assertIn("Never invoke TTS yourself", block)

    def test_slash_command_mentioned_only_for_claude(self):
        self.assertIn("`/tts`", render("claude", "macos", "~/.claude"))
        self.assertNotIn("`/tts`", render("codex", "macos", "~/.codex"))


if __name__ == "__main__":
    unittest.main()
