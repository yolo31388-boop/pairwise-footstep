"""
脚步声系统 - 核心模块

功能：
- 按移动速度和地面材质播放脚步声
- 音量按距离衰减，支持左右声道方向感
- 材质表支持多种地面，并考虑玩家装备（鞋类）
- 声音考虑障碍物遮挡和高度差
- 脚步声频率按移动速度和角色体重计算
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import math
import time


# 地面材质表：声音资源、基础音量、吸声系数
DEFAULT_SURFACE_MAP: Dict[str, Dict] = {
    "concrete": {"sound": "footstep_concrete", "volume": 1.0, "absorption": 0.1},
    "grass": {"sound": "footstep_grass", "volume": 0.6, "absorption": 0.5},
    "wood": {"sound": "footstep_wood", "volume": 0.9, "absorption": 0.2},
    "metal": {"sound": "footstep_metal", "volume": 1.1, "absorption": 0.05},
    "sand": {"sound": "footstep_sand", "volume": 0.5, "absorption": 0.6},
    "water": {"sound": "footstep_water", "volume": 0.8, "absorption": 0.3},
}

# 鞋类装备对脚步声音量的修正系数
DEFAULT_FOOTWEAR_MODIFIERS: Dict[str, float] = {
    "boots": 1.2,
    "sneakers": 0.8,
    "slippers": 0.5,
    "barefoot": 0.4,
}

DEFAULT_SURFACE = "concrete"
DEFAULT_FOOTWEAR = "boots"


@dataclass
class Config:
    """配置项"""
    walk_speed: float = 2.0        # 步行速度 (m/s)
    run_speed: float = 5.0         # 跑步速度 (m/s)
    reference_distance: float = 1.0  # 距离衰减参考距离 (m)
    max_distance: float = 50.0     # 最大可听距离 (m)
    occlusion_damping: float = 0.4   # 每个障碍物的音量保留系数
    height_damping: float = 0.15     # 每米高度差的衰减系数
    reference_weight: float = 70.0   # 参考体重 (kg)
    base_rate: float = 2.0           # 参考体重下步行频率 (步/秒)
    min_rate: float = 0.5            # 最小脚步频率
    max_rate: float = 6.0            # 最大脚步频率


class FootstepSystem:
    """脚步声系统核心类"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        cfg = Config()
        for key, value in self.config.items():
            if hasattr(cfg, key):
                setattr(cfg, key, value)
        self._cfg = cfg
        self._surface_map = dict(DEFAULT_SURFACE_MAP)
        self._surface_map.update(self.config.get("surface_map", {}))
        self._footwear_modifiers = dict(DEFAULT_FOOTWEAR_MODIFIERS)
        self._footwear_modifiers.update(self.config.get("footwear_modifiers", {}))
        self._state = {}
        self._history: List[Dict] = []

    def update(self, dt: float):
        """每帧更新，推进内部计时"""
        self._state["time"] = self._state.get("time", 0.0) + dt

    def reset(self):
        """重置状态"""
        self._state = {}
        self._history = []

    def play_footstep(
        self,
        player_id: str,
        speed: float,
        surface: str = DEFAULT_SURFACE,
        footwear: str = DEFAULT_FOOTWEAR,
        weight: float = 70.0,
        distance: float = 0.0,
        direction: float = 0.0,
        obstacles: int = 0,
        height_diff: float = 0.0,
    ) -> Optional[Dict]:
        """
        播放一次脚步声。

        - speed <= 0（未移动）时不播放，返回 None
        - 音量随速度提升，并随距离衰减、带左右声道方向感
        - 音色由地面材质和鞋类装备共同决定
        """
        if speed <= 0:
            return None

        surface_info = self.surface_mapping(surface, footwear)
        volume_info = self.calculate_volume(
            speed=speed,
            distance=distance,
            direction=direction,
            obstacles=obstacles,
            height_diff=height_diff,
            surface_volume=surface_info["volume"],
        )
        rate = self.footstep_rate(speed, weight)

        event = {
            "player_id": player_id,
            "sound": surface_info["sound"],
            "surface": surface_info["surface"],
            "footwear": footwear,
            "speed": speed,
            "volume": volume_info["volume"],
            "left": volume_info["left"],
            "right": volume_info["right"],
            "pan": volume_info["pan"],
            "rate": rate,
            "distance": distance,
            "occlusion": self.occlusion(obstacles, height_diff),
        }
        self._history.append(event)
        return event

    def calculate_volume(
        self,
        speed: float,
        distance: float = 0.0,
        direction: float = 0.0,
        obstacles: int = 0,
        height_diff: float = 0.0,
        surface_volume: float = 1.0,
    ) -> Dict:
        """
        计算脚步声最终音量与立体声声像。

        - 基础音量随速度提升（跑步比走路响）
        - 音量随距离反比衰减，超过最大可听距离时为 0
        - direction 为相对听者朝向的方位角（弧度），转换为左右声道声像
        """
        cfg = self._cfg
        speed_factor = min(max(speed / cfg.run_speed, 0.0), 1.0)
        base = speed_factor * surface_volume

        if distance >= cfg.max_distance:
            attenuation = 0.0
        else:
            attenuation = cfg.reference_distance / (cfg.reference_distance + max(distance, 0.0))

        occlusion_factor = self.occlusion(obstacles, height_diff)

        volume = base * attenuation * occlusion_factor

        pan = math.sin(direction)
        pan = max(-1.0, min(1.0, pan))
        # 等功率声像：pan=-1 全左，pan=+1 全右
        angle = (pan + 1.0) * math.pi / 4.0
        left = volume * math.cos(angle)
        right = volume * math.sin(angle)

        return {"volume": volume, "left": left, "right": right, "pan": pan}

    def surface_mapping(
        self, surface: str, footwear: str = DEFAULT_FOOTWEAR
    ) -> Dict:
        """
        查询地面材质对应的声音与音量，并应用鞋类装备修正。
        未知材质回退到水泥地，未知鞋类按无修正处理。
        """
        info = self._surface_map.get(surface, self._surface_map[DEFAULT_SURFACE])
        footwear_mod = self._footwear_modifiers.get(footwear, 1.0)
        return {
            "surface": surface if surface in self._surface_map else DEFAULT_SURFACE,
            "sound": info["sound"],
            "volume": info["volume"] * footwear_mod,
            "absorption": info["absorption"],
            "footwear_modifier": footwear_mod,
        }

    def occlusion(self, obstacles: int = 0, height_diff: float = 0.0) -> float:
        """
        计算遮挡衰减系数 (0, 1]。
        每有一个障碍物乘以 occlusion_damping；高度差按线性衰减。
        """
        cfg = self._cfg
        factor = cfg.occlusion_damping ** max(obstacles, 0)
        factor *= 1.0 / (1.0 + cfg.height_damping * abs(height_diff))
        return factor

    def footstep_rate(self, speed: float, weight: float = 70.0) -> float:
        """
        计算脚步频率（步/秒）。
        频率随速度线性提升；体重越大步幅越大，频率越低。
        """
        if speed <= 0:
            return 0.0
        cfg = self._cfg
        weight = max(weight, 1.0)
        # 参考体重下步幅 = walk_speed / base_rate；体重按 1/4 次幂调整步幅
        stride = (cfg.walk_speed / cfg.base_rate) * (weight / cfg.reference_weight) ** 0.25
        rate = speed / stride
        return min(max(rate, cfg.min_rate), cfg.max_rate)
