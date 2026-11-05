"""ZIP entry point. Only installs a new, fixed personal directory."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import socket
import stat
import sys
import zipfile

ROOT = Path("/home/car/hz_ws")
BUNDLE_NAME = "hz_mapping_tools"


class InstallError(RuntimeError):
    pass


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def install_archive(archive, root, expected_sha256):
    root = Path(root).absolute()
    if not root.is_dir() or root.is_symlink() or root.resolve() != root:
        raise InstallError("个人工作区必须是实际目录，不能经过外部链接")
    if not re.fullmatch(r"[a-fA-F0-9]{64}", expected_sha256) or sha256_file(archive) != expected_sha256.lower():
        raise InstallError("安装包 SHA256 不一致，停止安装")
    with zipfile.ZipFile(archive) as z:
        infos = z.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)) or len(names) > 64:
            raise InstallError("安装包含重复文件或文件数异常")
        for info in infos:
            path = PurePosixPath(info.filename)
            if path.is_absolute() or ".." in path.parts or "\\" in info.filename or ":" in info.filename or info.is_dir() or stat.S_ISLNK(info.external_attr >> 16):
                raise InstallError("安装包含不安全路径或符号链接")
            if info.file_size > 8 * 1024 ** 2:
                raise InstallError("安装包文件大小异常")
        try:
            manifest_bytes = z.read("manifest.json")
            manifest = json.loads(manifest_bytes)
            files = manifest["files"]
            if manifest["format"] != "hz_mapping_tools_bundle_v1" or manifest["bundle_name"] != BUNDLE_NAME or not isinstance(files, dict):
                raise InstallError("安装包版本或格式错误")
            if set(names) != {"__main__.py", "manifest.json", *("payload/" + name for name in files)}:
                raise InstallError("安装包含清单外文件")
            payload = {}
            for name, digest in files.items():
                if not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or name in (".", "..", "bundle_manifest.json"):
                    raise InstallError("交付文件名称异常")
                data = z.read("payload/" + name)
                if hashlib.sha256(data).hexdigest() != digest:
                    raise InstallError(f"文件 SHA256 校验失败：{name}")
                payload[name] = data
            dependencies = json.loads(payload["compatibility.json"])["files"]
        except (KeyError, ValueError, TypeError) as exc:
            raise InstallError("安装包清单格式错误") from exc
    required_helpers = {"scripts/hz_mapping_session.py", "scripts/pcd_export.py"}
    if set(dependencies) != required_helpers:
        raise InstallError("依赖校验清单错误")
    for relative, digest in dependencies.items():
        path = root / relative
        if not path.resolve().is_relative_to(root) or not path.is_file() or sha256_file(path) != digest:
            raise InstallError(f"已有依赖版本校验不一致，不覆盖：{path}")
    target = root / BUNDLE_NAME
    installed = dict(payload, **{"bundle_manifest.json": manifest_bytes})
    if target.exists() or target.is_symlink():
        if target.is_symlink() or not target.is_dir() or target.resolve() != target:
            raise InstallError(f"目标已存在且不是实际目录，不覆盖：{target}")
        if {p.name for p in target.iterdir()} != set(installed):
            raise InstallError(f"目标已存在且内容不同，不覆盖：{target}")
        for name, data in installed.items():
            file = target / name
            if file.is_symlink() or not file.is_file() or file.read_bytes() != data:
                raise InstallError(f"目标文件已存在且内容不同，不覆盖：{file}")
        return target
    # mkdir is exclusive: a concurrently created directory is never replaced.
    try:
        target.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise InstallError("目标刚被其他安装进程创建；停止并核对") from exc
    try:
        for name, data in installed.items():
            with (target / name).open("xb") as out:
                out.write(data)
            os.chmod(target / name, 0o600)
    except Exception as exc:
        raise InstallError(f"安装未完成，已写入的新目录保留供核对，不清理或覆盖旧文件：{target}") from exc
    return target


def main():
    parser = argparse.ArgumentParser(description="安装个人 FAST-LIVO2 最终入口，不覆盖已有工程")
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    if sys.platform != "linux" or socket.gethostname() != "car-NUC15JNKU7X4" or os.getuid() != ROOT.stat().st_uid:
        raise InstallError("只能由个人工作区所有者在指定小车上安装")
    archive = Path(sys.argv[0]).absolute()
    if archive.parent != ROOT or archive.is_symlink() or not re.fullmatch(r"\.hz_mapping_upload_[a-f0-9]{32}\.zip", archive.name):
        raise InstallError("上传位置不符合固定个人路径")
    target = install_archive(archive, ROOT, args.sha256)
    print(f"安装内容核对通过：{target}", flush=True)
    archive.unlink()  # Only this unique upload, after full hash verification.
    print("本次临时上传包已移除；已有工程、配置和地图未改写。", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"安装停止：{exc}", file=sys.stderr)
        sys.exit(1)
