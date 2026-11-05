"""Validate and merge the numbered binary PCDs; standard library only."""
import argparse
import hashlib
import json
import math
import re
import shutil
import struct
import tarfile
import tempfile
from pathlib import Path, PurePosixPath


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def pcd_info(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError(f"PCD 不接受符号链接：{path}")
    header = {}
    with path.open("rb") as f:
        while f.tell() < 65536:
            line = f.readline()
            if not line:
                raise ValueError(f"PCD 缺少 DATA：{path}")
            words = line.decode("ascii").strip().split()
            if not words or words[0].startswith("#"):
                continue
            key = words[0].upper()
            header[key] = words[1:]
            if key == "DATA":
                offset = f.tell()
                break
        else:
            raise ValueError(f"PCD 头部过长：{path}")
    if header.get("DATA") != ["binary"]:
        raise ValueError(f"仅支持 DATA binary：{path}")
    fields = header["FIELDS"]
    sizes = list(map(int, header["SIZE"]))
    types = header["TYPE"]
    counts = list(map(int, header.get("COUNT", ["1"] * len(fields))))
    if not (len(fields) == len(sizes) == len(types) == len(counts)) or any(x <= 0 for x in sizes + counts):
        raise ValueError(f"PCD 字段定义不完整：{path}")
    points = int(header["POINTS"][0])
    width = int(header["WIDTH"][0])
    height = int(header["HEIGHT"][0])
    step = sum(a * b for a, b in zip(sizes, counts))
    if points < 0 or width * height != points:
        raise ValueError(f"PCD 点数不一致：{path}")
    expected = offset + points * step
    if path.stat().st_size != expected:
        raise ValueError(f"PCD 数据字节不完整：{path.name} 实际 {path.stat().st_size}，应有 {expected}")
    return {"path": str(path), "points": points, "offset": offset, "step": step,
            "fields": fields, "sizes": sizes, "types": types, "counts": counts,
            "viewpoint": header.get("VIEWPOINT", ["0", "0", "0", "1", "0", "0", "0"])}


def validate_pcd_dir(directory):
    paths = sorted((p for p in Path(directory).glob("*.pcd") if re.fullmatch(r"[0-9]+\.pcd", p.name)),
                   key=lambda p: int(p.stem))
    if not paths:
        raise ValueError(f"没有本轮编号 PCD：{directory}")
    infos = [pcd_info(p) for p in paths]
    layout_keys = ("fields", "sizes", "types", "counts", "viewpoint")
    if any(any(item[k] != infos[0][k] for k in layout_keys) for item in infos):
        raise ValueError("各 PCD 的字段或 VIEWPOINT 不一致，不能直接合并")
    total = sum(p["points"] for p in infos)
    if total == 0:
        raise ValueError("本轮 PCD 全部为空")
    return {"files": infos, "file_count": len(infos), "total_points": total}


def pcd_header(info, points):
    lines = ["# .PCD v0.7", "VERSION 0.7"]
    for label, key in (("FIELDS", "fields"), ("SIZE", "sizes"), ("TYPE", "types"), ("COUNT", "counts")):
        lines.append(label + " " + " ".join(map(str, info[key])))
    lines += [f"WIDTH {points}", "HEIGHT 1", "VIEWPOINT " + " ".join(info["viewpoint"]),
              f"POINTS {points}", "DATA binary"]
    return ("\n".join(lines) + "\n").encode("ascii")


def merge_pcd(directory, output, voxel=0.15):
    if not math.isfinite(voxel) or voxel <= 0:
        raise ValueError("体素尺寸必须为正数")
    report = validate_pcd_dir(directory)
    info = report["files"][0]
    offsets = {}
    offset = 0
    for field, size, kind, count in zip(info["fields"], info["sizes"], info["types"], info["counts"]):
        if field in ("x", "y", "z"):
            if size != 4 or kind != "F" or count != 1:
                raise ValueError("预览要求 x/y/z 为 float32")
            offsets[field] = offset
        offset += size * count
    if set(offsets) != {"x", "y", "z"}:
        raise ValueError("PCD 缺少 x/y/z")
    output = Path(output)
    raw = output / "map_raw.pcd"
    preview = output / "map_preview_015m.pcd"
    if raw.exists() or preview.exists():
        raise FileExistsError("目标地图已存在，不覆盖；请使用新目录")
    output.mkdir(parents=True, exist_ok=True)
    voxels = {}
    with raw.open("xb") as dst:
        dst.write(pcd_header(info, report["total_points"]))
        for item in report["files"]:
            with Path(item["path"]).open("rb") as src:
                src.seek(item["offset"])
                for block in iter(lambda: src.read(info["step"] * 4096), b""):
                    dst.write(block)
                    for at in range(0, len(block), info["step"]):
                        xyz = [struct.unpack_from("<f", block, at + offsets[k])[0] for k in ("x", "y", "z")]
                        if not all(math.isfinite(v) for v in xyz):
                            continue
                        key = tuple(math.floor(v / voxel) for v in xyz)
                        if key not in voxels:
                            voxels[key] = block[at:at + info["step"]]
    with preview.open("xb") as dst:
        dst.write(pcd_header(info, len(voxels)))
        dst.writelines(voxels.values())
    pcd_info(raw)
    pcd_info(preview)
    return {"raw_points": report["total_points"], "preview_points": len(voxels),
            "raw": str(raw), "preview": str(preview)}


def unpack_map(archive, destination):
    archive = Path(archive)
    run_name = archive.name.removesuffix(".tar.gz")
    if not re.fullmatch(r"lab_[0-9_]+", run_name):
        raise ValueError("归档名称不符合本轮地图格式")
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    final = destination / run_name
    if final.exists():
        raise FileExistsError(f"本轮目录已存在，不覆盖：{final}")
    with tempfile.TemporaryDirectory(prefix="hz_unpack_", dir=destination) as staging:
        staging = Path(staging).resolve()
        if staging.parent != destination:
            raise ValueError("解包临时目录不在接收目录内")
        with tarfile.open(archive, "r:gz") as tar:
            for member in tar:
                p = PurePosixPath(member.name)
                if p.is_absolute() or ".." in p.parts or not p.parts or p.parts[0] != run_name:
                    raise ValueError("归档包含危险路径")
                if "\\" in member.name or ":" in member.name or not (member.isfile() or member.isdir()):
                    raise ValueError("归档包含不支持的链接或路径")
                target = staging.joinpath(*p.parts)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with tar.extractfile(member) as src, target.open("xb") as dst:
                        shutil.copyfileobj(src, dst)
        validate_pcd_dir(staging / run_name / "pcd")
        (staging / run_name).rename(final)
    return final


def main():
    parser = argparse.ArgumentParser(description="PCD 检查、解包、合并")
    parser.add_argument("action", choices=("check", "merge", "unpack"))
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", nargs="?", type=Path)
    parser.add_argument("--sha256")
    args = parser.parse_args()
    if args.sha256 and sha256_file(args.source).lower() != args.sha256.lower():
        raise ValueError("归档 SHA256 不一致，停止解包")
    if args.action == "check":
        result = validate_pcd_dir(args.source)
        print(json.dumps({k: v for k, v in result.items() if k != "files"}, ensure_ascii=False))
    elif args.destination is None:
        parser.error("需要目标目录")
    elif args.action == "merge":
        print(json.dumps(merge_pcd(args.source, args.destination), ensure_ascii=False, indent=2))
    else:
        print(unpack_map(args.source, args.destination))


if __name__ == "__main__":
    main()
