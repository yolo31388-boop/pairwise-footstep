# 脚步声系统

## 项目描述

脚步声系统的bug修复项目。核心模块 `audio/footstep.py` 存在多个已知bug，需要修复后使测试全部通过。

## 已知问题

- 不检查移动速度和地面材质
- 音量无距离衰减无方向感
- 材质表只有一种不考虑装备
- 无遮挡和高度差检测
- 频率固定不按速度体重

## 项目结构

```
├── audio/footstep.py       # 核心模块（带bug）
├── tests/test_footstep.py    # 验收测试（红态）
├── pyproject.toml          # 项目配置
└── README.md               # 说明文档
```

## 运行测试

```bash
python -m pytest tests/test_footstep.py -q
```

修复目标：所有 11 个测试全部通过。

## 技术要求

- 纯Python标准库，不引入第三方依赖
- 不修改测试文件
- 保持现有API接口不变
- 修复所有已知bug
