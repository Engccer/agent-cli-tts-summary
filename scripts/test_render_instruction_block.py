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
    def test_temp_path_matches_agent_home(self):
        block = render("codex", "windows", r"C:\Users\example\.codex")  # sanitize: allow 일반화된 예시 경로
        self.assertIn(r"C:\Users\example\.codex\tts-summary.txt", block)  # sanitize: allow 일반화된 예시 경로
        self.assertIn(r"C:\Users\example\.codex\TTS-Summary\txt\summary-*.txt", block)  # sanitize: allow 일반화된 예시 경로

    def test_korean_block_states_single_use_contract(self):
        """훅이 소비 후 삭제한다는 사실과 매 턴 새 파일 생성 계약이 빠지면 안 된다."""
        for agent in AGENTS:
            for platform in PLATFORMS:
                with self.subTest(agent=agent, platform=platform):
                    block = render(agent, platform, "~/.codex")
                    self.assertIn("일회용 파일", block)
                    self.assertIn("삭제", block)
                    self.assertIn("새 파일 생성", block)

    def test_english_block_states_single_use_contract(self):
        for agent in AGENTS:
            for platform in PLATFORMS:
                with self.subTest(agent=agent, platform=platform):
                    block = render(agent, platform, "~/.codex", language="English")
                    self.assertIn("Single-use file", block)
                    self.assertIn("deletes it after reading", block)
                    self.assertIn("creating a new file", block)

    def test_order_rule_survives(self):
        self.assertIn("순서 필수", render("claude", "macos", "~/.claude"))
        self.assertIn("Order matters", render("claude", "macos", "~/.claude", language="English"))


if __name__ == "__main__":
    unittest.main()
