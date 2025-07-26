import xml.etree.ElementTree as ET

def is_actionable(node):
    cls = node.attrib.get("class", "")
    clickable = node.attrib.get("clickable", "false") == "true"
    focusable = node.attrib.get("focusable", "false") == "true"
    editable = "EditText" in cls
    checkable = node.attrib.get("checkable", "false") == "true"
    return clickable or focusable or editable or checkable

def extract_ui_elements(xml_str):
    root = ET.fromstring(xml_str)
    elements = []

    for node in root.iter("node"):
        if not is_actionable(node):
            continue

        elements.append({
            "text": node.attrib.get("text", "").strip(),
            "hint": node.attrib.get("hint", "").strip(), 
            "resource_id": node.attrib.get("resource-id", ""),
            "class": node.attrib.get("class", ""),
            "content_desc": node.attrib.get("content-desc", "").strip(),
            "clickable": node.attrib.get("clickable", "false") == "true",
            "focusable": node.attrib.get("focusable", "false") == "true",
            "long_clickable": node.attrib.get("long-clickable", "false") == "true",
            "enabled": node.attrib.get("enabled", "false") == "true",
            "bounds": node.attrib.get("bounds", "")
        })

    return elements
