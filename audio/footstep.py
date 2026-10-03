"""
脚步声系统 - 核心模块（修复版）

修复内容：
- play_footstep() 按移动速度和地面材质播放脚步声
- calculate_volume() 音量按距离衰减，支持左右声道方向感
- surface_mapping() 材质表支持多种地面，并考虑玩家装备
- occlusion() 考虑障碍物遮挡和高度差
- footstep_rate() 频率按移动速度和角色体重计算
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import math
import time


@dataclass
class Config:
    """配置项"""
    walk_speed: float = 2.0        # 步行速度 (m/s)
    base_rate: float = 2.0         # 步行时的基准脚步频率 (步/秒)
    reference_weight: float = 70.0  # 基准体重 (kg)
    reference_distance: float = 1.0  # 距离衰减参考距离 (m)
    wall_transmission: float = 0.5   # 每堵墙的透声系数
    height_attenuation: float = 0.5  # 高度差衰减系数 (每米)


# 地面材质表：不同地面有不同的声音样本、基础音量和音调
SURFACE_TABLE: Dict[str, Dict[str, float]] = {
    "concrete": {"sound": "step_concrete", "volume": 1.0, "pitch": 1.0},
    "grass":    {"sound": "step_grass",    "volume": 0.5, "pitch": 0.9},
    "wood":     {"sound": "step_wood",     "volume": 0.8, "pitch": 1.1},
    "metal":    {"sound": "step_metal",    "volume": 0.9, "pitch": 1.3},
    "water":    {"sound": "step_water",    "volume": 0.7, "pitch": 0.8},
    "sand":     {"sound": "step_sand",     "volume": 0.4, "pitch": 0.85},
}
DEFAULT_SURFACE = "concrete"

# 装备（鞋类）修正：不同 footwear 音量和音调不同
EQUIPMENT_MODIFIERS: Dict[str, Dict[str, float]] = {
    "boots":    {"volume": 1.2, "pitch": 0.9},
    "sneakers": {"volume": 0.9, "pitch": 1.0},
    "slippers": {"volume": 0.6, "pitch": 1.1},
    "barefoot": {"volume": 0.4, "pitch": 1.0},
}
DEFAULT_EQUIPMENT = "boots"


class FootstepSystem:
    """脚步声系统核心类"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self._state = {}
        self._history = []

    # ------------------------------------------------------------------
    # 配置读取
    # ------------------------------------------------------------------
    def _cfg(self, key: str) -> float:
        defaults = Config()
        return self.config.get(key, getattr(defaults, key))

    # ------------------------------------------------------------------
    # 播放脚步声：按移动速度和地面材质
    # ------------------------------------------------------------------
    def play_footstep(self, moving: bool = False, speed: float = 0.0,
                      surface: str = DEFAULT_SURFACE,
                      equipment: str = DEFAULT_EQUIPMENT,
                      distance: float = 1.0, direction: float = 0.0,
                      obstacles: int = 0, height_diff: float = 0.0,
                      weight: float = 70.0) -> Optional[Dict]:
        """播放一次脚步声。

        参数:
            moving: 玩家是否在移动
            speed: 移动速度 (m/s)，速度越快脚步越响
            surface: 地面材质（见 SURFACE_TABLE）
            equipment: 脚部装备（见 EQUIPMENT_MODIFIERS）
            distance: 与听者的距离 (m)
            direction: 相对听者的方向角 (弧度, 0=正前方, 正值偏右)
            obstacles: 之间的障碍物（墙）数量
            height_diff: 与听者的高度差 (m)
            weight: 角色体重 (kg)

        返回:
            脚步声音事件 dict；未移动或速度为 0 时返回 None。
        """
        if not moving or speed <= 0.0:
            return None

        profile = self.surface_mapping(surface, equipment)

        # 速度越快脚步越响（走路 < 跑步）
        walk_speed = self._cfg("walk_speed")
        speed_factor = min(max(speed / walk_speed, 0.2), 3.0)

        base_volume = profile["volume"] * speed_factor
        left, right = self.calculate_volume(distance, direction, base_volume)

        occ = self.occlusion(obstacles=obstacles, height_diff=height_diff)
        left *= occ
        right *= occ

        event = {
            "sound": profile["sound"],
            "surface": profile["surface"],
            "equipment": equipment,
            "volume": (left + right) / 2.0,
            "left": left,
            "right": right,
            "pitch": profile["pitch"],
            "rate": self.footstep_rate(speed, weight),
            "time": time.time(),
        }
        self._history.append(event)
        return event

    # ------------------------------------------------------------------
    # 音量计算：距离衰减 + 左右声道方向感
    # ------------------------------------------------------------------
    def _distance_attenuation(self, distance: float) -> float:
        """距离衰减：距离越远音量越小。"""
        ref = self._cfg("reference_distance")
        return ref / (ref + max(distance, 0.0))

    def calculate_volume(self, distance: float, direction: float = 0.0,
                         base_volume: float = 1.0) -> Tuple[float, float]:
        """按距离衰减并做立体声声像，返回 (左声道, 右声道) 音量。

        direction 为弧度：0=正前方，+pi/2=正右方，-pi/2=正左方。
        使用等功率声像（constant-power panning）。
        """
        volume = base_volume * self._distance_attenuation(distance)

        pan = math.sin(direction)          # -1(全左) .. 0(中) .. +1(全右)
        pan = min(max(pan, -1.0), 1.0)
        angle = (pan + 1.0) * math.pi / 4.0
        left = volume * math.cos(angle)
        right = volume * math.sin(angle)
        return left, right

    # ------------------------------------------------------------------
    # 地面材质映射：多种地面 + 装备修正
    # ------------------------------------------------------------------
    def surface_mapping(self, surface: str,
                        equipment: str = DEFAULT_EQUIPMENT) -> Dict:
        """根据地面材质和装备返回脚步声配置。

        未知材质回退到水泥地，未知装备不做修正。
        """
        profile = dict(SURFACE_TABLE.get(surface,
                                         SURFACE_TABLE[DEFAULT_SURFACE]))
        profile["surface"] = surface if surface in SURFACE_TABLE else DEFAULT_SURFACE

        modifier = EQUIPMENT_MODIFIERS.get(equipment, {})
        profile["volume"] = profile["volume"] * modifier.get("volume", 1.0)
        profile["pitch"] = profile["pitch"] * modifier.get("pitch", 1.0)
        return profile

    # ------------------------------------------------------------------
    # 声音遮挡：障碍物 + 高度差
    # ------------------------------------------------------------------
    def occlusion(self, obstacles: int = 0, height_diff: float = 0.0) -> float:
        """返回遮挡衰减系数 (0, 1]。

        每堵墙按透声系数衰减；高度差越大衰减越明显（楼上/楼下对称）。
        """
        factor = self._cfg("wall_transmission") ** max(int(obstacles), 0)
        height = self._cfg("height_attenuation")
        factor *= 1.0 / (1.0 + height * abs(height_diff))
        return factor

    # ------------------------------------------------------------------
    # 脚步频率：按移动速度和体重
    # ------------------------------------------------------------------
    def footstep_rate(self, speed: float, weight: float = 70.0) -> float:
        """脚步频率 (步/秒)。

        速度越快频率越高；体重越大步幅越大、频率越低。
        静止时频率为 0。
        """
        if speed <= 0.0:
            return 0.0
        walk_speed = self._cfg("walk_speed")
        base_rate = self._cfg("base_rate")
        ref_weight = self._cfg("reference_weight")
        weight = max(weight, 1.0)
        rate = base_rate * (speed / walk_speed) * (ref_weight / weight) ** 0.5
        return min(max(rate, 0.0), 10.0)

    # ------------------------------------------------------------------
    # 帧更新 / 重置
    # ------------------------------------------------------------------
    def update(self, dt: float):
        """每帧更新"""
        self._state["elapsed"] = self._state.get("elapsed", 0.0) + dt

    def reset(self):
        """重置状态"""
        self._state = {}
        self._history = []
