#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""business_constants 自动加载器。

根据 ``--project`` 命令行参数或 ``CASE_GEN_PROJECT`` 环境变量，
自动加载对应项目的 ``business_constants.py`` 并暴露所有常量。

所有脚本仍然 ``from business_constants import XXX``，
不需要修改任何 import 语句——本模块会自动转发到正确的项目配置。

用法::

    # 命令行指定项目
    python scripts/validate_cases.py --project qrs --source ...

    # 或通过环境变量
    export CASE_GEN_PROJECT=qrs
    python scripts/validate_cases.py --source ...

    # 默认项目（未指定时）
    python scripts/validate_cases.py --source ...  # 使用 DEFAULT_PROJECT
"""

from __future__ import annotations

import os
import sys

# 默认项目（未指定 --project 时使用）
DEFAULT_PROJECT = "qrs"


def _detect_project() -> str:
    """从环境变量或命令行参数检测当前项目。"""
    # 1. 环境变量优先
    project = os.environ.get("CASE_GEN_PROJECT")
    if project:
        return project

    # 2. 命令行参数 --project xxx 或 --project=xxx
    for i, arg in enumerate(sys.argv):
        if arg == "--project" and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
        if arg.startswith("--project="):
            return arg.split("=", 1)[1]

    # 3. 默认项目
    return DEFAULT_PROJECT


def _load_project_constants():
    """加载当前项目的 business_constants 并把所有常量暴露到本模块。"""
    project = _detect_project()

    # 计算项目配置文件路径
    _this_dir = os.path.dirname(os.path.abspath(__file__))
    _skill_root = os.path.dirname(_this_dir)
    constants_path = os.path.join(_skill_root, "projects", project, "business_constants.py")

    if not os.path.exists(constants_path):
        available = []
        projects_dir = os.path.join(_skill_root, "projects")
        if os.path.isdir(projects_dir):
            available = [
                d for d in os.listdir(projects_dir)
                if os.path.isfile(
                    os.path.join(projects_dir, d, "business_constants.py")
                )
            ]
        raise ValueError(
            f"项目不存在：{project}\n"
            f"可用项目：{', '.join(sorted(available))}\n"
            f"使用 --project <name> 指定项目，或设置环境变量 CASE_GEN_PROJECT"
        )

    # 动态加载项目配置
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        f"projects.{project}.business_constants", constants_path
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载项目配置：{constants_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # 把项目目录加入 sys.path，让业务规则模块能被 import
    project_dir = os.path.join(_skill_root, "projects", project)
    if project_dir not in sys.path:
        sys.path.insert(0, project_dir)

    # 注册到 sys.modules，让后续 import business_constants 直接拿到
    sys.modules["business_constants"] = module

    # 暴露项目名，供其他模块（如 case_utils.py）使用
    module.PROJECT_NAME = project

    return module


# 加载并暴露所有常量
_project_constants = _load_project_constants()

# 把项目配置中的所有公开常量暴露到本模块
for _name in dir(_project_constants):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_project_constants, _name)
