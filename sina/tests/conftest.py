"""
全局测试夹具：默认把 SINA_DATA_DIR 指向会话级临时目录。

SinaSimulation 的输出根目录取 SINA_DATA_DIR（回落仓库根），所以这个 autouse 夹具
能保证测试既不覆盖仓库里的 world_state_v3_backup.json，也不改写 obsidian_vault/。

它同时让"从存档恢复 vs 从 agents.json 初始化"这条分支在所有机器上表现一致：
否则本地残留的存档会让测试走 `_load_world_state`（class 0.5 / wealth 100），
而 fresh clone 走 `agents.json`，测试结果取决于运行环境。
"""

import os

import pytest


@pytest.fixture(autouse=True, scope="session")
def _isolate_sina_data_dir(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("sina_data")
    previous = os.environ.get("SINA_DATA_DIR")
    os.environ["SINA_DATA_DIR"] = str(tmp)
    try:
        yield tmp
    finally:
        if previous is None:
            os.environ.pop("SINA_DATA_DIR", None)
        else:
            os.environ["SINA_DATA_DIR"] = previous
