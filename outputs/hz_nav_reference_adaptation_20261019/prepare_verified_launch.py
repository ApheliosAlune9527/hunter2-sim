"""Build narrowly adapted Nav2 launch copies from hash-verified car evidence."""

from __future__ import annotations

import ast
import copy
import difflib
import gzip
import hashlib
import io
import json
import re
import tarfile
from pathlib import Path


OUT = Path(__file__).resolve().parent
ATTACHMENTS = Path("C:/Users/Aphelios/.codex/attachments")
SOURCE = {
    "bringup_launch.py": (
        "04fda6f8-67f9-463e-8d74-13eca059af71",
        "91460eb80d7b5d0bbb72eb5ac52bad6439ae2175c31be86c8ec256fd4bbee3c6",
    ),
    "localization_launch.py": (
        "d090dd77-813d-4f0c-a6ba-f9b39739f838",
        "13d9ac3c7c27cba61570501f1ea41dafd63f8e3a08962f803f6281e426d995c2",
    ),
    "navigation_launch.py": (
        "d090dd77-813d-4f0c-a6ba-f9b39739f838",
        "11438a4bc65def4a3d5805919e82bc52ff6008ee6d1fd7c5dd90a29c2f50f56f",
    ),
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def reconstruct_sources() -> dict[str, str]:
    result = {}
    for folder in dict.fromkeys(item[0] for item in SOURCE.values()):
        text = (ATTACHMENTS / folder / "已粘贴的文本.txt").read_text(
            encoding="utf-8"
        )
        commands = list(
            re.finditer(
                r"^car@[^\n]*\$ sed[^\n]*/([a-z_]+_launch\.py)[^\n]*\n",
                text,
                re.M,
            )
        )
        for index, command in enumerate(commands):
            name = command.group(1)
            end = commands[index + 1].start() if index + 1 < len(commands) else len(text)
            body = text[command.end() : end].rstrip("\n")
            variants = [body + "\n" * count for count in range(5)]
            matches = [s for s in variants if digest(s.encode()) == SOURCE[name][1]]
            if len(matches) != 1:
                raise RuntimeError(f"Exact source reconstruction failed: {name}")
            result[name] = matches[0]
    if set(result) != set(SOURCE):
        raise RuntimeError("Missing source file")
    return result


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"Expected exactly one source fragment: {old!r}")
    return text.replace(old, new, 1)


def adapt(name: str, original: str) -> str:
    text = replace_once(original, "('/tf', 'tf')", "('/tf', '/tf')")
    text = replace_once(text, "('/tf_static', 'tf_static')", "('/tf_static', '/tf_static')")
    if name != "bringup_launch.py":
        return text

    anchor = "    launch_dir = os.path.join(bringup_dir, 'launch')\n"
    text = replace_once(
        text,
        anchor,
        anchor + "    personal_launch_dir = os.path.dirname(os.path.abspath(__file__))\n",
    )
    text = replace_once(
        text,
        "'namespace',\n        default_value='',",
        "'namespace',\n        default_value='hz_nav',",
    )
    text = replace_once(
        text,
        "'use_namespace',\n        default_value='false',",
        "'use_namespace',\n        default_value='true',",
    )
    text = replace_once(
        text,
        "default_value=os.path.join(bringup_dir, 'params', 'nav2_params.yaml'),",
        "default_value=os.path.join(os.path.dirname(personal_launch_dir), 'config', 'nav2_params.yaml'),",
    )
    text = replace_once(
        text,
        "'autostart', default_value='true',",
        "'autostart', default_value='false',",
    )
    for child in ("localization_launch.py", "navigation_launch.py"):
        pattern = r"os\.path\.join\(launch_dir,(\s*'" + re.escape(child) + r"')\)"
        text, count = re.subn(
            pattern,
            lambda match: "os.path.join(personal_launch_dir," + match.group(1) + ")",
            text,
        )
        if count != 1:
            raise RuntimeError(f"Expected one child include: {child}")
    return text


