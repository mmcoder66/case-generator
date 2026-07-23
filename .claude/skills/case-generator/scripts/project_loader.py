#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""项目配置加载器。

根据 ``--project`` 参数动态加载对应项目的 ``business_constants.py``，
并设置该项目专属的输入/输出路径和知识库路径。

用法::

    from project_loader import load_project
    project = load_project("qrs")
    constants = project["constants"]
    # constants.PROJECT_SPECIFIC_HEADERS, constants.SHEET_NAME, ...

所有脚本通过本模块获取项目配置，不再直接 import business_constants。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any


def skill_root() -> Path:
    """返回 case-generator Skill 根目录。"""
    return Path(__file__).resolve().parent.parent


def project_dir(project_name: str) -> Path:
    """返回项目专属配置目录路径。"""
    return skill_root() / "projects" / project_name


def load_project(project_name: str) -> dict[str, Any]:
    """加载项目配置。

    参数:
        project_name: 项目名称（如 ``"qrs"``、``"cpv"``）

    返回:
        包含以下 key 的字典::

            {
                "name": 项目名称,
                "constants": business_constants 模块,
                "inputs_root": inputs/<name> 路径,
                "outputs_root": outputs/<name> 路径,
                "knowledge_base": projects/<name>/knowledge_base 路径,
                "project_dir": projects/<name> 路径,
            }
    """
    root = skill_root()
    pdir = project_dir(project_name)

    if not pdir.exists():
        raise ValueError(
            f"项目不存在：{project_name}\n"
            f"可用项目：{', '.join(_list_projects())}"
        )

    constants_path = pdir / "business_constants.py"
    if not constants_path.exists():
        raise FileNotFoundError(f"项目缺少 business_constants.py：{constants_path}")

    # 动态加载 business_constants.py
    module_name = f"projects.{project_name}.business_constants"
    spec = importlib.util.spec_from_file_location(module_name, constants_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载项目配置：{constants_path}")
    constants = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(constants)

    # 把项目配置目录加入 sys.path，让项目内的业务规则模块能 import
    pdir_str = str(pdir)
    if pdir_str not in sys.path:
        sys.path.insert(0, pdir_str)

    # 同步把 constants 注册到 sys.modules，让 ``import business_constants`` 仍可用
    sys.modules["business_constants"] = constants

    # 确保站点子目录存在
    site_types = getattr(constants, "SITE_TYPES", ())
    outputs_root = root / "outputs" / project_name
    if site_types:
        for site in site_types:
            (outputs_root / site / "origin_exports").mkdir(parents=True, exist_ok=True)
            (outputs_root / site / "excel_exports").mkdir(parents=True, exist_ok=True)
    else:
        (outputs_root / "origin_exports").mkdir(parents=True, exist_ok=True)
        (outputs_root / "excel_exports").mkdir(parents=True, exist_ok=True)

    return {
        "name": project_name,
        "constants": constants,
        "inputs_root": root / "inputs" / project_name,
        "outputs_root": outputs_root,
        "knowledge_base": pdir / "knowledge_base",
        "templates_dir": root / "testcase_templates" / "modules" / project_name,
        "project_dir": pdir,
    }


def _list_projects() -> list[str]:
    """列出所有可用项目。"""
    projects_parent = skill_root() / "projects"
    if not projects_parent.exists():
        return []
    return sorted(
        p.name for p in projects_parent.iterdir()
        if p.is_dir() and (p / "business_constants.py").exists()
    )


def print_available_projects() -> None:
    """打印可用项目列表（用于错误提示）。"""
    projects = _list_projects()
    if projects:
        print("可用项目：")
        for name in projects:
            print(f"  {name}")
    else:
        print("未找到任何项目配置。")
