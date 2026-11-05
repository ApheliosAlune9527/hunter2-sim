"""Derive a separate control scene from the unchanged, checked preview."""
import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET

from check_control_scene import CONTROLLER, CONTROL_TEXT, CONTROL_NUMBERS, validate_world, validate_gui


def main():
    scenes = Path(__file__).resolve().parent.parent / "scenes"
    preview = scenes / "hz_hunter_preview.sdf"
    gui = scenes / "hz_hunter_preview_gui.config"
    known = {
        preview: "6f1c39a576bd8160a6b703edcce5a55e701aa09128a7b0a504b4a223f7460265",
        gui: "c222fbf73caf00b1ef5f1fb34c7a3b28ca1ee93178a8ef59049917361d9cec09",
    }
    for path, digest in known.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("The checked preview files have changed")
    destination = scenes / "hz_hunter_control.sdf"
    # Desktop copy; the baseline hz_hunter_control.sha256 is left untouched.
    manifest = scenes / "hz_hunter_control_d.sha256"
    control_gui = scenes / "hz_hunter_control_gui.config"
    if destination.exists() or manifest.exists() or control_gui.exists():
        raise FileExistsError("Control scene already exists; refusing to overwrite it")
    gui_text = gui.read_text()
    if gui_text.count("<engine>ogre2</engine>") != 1:
        raise ValueError("Preview GUI renderer is not the checked original")
    gui_text = gui_text.replace("<engine>ogre2</engine>", "<engine>ogre</engine>")
    validate_gui(gui_text)
    root = ET.parse(preview).getroot()
    world = root.find("world")
    world.set("name", "hz_hunter_control")
    vehicle = world.find("model[@name='hz_hunter_core']")
    vehicle.append(ET.Comment("Virtual Gazebo control only; no ROS bridge or hardware driver."))
    plugin = ET.SubElement(vehicle, "plugin", filename=CONTROLLER[0], name=CONTROLLER[1])
    for key, value in {**CONTROL_TEXT, **CONTROL_NUMBERS}.items():
        ET.SubElement(plugin, key).text = str(value)
    validate_world(root)
    ET.indent(root, space="  ")
    data = ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"
    with destination.open("xb") as stream:
        stream.write(data)
    with control_gui.open("x", encoding="utf-8") as stream:
        stream.write(gui_text)
    paths = [destination, control_gui]
    manifest.write_text("".join(
        hashlib.sha256(path.read_bytes()).hexdigest() + "  " +
        "/mnt/d/rob-memory/sim/scenes/" + path.name + "\n" for path in paths),
        encoding="utf-8")
    print("Created separate control scene; preview files unchanged.")


if __name__ == "__main__":
    main()