def function_name(call: ast.Call) -> str:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return ""


def calls(tree: ast.AST, name: str) -> list[ast.Call]:
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call) and function_name(n) == name]


def assignment(tree: ast.AST, name: str):
    found = [
        n.value
        for n in ast.walk(tree)
        if isinstance(n, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == name for target in n.targets)
    ]
    if len(found) != 1:
        raise RuntimeError(f"Expected exactly one assignment: {name}")
    return found[0]


def declared_defaults(tree: ast.AST) -> dict[str, str | None]:
    result = {}
    for call in calls(tree, "DeclareLaunchArgument"):
        name = ast.literal_eval(call.args[0])
        defaults = [kw.value for kw in call.keywords if kw.arg == "default_value"]
        result[name] = ast.dump(defaults[0]) if defaults else None
    return result


def validate(name: str, original: str, adapted: str) -> dict:
    before = ast.parse(original, feature_version=(3, 10))
    after = ast.parse(adapted, feature_version=(3, 10))
    for constructor in ("Node", "ComposableNode", "GroupAction", "LoadComposableNodes"):
        old_calls = [ast.dump(node) for node in calls(before, constructor)]
        normalized_calls = copy.deepcopy(calls(after, constructor))
        if name == "bringup_launch.py" and constructor == "GroupAction":
            for call in normalized_calls:
                for node in ast.walk(call):
                    if isinstance(node, ast.Name) and node.id == "personal_launch_dir":
                        node.id = "launch_dir"
        new_calls = [ast.dump(node) for node in normalized_calls]
        if old_calls != new_calls:
            raise RuntimeError(f"Original {constructor} declarations changed: {name}")

    expected_tf = [("/tf", "/tf"), ("/tf_static", "/tf_static")]
    if ast.literal_eval(assignment(after, "remappings")) != expected_tf:
        raise RuntimeError(f"Global TF endpoints invalid: {name}")

    before_imports = [ast.dump(n) for n in ast.walk(before) if isinstance(n, (ast.Import, ast.ImportFrom))]
    after_imports = [ast.dump(n) for n in ast.walk(after) if isinstance(n, (ast.Import, ast.ImportFrom))]
    if before_imports != after_imports:
        raise RuntimeError(f"Imports changed: {name}")

    old_defaults = declared_defaults(before)
    new_defaults = declared_defaults(after)
    changed_defaults = sorted(
        key for key in set(old_defaults) | set(new_defaults)
        if old_defaults.get(key) != new_defaults.get(key)
    )
    allowed_defaults = ["autostart", "namespace", "params_file", "use_namespace"] if name == "bringup_launch.py" else []
    if changed_defaults != allowed_defaults:
        raise RuntimeError(f"Unexpected launch argument changes: {name}: {changed_defaults}")

    if name == "bringup_launch.py":
        for key, value in {"namespace": "hz_nav", "use_namespace": "true", "autostart": "false"}.items():
            if new_defaults[key] != ast.dump(ast.Constant(value=value)):
                raise RuntimeError(f"Wrong personal default: {key}")
        if new_defaults["map"] is not None:
            raise RuntimeError("Map must still be explicitly specified")
        if ast.dump(assignment(after, "personal_launch_dir")) != ast.dump(
            ast.parse("os.path.dirname(os.path.abspath(__file__))", mode="eval").body
        ):
            raise RuntimeError("Personal launch root is not based on this file")
        expected_parameter_default = ast.dump(
            ast.parse("os.path.join(os.path.dirname(personal_launch_dir), 'config', 'nav2_params.yaml')", mode="eval").body
        )
        if new_defaults["params_file"] != expected_parameter_default:
            raise RuntimeError("Personal parameter path invalid")

        include_paths = {}
        for include in calls(after, "PythonLaunchDescriptionSource"):
            path_call = include.args[0]
            include_paths[ast.literal_eval(path_call.args[1])] = path_call.args[0].id
        if include_paths != {
            "slam_launch.py": "launch_dir",
            "localization_launch.py": "personal_launch_dir",
            "navigation_launch.py": "personal_launch_dir",
        }:
            raise RuntimeError(f"Wrong child source paths: {include_paths}")

        old_includes = calls(before, "IncludeLaunchDescription")
        normalized_includes = copy.deepcopy(calls(after, "IncludeLaunchDescription"))
        for include in normalized_includes:
            for node in ast.walk(include):
                if isinstance(node, ast.Name) and node.id == "personal_launch_dir":
                    node.id = "launch_dir"
        if [ast.dump(n) for n in old_includes] != [ast.dump(n) for n in normalized_includes]:
            raise RuntimeError("Child launch conditions or arguments changed")
    elif ast.dump(assignment(before, "lifecycle_nodes")) != ast.dump(assignment(after, "lifecycle_nodes")):
        raise RuntimeError("Lifecycle node list changed")

    return {
        "python_3_10_syntax": "passed",
        "node_and_component_declarations": "unchanged",
        "group_and_loading_actions": "unchanged apart from verified child source paths" if name == "bringup_launch.py" else "unchanged",
        "velocity_remappings": "unchanged",
        "lifecycle_node_list": "unchanged" if name != "bringup_launch.py" else "in child files",
        "changed_launch_argument_defaults": changed_defaults,
        "tf_endpoints": expected_tf,
    }


