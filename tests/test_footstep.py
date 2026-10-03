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

from audio.footstep import FootstepSystem, SURFACE_TABLE, EQUIPMENT_MODIFIERS


class TestFootstepSystem:
    """脚步声系统测试套件"""

    def setup_method(self):
        """每个测试前的初始化"""
        self.system = FootstepSystem()

    def test_case_01(self):
        """静止时不播放脚步声"""
        assert self.system.play_footstep(moving=False, speed=0.0) is None
        assert self.system.play_footstep(moving=True, speed=0.0) is None
        assert self.system.play_footstep(moving=False, speed=5.0) is None

    def test_case_02(self):
        """脚步声随移动速度变化：跑步比走路响"""
        walk = self.system.play_footstep(moving=True, speed=2.0)
        run = self.system.play_footstep(moving=True, speed=6.0)
        assert walk is not None and run is not None
        assert run["volume"] > walk["volume"]

    def test_case_03(self):
        """不同地面材质播放不同的脚步声"""
        concrete = self.system.play_footstep(moving=True, speed=2.0, surface="concrete")
        grass = self.system.play_footstep(moving=True, speed=2.0, surface="grass")
        assert concrete["sound"] != grass["sound"]
        # 草地比水泥地安静
        assert grass["volume"] < concrete["volume"]

    def test_case_04(self):
        """音量按距离衰减：越远越小"""
        near_l, near_r = self.system.calculate_volume(distance=1.0)
        far_l, far_r = self.system.calculate_volume(distance=10.0)
        assert near_l > far_l
        assert near_r > far_r
        assert 0.0 < far_l < 1.0

    def test_case_05(self):
        """音量有方向感：左右声道随方向变化"""
        left, right = self.system.calculate_volume(distance=5.0, direction=math.radians(90))
        assert right > left  # 声源在右，右声道更响
        left, right = self.system.calculate_volume(distance=5.0, direction=math.radians(-90))
        assert left > right  # 声源在左，左声道更响
        left, right = self.system.calculate_volume(distance=5.0, direction=0.0)
        assert left == pytest.approx(right)  # 正前方两声道相等

    def test_case_06(self):
        """材质表支持多种地面"""
        assert len(SURFACE_TABLE) >= 4
        profiles = {s: self.system.surface_mapping(s) for s in SURFACE_TABLE}
        sounds = {p["sound"] for p in profiles.values()}
        assert len(sounds) == len(SURFACE_TABLE)  # 每种地面声音不同
        assert self.system.surface_mapping("grass")["sound"] != \
            self.system.surface_mapping("concrete")["sound"]

    def test_case_07(self):
        """材质映射考虑装备：靴子和拖鞋不同"""
        boots = self.system.surface_mapping("concrete", equipment="boots")
        slippers = self.system.surface_mapping("concrete", equipment="slippers")
        assert boots["volume"] != slippers["volume"]
        assert boots["volume"] > slippers["volume"]  # 靴子比拖鞋响

    def test_case_08(self):
        """声音遮挡：障碍物降低音量"""
        clear = self.system.occlusion(obstacles=0)
        one_wall = self.system.occlusion(obstacles=1)
        two_walls = self.system.occlusion(obstacles=2)
        assert clear == 1.0
        assert one_wall < clear
        assert two_walls < one_wall

    def test_case_09(self):
        """声音遮挡：高度差降低音量（楼上/楼下）"""
        same_floor = self.system.occlusion(height_diff=0.0)
        upstairs = self.system.occlusion(height_diff=3.0)
        downstairs = self.system.occlusion(height_diff=-3.0)
        assert same_floor == 1.0
        assert upstairs < same_floor
        assert downstairs < same_floor
        assert upstairs == pytest.approx(downstairs)  # 高度差对称

    def test_case_10(self):
        """脚步频率随移动速度变化"""
        assert self.system.footstep_rate(speed=0.0) == 0.0
        walk = self.system.footstep_rate(speed=2.0)
        run = self.system.footstep_rate(speed=6.0)
        assert walk > 0.0
        assert run > walk

    def test_case_11(self):
        """脚步频率随体重变化：轻重角色不同"""
        light = self.system.footstep_rate(speed=4.0, weight=50.0)
        heavy = self.system.footstep_rate(speed=4.0, weight=100.0)
        assert light != heavy
        assert heavy < light  # 重角色步频更低


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
