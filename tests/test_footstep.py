"""
脚步声系统 - 验收测试

运行方式：python -m pytest tests/test_footstep.py -q
共 11 个测试用例
"""
import math

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from audio.footstep import FootstepSystem


class TestFootstepSystem:
    """脚步声系统测试套件"""

    def setup_method(self):
        """每个测试前的初始化"""
        self.system = FootstepSystem()

    def test_case_01(self):
        """静止的玩家不播放脚步声"""
        assert self.system.play_footstep("p1", speed=0.0) is None
        assert self.system.play_footstep("p1", speed=-1.0) is None
        assert self.system.play_footstep("p1", speed=2.0) is not None

    def test_case_02(self):
        """跑步的脚步声比走路响"""
        walk = self.system.play_footstep("p1", speed=2.0)
        run = self.system.play_footstep("p1", speed=5.0)
        assert run["volume"] > walk["volume"] > 0

    def test_case_03(self):
        """不同地面材质播放不同的声音和音量"""
        concrete = self.system.play_footstep("p1", speed=2.0, surface="concrete")
        grass = self.system.play_footstep("p1", speed=2.0, surface="grass")
        assert concrete["sound"] != grass["sound"]
        assert concrete["volume"] > grass["volume"]

    def test_case_04(self):
        """音量随距离衰减，10 米外比 1 米外小"""
        near = self.system.calculate_volume(speed=5.0, distance=1.0)
        far = self.system.calculate_volume(speed=5.0, distance=10.0)
        assert near["volume"] > far["volume"] > 0
        silent = self.system.calculate_volume(speed=5.0, distance=100.0)
        assert silent["volume"] == 0.0

    def test_case_05(self):
        """方向感：声源在右侧时右声道大于左声道，左侧反之"""
        right = self.system.calculate_volume(speed=5.0, direction=math.pi / 2)
        assert right["right"] > right["left"]
        left = self.system.calculate_volume(speed=5.0, direction=-math.pi / 2)
        assert left["left"] > left["right"]
        front = self.system.calculate_volume(speed=5.0, direction=0.0)
        assert front["left"] == pytest.approx(front["right"])

    def test_case_06(self):
        """材质表支持多种地面，未知材质回退到水泥地"""
        for surface in ("concrete", "grass", "wood", "metal", "sand", "water"):
            info = self.system.surface_mapping(surface)
            assert info["sound"] == f"footstep_{surface}"
        fallback = self.system.surface_mapping("cloud")
        assert fallback["surface"] == "concrete"
        assert fallback["sound"] == "footstep_concrete"

    def test_case_07(self):
        """装备影响脚步声：靴子比拖鞋响"""
        boots = self.system.surface_mapping("concrete", footwear="boots")
        slippers = self.system.surface_mapping("concrete", footwear="slippers")
        assert boots["volume"] > slippers["volume"]
        event_boots = self.system.play_footstep("p1", speed=2.0, footwear="boots")
        event_slippers = self.system.play_footstep("p1", speed=2.0, footwear="slippers")
        assert event_boots["volume"] > event_slippers["volume"]

    def test_case_08(self):
        """障碍物遮挡降低音量，障碍物越多越安静"""
        clear = self.system.calculate_volume(speed=5.0, obstacles=0)
        wall = self.system.calculate_volume(speed=5.0, obstacles=1)
        two_walls = self.system.calculate_volume(speed=5.0, obstacles=2)
        assert clear["volume"] > wall["volume"] > two_walls["volume"] > 0

    def test_case_09(self):
        """高度差降低音量，楼上楼下比同层安静"""
        same_floor = self.system.calculate_volume(speed=5.0, height_diff=0.0)
        upstairs = self.system.calculate_volume(speed=5.0, height_diff=3.0)
        assert same_floor["volume"] > upstairs["volume"] > 0
        assert self.system.occlusion(obstacles=0, height_diff=0.0) == 1.0
        assert self.system.occlusion(obstacles=0, height_diff=3.0) < 1.0

    def test_case_10(self):
        """脚步频率随移动速度提升，静止时为零"""
        assert self.system.footstep_rate(speed=0.0) == 0.0
        walk = self.system.footstep_rate(speed=2.0)
        run = self.system.footstep_rate(speed=5.0)
        assert run > walk > 0
        assert walk == pytest.approx(2.0)

    def test_case_11(self):
        """脚步频率考虑体重：重角色步频低于轻角色"""
        light = self.system.footstep_rate(speed=3.0, weight=50.0)
        heavy = self.system.footstep_rate(speed=3.0, weight=100.0)
        assert light > heavy > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