def write_once_or_identical(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise RuntimeError(f"Refusing to overwrite a different file: {path}")
        return
    with path.open("xb") as handle:
        handle.write(data)


def main() -> None:
    originals = reconstruct_sources()
    adapted_files = {name: adapt(name, text) for name, text in originals.items()}
    checks = {
        name: validate(name, originals[name], adapted_files[name])
        for name in SOURCE
    }
    diff = "".join(
        line
        for name in SOURCE
        for line in difflib.unified_diff(
            originals[name].splitlines(keepends=True),
            adapted_files[name].splitlines(keepends=True),
            fromfile=f"/opt/ros/humble/share/nav2_bringup/launch/{name}",
            tofile=f"/home/car/hz_nav_ws/launch/{name}",
        )
    )

    uncompressed = io.BytesIO()
    with tarfile.open(fileobj=uncompressed, mode="w") as archive:
        for name, text in adapted_files.items():
            data = text.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o644
            info.mtime = 0
            archive.addfile(info, io.BytesIO(data))
    compressed = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed, mode="wb", filename="", mtime=0) as stream:
        stream.write(uncompressed.getvalue())
    archive_bytes = compressed.getvalue()
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as archive:
        if archive.getnames() != list(SOURCE):
            raise RuntimeError("Archive contains unexpected paths")
        for member in archive.getmembers():
            if not member.isfile() or archive.extractfile(member).read() != adapted_files[member.name].encode():
                raise RuntimeError("Unsafe or incorrect archive member")

    files = {}
    for name in SOURCE:
        data = adapted_files[name].encode()
        write_once_or_identical(OUT / "reference" / name, originals[name].encode())
        write_once_or_identical(OUT / "launch" / name, data)
        files[name] = {
            "source_sha256": SOURCE[name][1],
            "adapted_sha256": digest(data),
            "bytes": len(data),
            "verification": checks[name],
        }

    archive_name = "nav2_launch_personal.tar.gz"
    report = {
        "date": "2026-10-19",
        "source": "Car-provided files, reconstructed only when original SHA256 matches",
        "files": files,
        "archive": {"name": archive_name, "sha256": digest(archive_bytes), "members": list(SOURCE)},
        "car_runtime_validation": "not performed; only static validation on Windows",
        "configuration_status": "car nav2_params.yaml still original; topic/path adaptations pending",
        "chassis": "not started; source enables commanded mode and releases brake",
    }
    write_once_or_identical(OUT / "launch_changes.diff", diff.encode())
    write_once_or_identical(OUT / archive_name, archive_bytes)
    write_once_or_identical(OUT / "validation.json", (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
