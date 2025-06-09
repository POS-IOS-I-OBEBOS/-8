from __future__ import annotations
import os
import uuid
import logging
from xml.etree.ElementTree import Element, SubElement, ElementTree


logger = logging.getLogger(__name__)


def generate_xml(data: dict) -> str:
    logger.info("Generating XML")
    logger.debug("Data: %s", data)
    root = Element("KitchenResources")

    statuses_el = SubElement(root, "Statuses")
    for name, color in data.get("statuses", {}).items():
        SubElement(statuses_el, "Status", name=name, color=color)

    text_el = SubElement(root, "TextStyle")
    text_el.set("color", data.get("text_color", "#000000"))
    text_el.set("size", str(data.get("text_size", "12")))

    panel_el = SubElement(root, "PanelStyle")
    panel_el.set("background", data.get("panel_bg", "#ffffff"))

    grid_el = SubElement(root, "Grid")
    grid_el.set("columns", str(data.get("columns", 2)))
    grid_el.set("rows", str(data.get("rows", 2)))

    flags_el = SubElement(root, "Flags")
    for key in ("blinkOnChange", "groupOrders", "showTime"):
        flags_el.set(key, str(data.get(key, False)).lower())

    tree = ElementTree(root)
    os.makedirs("kitchen_gen_bot/data/output", exist_ok=True)
    filename = f"KitchenResources_{uuid.uuid4().hex}.xml"
    path = os.path.join("kitchen_gen_bot/data/output", filename)
    tree.write(path, encoding="utf-8", xml_declaration=True)
    logger.info("XML saved to %s", path)
    return path
