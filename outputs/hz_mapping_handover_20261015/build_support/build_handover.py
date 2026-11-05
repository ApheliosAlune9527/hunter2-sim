"""Build and check the reusable text-first handover; never connects to the robot."""
import ast
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

sys.dont_write_bytecode = True
PROJECT = Path(__file__).resolve().parents[1]
DELIVERY = PROJECT / "deliverables"
FINAL = Path("E:/robot_lab/FAST-LIVO2建图使用包")
TOOLS = PROJECT / "tests/fixtures/tools"
sys.path.insert(0, str(PROJECT / "package"))
from installer import install_archive
import hz_launch_support as support


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def put(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise RuntimeError(f"Existing file differs; refusing to overwrite: {path}")
    else:
        with path.open("xb") as stream:
            stream.write(data)


def archive(path, files):
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2026, 10, 15, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100600 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            output.writestr(info, data)
    put(path, memory.getvalue())


def environment():
    return {key: value for key, value in dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8").items() if key.upper() != "PSMODULEPATH"}


def checked(command, cwd=None):
    result = subprocess.run(command, cwd=cwd, env=environment(), capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError(result.stdout + "\n" + result.stderr)
    return result.stdout.strip()


def main():
    live_path = PROJECT / "robot_validation_20261016.json"
    live = json.loads(live_path.read_text(encoding="utf-8")) if live_path.exists() else {}
    guide_check_path = PROJECT / "guide_verification_20261016.json"
    guide_check = json.loads(guide_check_path.read_text(encoding="utf-8")) if guide_check_path.exists() else {}
    old_sources = [TOOLS / name for name in ("hz_mapping_session.py", "pcd_export.py")]
    original = {str(path): sha(path) for path in old_sources}
    assert support.BUNDLE_NAME == "hz_mapping_tools"
    expected = json.loads((PROJECT / "package/compatibility.json").read_text(encoding="utf-8"))["files"]
    assert all(sha(TOOLS / Path(name).name) == digest for name, digest in expected.items())
    unit_log = io.StringIO()
    with contextlib.redirect_stdout(unit_log):
        suite = unittest.defaultTestLoader.discover(str(PROJECT / "tests"))
        result = unittest.TextTestRunner(stream=unit_log, verbosity=2).run(suite)
    (PROJECT / "unit_test_output.txt").write_text(unit_log.getvalue(), encoding="utf-8")
    if not result.wasSuccessful():
        raise RuntimeError(unit_log.getvalue())
    payload = {p.name: p.read_bytes() for p in (PROJECT / "package").iterdir() if p.is_file()}
    assert set(payload) == {"hz_env.sh", "hz_mapping.launch.py", "hz_launch_support.py", "hz_diagnose.py", "compatibility.json"}
    for name, data in payload.items():
        assert b"hz_final_20261015" not in data and b"\r\n" not in data, name
    bundle_manifest = {"format": "hz_mapping_tools_bundle_v1", "bundle_name": support.BUNDLE_NAME, "files": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(payload.items())}}
    robot_zip = DELIVERY / "hz_mapping_tools.zip"
    robot_files = {"__main__.py": (PROJECT / "build_support/installer.py").read_bytes(), "manifest.json": json.dumps(bundle_manifest, indent=2).encode("utf-8") + b"\n"}
    robot_files.update({"payload/" + name: data for name, data in payload.items()})
    archive(robot_zip, robot_files)
    put(DELIVERY / "hz_mapping_tools.zip.sha256", (sha(robot_zip) + "  hz_mapping_tools.zip\n").encode("ascii"))
    for source in (PROJECT / "delivery_src").iterdir():
        put(DELIVERY / source.name, source.read_text(encoding="utf-8-sig").encode("utf-8-sig"))
    put(DELIVERY / "pcd_export.py", (TOOLS / "pcd_export.py").read_bytes())
    compiled = []
    for directory in ("package", "build_support", "tests"):
        for source in sorted((PROJECT / directory).rglob("*.py")):
            text = source.read_text(encoding="utf-8-sig")
            ast.parse(text, feature_version=(3, 10), filename=str(source))
            compile(text, str(source), "exec")
            compiled.append(source.relative_to(PROJECT).as_posix())
    checked(["F:/w64devkit/bin/bash.exe", "-n", (PROJECT / "package/hz_env.sh").as_posix()])
    powershell = json.loads(checked(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(PROJECT / "build_support/verify_powershell.ps1"), "-Directory", str(DELIVERY)]))
    check_only = checked(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(DELIVERY / "安装建图工具.ps1"), "-CheckOnly"], cwd=DELIVERY)
    with tempfile.TemporaryDirectory(prefix="hz_tools_handover_check_") as temporary:
        root = Path(temporary) / "hz_ws"
        (root / "scripts").mkdir(parents=True)
        for name in ("hz_mapping_session.py", "pcd_export.py"):
            shutil.copyfile(TOOLS / name, root / "scripts" / name)
        before = {p.name: p.read_bytes() for p in (root / "scripts").iterdir()}
        target = install_archive(robot_zip, root, sha(robot_zip))
        assert target.name == "hz_mapping_tools"
        stamps = {p.name: p.stat().st_mtime_ns for p in target.iterdir()}
        assert install_archive(robot_zip, root, sha(robot_zip)) == target
        assert stamps == {p.name: p.stat().st_mtime_ns for p in target.iterdir()}
        assert before == {p.name: p.read_bytes() for p in (root / "scripts").iterdir()}
        assert all((target / name).read_bytes() == data for name, data in payload.items())
        bad_folder = Path(temporary) / "changed_zip"
        bad_folder.mkdir()
        for name in ("安装建图工具.ps1", "hz_mapping_tools.zip", "hz_mapping_tools.zip.sha256"):
            shutil.copyfile(DELIVERY / name, bad_folder / name)
        with (bad_folder / "hz_mapping_tools.zip").open("ab") as stream:
            stream.write(b"changed")
        bad = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(bad_folder / "安装建图工具.ps1"), "-CheckOnly"], env=environment(), capture_output=True, text=True, encoding="utf-8", errors="replace")
        assert bad.returncode != 0 and "本地安装包 SHA256 校验失败" in bad.stdout + bad.stderr
    guide = (DELIVERY / "建图使用说明.txt").read_text(encoding="utf-8-sig")
    assert set(re.findall(r'ros2 launch "\$hzLaunch" role:=(\w+)', guide)) == set(support.ROLES)
    assert "hz_final" not in guide and ".md" not in guide and "待填写" not in guide
    assert "powershell -NoProfile -ExecutionPolicy Bypass -File \".\\安装建图工具.ps1\"" in guide
    assert "powershell -NoProfile -ExecutionPolicy Bypass -File \".\\下载地图.ps1\" -RobotIp $hzRobotIp" in guide
    assert guide.index("role:=prepare") < guide.index("role:=lidar") < guide.index("role:=imu") < guide.index("role:=camera") < guide.index("role:=mapping")
    assert guide.index("role:=check") < guide.index("role:=merge") < guide.index("role:=pack") < guide.index('".\\下载地图.ps1"')
    assert (DELIVERY / "下载地图.ps1").read_text(encoding="utf-8-sig") == (PROJECT / "delivery_src/下载地图.ps1").read_text(encoding="utf-8-sig")
    assert (DELIVERY / "pcd_export.py").read_bytes() == (TOOLS / "pcd_export.py").read_bytes()
    report = {"date": "2026-10-16", "robot_directory": "/home/car/hz_ws/hz_mapping_tools", "scope": "offline_build_checks_and_separately_attributed_user_evidence", "tests": {"count": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped)}, "python_310_syntax": compiled, "powershell": powershell, "bash_syntax": "PASS", "real_zip_install_and_repeat": "PASS", "check_only": check_only, "tampered_zip_refused": True, "txt_roles": sorted(set(re.findall(r'role:=(\w+)', guide))), "robot_zip_sha256": sha(robot_zip), "old_files_sha256": original, "robot_install_and_runtime": live or "not_performed", "guide_command_verification": guide_check}
    (PROJECT / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_text = f"""建图使用包离线核验记录
日期：2026-10-16
机器人新增目录：/home/car/hz_ws/hz_mapping_tools
主操作文件：建图使用说明.txt

现有 {result.testsRun} 项隔离行为/契约测试通过，零失败、零错误、零跳过。
覆盖旧 PCD 与日志保护、路径边界、分批保存参数、输入话题、重复节点、
日志复制、旧 stop/watch 进程识别和安装不覆盖。
launch 适配层测试替代了 ROS 导入，不作为 ROS 运行或实车证据。
真实 ZIP 在隔离目录安装、内容比较及重复安装不重写：通过。
shell 语法与 Python 3.10 语法兼容检查：通过。
Windows PowerShell {powershell['version']} 脚本解析与本地安装检查：通过。
故意修改 ZIP 后安装脚本拒绝继续：通过。
TXT 包含全部 {len(support.ROLES)} 个操作角色，安装、启动、保存和下载顺序已核对。
Windows 下载工具仅把默认目标改为当前用户 Documents/HunterMaps；
原点云解包、校验、合并逻辑和 pcd_export.py 保持不变。
包内底层参考脚本打包前后 SHA256 一致；构建无需读取旧交付目录。

默认教程已改为异地 ToDesk 文件传输、Ubuntu 安装及预检；SSH 方法放在可选附录。
地图回传同样使用 ToDesk，Windows 本地核对 SHA256 后解包和合并。
ToDesk 章节 10 条 Ubuntu 安装命令 Bash 语法检查：{guide_check.get('bash_syntax', '未记录')}。
Windows 章节 10 条命令 PowerShell 5.1 解析及临时样例处理：{guide_check.get('exact_windows_guide_workflow', '未记录')}。
样例为 2 个 PCD / 3 个点，合并原始记录保持一致、预览为 2 点；重复解包和错误 SHA256 被拒绝。
该样例验证不代表真实 ToDesk 地图传输已经完成。

机器人 ZIP SHA256：{sha(robot_zip)}
本次包只包含使用工具、TXT 和校验资料，不包含 PPT、PNG 或历史地图。
机器人安装与 doctor 证据来源：{live.get('source', '尚无实车记录')}。
用户于 2026-10-16 回传安装成功、加载环境和 doctor 通过输出：{bool(live.get('doctor_passed'))}。
仅这一部分已在指定小车上验证；新入口的传感器、建图、监测及地图回传仍待实测。
本构建程序只做本机隔离检查，不连接小车，也不启动真实传感器或算法。
"""
    put(DELIVERY / "校验资料/验证报告.txt", report_text.encode("utf-8-sig"))
    source_files = {}
    for directory in ("package", "build_support", "tests", "delivery_src"):
        for source in sorted((PROJECT / directory).rglob("*")):
            if source.is_file() and "__pycache__" not in source.parts:
                source_files[source.relative_to(PROJECT).as_posix()] = source.read_bytes()
    for name in ("verification.json", "unit_test_output.txt", "robot_validation_20261016.json", "guide_verification_20261016.json"):
        if not (PROJECT / name).exists():
            continue
        source_files[name] = (PROJECT / name).read_bytes()
    archive(DELIVERY / "校验资料/审阅源码.zip", source_files)
    for file in DELIVERY.rglob("*"):
        assert file.suffix.lower() not in (".pptx", ".ppt", ".png", ".pcd"), file
        if file.suffix == ".zip":
            with zipfile.ZipFile(file) as z:
                assert z.testzip() is None
                assert not any(Path(name).suffix.lower() in (".pptx", ".ppt", ".png", ".pcd") for name in z.namelist())
    hashes = {p.relative_to(DELIVERY).as_posix(): {"bytes": p.stat().st_size, "sha256": sha(p)} for p in sorted(DELIVERY.rglob("*")) if p.is_file()}
    put(DELIVERY / "校验资料/文件清单_SHA256.json", (json.dumps({"files": hashes, "robot_runtime_verified": False, "robot_install_and_doctor_verified": bool(live.get('doctor_passed')), "robot_mapping_roles_verified": False, "robot_map_return_verified": False}, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    if FINAL.exists():
        raise RuntimeError("Final folder already exists; inspect before copying")
    FINAL.mkdir()
    for source in sorted(DELIVERY.rglob("*")):
        if source.is_file():
            target = FINAL / source.relative_to(DELIVERY)
            put(target, source.read_bytes())
            assert sha(target) == sha(source)
    final_zip = FINAL.with_suffix(".zip")
    final_files = {FINAL.name + "/" + p.relative_to(FINAL).as_posix(): p.read_bytes() for p in FINAL.rglob("*") if p.is_file()}
    archive(final_zip, final_files)
    with zipfile.ZipFile(final_zip) as z:
        assert z.testzip() is None
        assert all(z.read(name) == data for name, data in final_files.items())
    assert original == {str(path): sha(path) for path in old_sources}
    final_result = {"folder": str(FINAL), "guide": str(FINAL / "建图使用说明.txt"), "zip": str(final_zip), "zip_bytes": final_zip.stat().st_size, "zip_sha256": sha(final_zip), "tests": result.testsRun, "files": len(final_files), "robot_runtime": "installation_and_doctor_passed; mapping_not_verified" if live.get('doctor_passed') else "not_run"}
    (PROJECT / "handover_result.json").write_text(json.dumps(final_result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(final_result, ensure_ascii=False))


if __name__ == "__main__":
    main()
