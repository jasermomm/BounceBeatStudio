from __future__ import annotations

import builtins
import symtable
from pathlib import Path


def test_source_has_no_unresolved_global_name_references():
    allowed = set(dir(builtins)) | {
        "__annotations__",
        "__cached__",
        "__file__",
        "__loader__",
        "__name__",
        "__package__",
        "__spec__",
    }
    failures: list[str] = []

    for path in sorted(Path("src").rglob("*.py")):
        root = symtable.symtable(path.read_text(encoding="utf-8"), str(path), "exec")
        module_names = {
            symbol.get_name()
            for symbol in root.get_symbols()
            if symbol.is_assigned()
            or symbol.is_imported()
            or symbol.is_namespace()
            or symbol.is_parameter()
        }

        def inspect(table) -> None:
            for symbol in table.get_symbols():
                name = symbol.get_name()
                if (
                    symbol.is_referenced()
                    and symbol.is_global()
                    and name not in module_names
                    and name not in allowed
                ):
                    failures.append(f"{path}:{table.get_name()} references undefined global {name!r}")
            for child in table.get_children():
                inspect(child)

        inspect(root)

    assert not failures, "\n".join(failures)


def test_properties_panel_bindings_match_scene_model_fields():
    import ast
    from dataclasses import fields

    from bouncebeat.models.scene import (
        BallObject,
        BaseObject,
        BumperObject,
        EmitterObject,
        PolygonObject,
        PortalObject,
        RingObject,
        TextOverlayObject,
        WallObject,
    )

    source = Path("src/bouncebeat/ui/properties.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    class_map = {
        cls.__name__: cls
        for cls in (
            BallObject,
            WallObject,
            RingObject,
            BumperObject,
            PolygonObject,
            PortalObject,
            EmitterObject,
            TextOverlayObject,
        )
    }
    failures: list[str] = []

    def bound_names(statements: list[ast.stmt]) -> set[str]:
        names: set[str] = set()
        for statement in statements:
            for node in ast.walk(statement):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                    continue
                if not isinstance(node.func.value, ast.Name) or node.func.value.id != "self":
                    continue
                if node.func.attr.startswith("_bind_") and len(node.args) >= 2:
                    candidate = node.args[1]
                    if isinstance(candidate, ast.Constant) and isinstance(candidate.value, str):
                        names.add(candidate.value)
                if node.func.attr == "_emit_object" and node.args:
                    candidate = node.args[0]
                    if isinstance(candidate, ast.Constant) and isinstance(candidate.value, str):
                        names.add(candidate.value)
        return names

    properties_class = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "PropertiesPanel"
    )
    build_method = next(
        node
        for node in properties_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "_build_object_tab"
    )
    first_type_branch = next(
        index
        for index, statement in enumerate(build_method.body)
        if isinstance(statement, ast.If)
        and isinstance(statement.test, ast.Call)
        and isinstance(statement.test.func, ast.Name)
        and statement.test.func.id == "isinstance"
    )
    base_fields = {field.name for field in fields(BaseObject)}
    for name in bound_names(build_method.body[:first_type_branch]) - base_fields:
        failures.append(f"BaseObject has no property {name!r}")

    branch = build_method.body[first_type_branch]
    while isinstance(branch, ast.If):
        test = branch.test
        if (
            isinstance(test, ast.Call)
            and isinstance(test.func, ast.Name)
            and test.func.id == "isinstance"
            and len(test.args) >= 2
            and isinstance(test.args[1], ast.Name)
            and test.args[1].id in class_map
        ):
            cls = class_map[test.args[1].id]
            valid = {field.name for field in fields(cls)}
            for name in bound_names(branch.body) - valid:
                failures.append(f"{cls.__name__} has no property {name!r}")
        branch = branch.orelse[0] if len(branch.orelse) == 1 and isinstance(branch.orelse[0], ast.If) else None

    assert not failures, "\n".join(failures)


def test_project_property_paths_resolve_on_default_project():
    import ast

    from bouncebeat.models.project import BounceBeatProject

    source = Path("src/bouncebeat/ui/properties.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    paths: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if isinstance(node.func.value, ast.Name) and node.func.value.id == "self":
            if node.func.attr.startswith("_project_") and len(node.args) >= 2:
                candidate = node.args[1]
                if isinstance(candidate, ast.Constant) and isinstance(candidate.value, str):
                    paths.add(candidate.value)
        if node.func.attr == "emit" and node.args:
            owner = node.func.value
            if (
                isinstance(owner, ast.Attribute)
                and isinstance(owner.value, ast.Name)
                and owner.value.id == "self"
                and owner.attr == "project_property_changed"
            ):
                candidate = node.args[0]
                if isinstance(candidate, ast.Constant) and isinstance(candidate.value, str):
                    paths.add(candidate.value)

    project = BounceBeatProject()
    failures: list[str] = []
    for path in sorted(paths):
        value = project
        try:
            for part in path.split("."):
                value = getattr(value, part)
        except AttributeError:
            failures.append(path)
    assert not failures, "Invalid project property paths: " + ", ".join(failures)
