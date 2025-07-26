import xml.etree.ElementTree as ET
import json
import re

def parse_bounds(bounds_str):
    """Turn bounds string like [100,200][400,300] → center point (x, y)"""
    matches = re.findall(r'\[(\d+),(\d+)\]', bounds_str)
    if len(matches) != 2:
        return None
    (x1, y1), (x2, y2) = map(lambda m: (int(m[0]), int(m[1])), matches)
    return {"x": (x1 + x2) // 2, "y": (y1 + y2) // 2}

def is_actionable(node):
    cls = node.attrib.get("class", "")
    clickable = node.attrib.get("clickable", "false") == "true"
    focusable = node.attrib.get("focusable", "false") == "true"
    editable = "EditText" in cls
    tickable = any(x in cls for x in ["CheckBox", "Switch", "ToggleButton"])

    return clickable or focusable or editable or tickable

def extract_ui_elements(xml_path="view.xml", output_path="ui_elements.json"):
    tree = ET.parse(xml_path)
    root = tree.getroot()

    elements = []

    for node in root.iter("node"):
        if not is_actionable(node):
            continue

        bounds = node.attrib.get("bounds")
        center = parse_bounds(bounds) if bounds else None
        if not center:
            continue

        elements.append({
            "text": node.attrib.get("text", "").strip(),
            "resource_id": node.attrib.get("resource-id", ""),
            "class": node.attrib.get("class", ""),
            "bounds": bounds,
            "center": center,
            "clickable": node.attrib.get("clickable", "false") == "true",
            "focusable": node.attrib.get("focusable", "false") == "true",
            "focused": node.attrib.get("focused", "false") == "true"
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(elements, f, indent=2, ensure_ascii=False)

    print(f"✅ Saved {len(elements)} actionable elements to {output_path}")

if __name__ == "__main__":
    extract_ui_elements()
