from __future__ import annotations
import re
from typing import Any, List, Dict, Union, Optional


class JSONXPath:
    """XPath-ähnliche Suche für JSON (dict/list) – mit robuster Prädikats-Engine und Parent-Achse '..'."""

    # ============================== Public API ==============================

    @staticmethod
    def search(expr: str, data: Any) -> List[Any]:
        return [m["value"] for m in JSONXPath.evaluate(expr, data)]

    @staticmethod
    def get_path(expr: str, data: Any) -> List[str]:
        return [m["path"] for m in JSONXPath.evaluate(expr, data)]

    @staticmethod
    def get_parent_key(expr: str, data: Any, depth: int = 1) -> List[Union[str, int, None]]:
        out: List[Union[str, int, None]] = []
        for m in JSONXPath.evaluate(expr, data):
            out.append(JSONXPath.parent_Key_From_Path(m["path"], depth))
        return out

    # ============================== Core Eval ===============================

    @staticmethod
    def evaluate(expr: str, data: Any) -> List[Dict[str, Any]]:
        if not isinstance(expr, str) or not expr or expr[0] != "/":
            raise ValueError("Ausdruck muss mit '/' oder '//' beginnen.")
        steps = JSONXPath.tokenize(expr)
        # Startnode inklusive parent=None
        current = [{"value": data, "path": "", "parent": None}]

        for axis, name, predicate in steps:
            next_nodes: List[Dict[str, Any]] = []

            # --- Parent-Achse '..' ---
            if name == "..":
                for node in current:
                    if node.get("parent") is not None:
                        next_nodes.append(node["parent"])
                current = next_nodes
                # Prädikate auf '..' sind in XPath nicht üblich; wir überspringen sie
                continue

            # --- Auswahl gemäß Achse ---
            if axis == "//":
                for node in current:
                    next_nodes.extend(JSONXPath.desc_Select(node, name))
            else:  # "/"
                for node in current:
                    next_nodes.extend(JSONXPath.child_Select(node, name))

            # --- Prädikat anwenden ---
            if predicate:
                next_nodes = JSONXPath.apply_Filter(next_nodes, predicate)

            current = next_nodes

        return current

    # ============================== Tokenizer ===============================

    @staticmethod
    def tokenize(expr: str) -> List[tuple[str, str, Optional[str]]]:
        """
        Zerlegt den Ausdruck in (axis, name, predicate).
        - axis: '//' oder '/'
        - name: Segment-Name, '*', oder '..'
        - predicate: Inhalt innerhalb [ ... ] (ohne eckige Klammern) oder None
        """
        parts: List[tuple[str, str, Optional[str]]] = []
        rgx = re.compile(r'(//|/)([^/\[]+|\*)(?:\[(.*?)\])?')
        pos = 0
        for m in rgx.finditer(expr):
            axis, name, pred = m.groups()
            parts.append((axis, name.strip(), pred.strip() if pred else None))
            pos = m.end()
        if not parts or pos != len(expr):
            raise ValueError(f"Ungültiger Ausdruck: {expr!r}")
        return parts

    # ============================== Selection ===============================

    @staticmethod
    def create_Node(value: Any, path: str, parent: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        return {"value": value, "path": path, "parent": parent}

    @staticmethod
    def child_Select(node: Dict[str, Any], name: str) -> List[Dict[str, Any]]:
        """Direkter Kind-Schritt vom gegebenen Node."""
        value, base_path = node["value"], node["path"]
        parentcreate_Node = node  # der gegebene Node ist der Parent der direkten Kinder
        out: List[Dict[str, Any]] = []

        if isinstance(value, dict):
            if name == "*":
                for k, v in value.items():
                    child_path = f"{base_path}/{k}" if base_path else k
                    out.append(JSONXPath.create_Node(v, child_path, parentcreate_Node))
            elif name in value:
                v = value[name]
                child_path = f"{base_path}/{name}" if base_path else name
                out.append(JSONXPath.create_Node(v, child_path, parentcreate_Node))

        elif isinstance(value, list):
            for i, item in enumerate(value):
                if name == "*":
                    child_path = f"{base_path}[{i}]" if base_path else f"[{i}]"
                    out.append(JSONXPath.create_Node(item, child_path, parentcreate_Node))
                elif isinstance(item, dict) and name in item:
                    # Parent des Feldes ist das Dict-Item selbst (nicht die Liste)
                    itemcreate_Node = JSONXPath.create_Node(item, f"{base_path}[{i}]" if base_path else f"[{i}]", parentcreate_Node)
                    v = item[name]
                    child_path = f"{itemcreate_Node['path']}/{name}"
                    out.append(JSONXPath.create_Node(v, child_path, itemcreate_Node))

        return out

    @staticmethod
    def desc_Select(node: Dict[str, Any], name: str) -> List[Dict[str, Any]]:
        """Descendant-or-self Schritt: findet passende Knoten rekursiv."""
        start_value, start_path = node["value"], node["path"]
        out: List[Dict[str, Any]] = []

        def rec(val: Any, path: str, parent: Optional[Dict[str, Any]]):
            current = JSONXPath.create_Node(val, path, parent)

            if isinstance(val, dict):
                # Treffer am aktuellen Knoten?
                if name == "*":
                    out.append(current)
                elif name in val:
                    child_path = f"{path}/{name}" if path else name
                    out.append(JSONXPath.create_Node(val[name], child_path, current))

                # In Kinder absteigen
                for k, v in val.items():
                    rec(v, f"{path}/{k}" if path else k, current)

            elif isinstance(val, list):
                if name == "*":
                    out.append(current)
                for i, v in enumerate(val):
                    rec(v, f"{path}[{i}]" if path else f"[{i}]", current)
            # Skalare: keine Kinder

        rec(start_value, start_path, node.get("parent"))
        return out

    # ============================== Filtering ===============================

    @staticmethod
    def apply_Filter(nodes: List[Dict[str, Any]], predicate: str) -> List[Dict[str, Any]]:
        """Wendet Prädikat auf jeden Node an.
        - Bei Listen: filtert Elemente (item-level) und liefert Dict-Items zurück.
        - Bei Dicts: prüft den Knoten selbst.
        """
        out: List[Dict[str, Any]] = []
        for node in nodes:
            val = node["value"]
            if isinstance(val, list):
                for i, item in enumerate(val):
                    if JSONXPath.eval_Predicate(item, predicate):
                        item_path = f"{node['path']}[{i}]"
                        # Parent des Items ist die Liste (node)
                        out.append(JSONXPath.create_Node(item, item_path, node))
            elif isinstance(val, dict):
                if JSONXPath.eval_Predicate(val, predicate):
                    out.append(node)
        return out

    # ============================== Predicate Eval ==========================

    @staticmethod
    def eval_Predicate(ctx: Any, expr: str) -> bool:
        if not isinstance(ctx, dict):
            return False
        s = expr.strip()

        # not(...)
        m_not = JSONXPath.match_Wrapped(s, "not")
        if m_not is not None:
            return not JSONXPath.eval_Predicate(ctx, m_not)

        # A and B  (Top-Level)
        parts = JSONXPath.split_Top(s, "and")
        if parts:
            return all(JSONXPath.eval_Predicate(ctx, p) for p in parts)

        # A or B
        parts = JSONXPath.split_Top(s, "or")
        if parts:
            return any(JSONXPath.eval_Predicate(ctx, p) for p in parts)

        # Funktionen: contains/starts-with/ends-with
        f = JSONXPath.parse_Function_Call(s)
        if f:
            fname, args = f
            if fname in ("contains", "starts-with", "ends-with") and len(args) == 2:
                left = JSONXPath.value_Of(ctx, args[0])       # Feldwert
                right = JSONXPath.literal_Of(args[1])         # Literal
                left_s = "" if left is None else str(left)
                right_s = "" if right is None else str(right)
                if fname == "contains":
                    return right_s in left_s
                if fname == "starts-with":
                    return left_s.startswith(right_s)
                if fname == "ends-with":
                    return left_s.endswith(right_s)

        # einfacher Vergleich: lhs op rhs
        cmp = JSONXPath.parse_Comparison(s)
        if cmp:
            lhs, op, rhs = cmp
            lval = JSONXPath.value_Of(ctx, lhs)
            # Vergleiche nur wahr, wenn das Feld existiert
            if lval is None:
                return False

            if rhs.kind == "literal_str":
                r = rhs.value
                if op == "=":  return lval == r
                if op == "!=": return lval != r
                return False

            if rhs.kind == "literal_num":
                lnum = JSONXPath.to_Float(lval)
                if lnum is None:
                    return False
                r = float(rhs.value)
                if op == "=":  return lnum == r
                if op == "!=": return lnum != r
                if op == ">":  return lnum >  r
                if op == "<":  return lnum <  r
                if op == ">=": return lnum >= r
                if op == "<=": return lnum <= r
                return False

            if rhs.kind == "literal_bool":
                r = rhs.value
                if op == "=":  return lval is r
                if op == "!=": return lval is not r
                return False

            if rhs.kind == "literal_null":
                r = None
                if op == "=":  return lval is r
                if op == "!=": return lval is not r
                return False

        # Feld-Existenzprüfung (z. B. [name])
        if JSONXPath.looks_Like_Path(s):
            return JSONXPath.value_Of(ctx, s) is not None

        return False

    # ---------- predicate helpers ----------

    @staticmethod
    def match_Wrapped(s: str, fname: str) -> Optional[str]:
        # fname ( ... )  mit ausgewogener Klammerung
        if not s.startswith(fname):
            return None
        i = len(fname)
        while i < len(s) and s[i].isspace(): i += 1
        if i >= len(s) or s[i] != "(": return None
        i += 1
        depth, inq = 1, None
        start = i
        while i < len(s):
            ch = s[i]
            if inq:
                if ch == "\\": i += 2; continue
                if ch == inq: inq = None
            else:
                if ch in ("'", '"'): inq = ch
                elif ch == "(": depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        inner = s[start:i].strip()
                        rest = s[i+1:].strip()
                        return inner if rest == "" else None
            i += 1
        return None

    @staticmethod
    def split_Top(s: str, op: str) -> List[str] | None:
        out, last, depth, inq = [], 0, 0, None
        i = 0
        needle = f" {op} "
        while i < len(s):
            ch = s[i]
            if inq:
                if ch == "\\": i += 2; continue
                if ch == inq: inq = None
            else:
                if ch in ("'", '"'): inq = ch
                elif ch == "(": depth += 1
                elif ch == ")": depth = max(0, depth - 1)
                elif depth == 0 and s.startswith(needle, i):
                    out.append(s[last:i].strip())
                    i += len(needle)
                    last = i
                    continue
            i += 1
        if out:
            out.append(s[last:].strip())
            return out
        return None

    @staticmethod
    def parse_Function_Call(s: str):
        # name(arg1, arg2)
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_-]*)\s*\(', s)
        if not m:
            return None
        name = m.group(1)
        i = m.end()  # pos nach '('
        depth, inq = 1, None
        args_raw = ""
        start = i
        while i < len(s):
            ch = s[i]
            if inq:
                if ch == "\\": i += 2; continue
                if ch == inq: inq = None
            else:
                if ch in ("'", '"'): inq = ch
                elif ch == "(": depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        args_raw = s[start:i].strip()
                        if s[i+1:].strip(): return None
                        break
            i += 1
        if depth != 0:
            return None
        args = JSONXPath.split_Args(args_raw)
        return name, args

    @staticmethod
    def split_Args(s: str) -> List[str]:
        out, last, depth, inq = [], 0, 0, None
        i = 0
        while i < len(s):
            ch = s[i]
            if inq:
                if ch == "\\": i += 2; continue
                if ch == inq: inq = None
            else:
                if ch in ("'", '"'): inq = ch
                elif ch == "(": depth += 1
                elif ch == ")": depth = max(0, depth - 1)
                elif ch == "," and depth == 0:
                    out.append(s[last:i].strip())
                    last = i + 1
            i += 1
        out.append(s[last:].strip())
        return [a for a in out if a]

    # --------- comparison parsing ----------

    class RHS:
        def __init__(self, kind: str, value: Any = None):
            self.kind = kind
            self.value = value

    @staticmethod
    def parse_Comparison(s: str):
        # ersten top-level Operator außerhalb Quotes finden: !=, >=, <=, =, >, <
        ops = ["!=", ">=", "<=", "=", ">", "<"]
        inq, depth = None, 0
        i = 0
        while i < len(s):
            ch = s[i]
            if inq:
                if ch == "\\": i += 2; continue
                if ch == inq: inq = None
            else:
                if ch in ("'", '"'): inq = ch
                elif ch == "(": depth += 1
                elif ch == ")": depth = max(0, depth - 1)
                elif depth == 0:
                    for op in ops:
                        if s.startswith(op, i):
                            lhs = s[:i].strip()
                            rhs = s[i+len(op):].strip()
                            if not lhs or not rhs: return None
                            rhscreate_Node = JSONXPath.parse_Rhs(rhs)
                            if rhscreate_Node is None: return None
                            return (lhs, op, rhscreate_Node)
            i += 1
        return None

    @staticmethod
    def parse_Rhs(s: str):
        # string literal
        if (len(s) >= 2) and (s[0] == s[-1]) and (s[0] in ("'", '"')):
            return JSONXPath.RHS("literal_str", s[1:-1])
        # bool / null
        low = s.lower()
        if low == "true":  return JSONXPath.RHS("literal_bool", True)
        if low == "false": return JSONXPath.RHS("literal_bool", False)
        if low == "null":  return JSONXPath.RHS("literal_null", None)
        # number
        if re.fullmatch(r'-?\d+(?:\.\d+)?', s):
            return JSONXPath.RHS("literal_num", float(s))
        return None

    # --------- value & helpers ----------

    @staticmethod
    def literal_Of(s: str) -> Any:
        """Liest ein Literal aus einer Argumentposition (String/Num/Bool/Null).
           Ungequotete Wörter (außer true/false/null/number) werden als String genommen."""
        s = s.strip()
        if (len(s) >= 2) and (s[0] == s[-1]) and (s[0] in ("'", '"')):
            return s[1:-1]
        low = s.lower()
        if low == "true":  return True
        if low == "false": return False
        if low == "null":  return None
        if re.fullmatch(r'-?\d+(?:\.\d+)?', s):
            try: return float(s)
            except ValueError: return s
        return s

    @staticmethod
    def looks_Like_Path(s: str) -> bool:
        return bool(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*(?:\[[0-9]+\])?(?:\.[A-Za-z_][A-Za-z0-9_]*(?:\[[0-9]+\])?)*', s))

    @staticmethod
    def value_Of(ctx: dict, dotted: str) -> Any:
        """Liest verschachtelte Werte via 'a.b[0].c' (Dict-Schlüssel + Listenindizes)."""
        cur: Any = ctx
        for part in dotted.split("."):
            m = re.fullmatch(r'([A-Za-z_][A-Za-z0-9_]*)(\[[0-9]+\])*', part)
            if not m:
                return None
            key = m.group(1)
            if not isinstance(cur, dict) or key not in cur:
                return None
            cur = cur[key]
            idxs = re.findall(r'\[([0-9]+)\]', part)
            for idx_s in idxs:
                if not isinstance(cur, list):
                    return None
                idx = int(idx_s)
                if idx < 0 or idx >= len(cur):
                    return None
                cur = cur[idx]
        return cur

    @staticmethod
    def to_Float(x: Any) -> Optional[float]:
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def parent_Key_From_Path(path: str, depth: int) -> Union[str, int, None]:
        if not path:
            return None
        tokens = re.findall(r"[A-Za-z0-9_]+|\[\d+\]", path)
        if not tokens:
            return None
        pos = len(tokens) - depth - 1
        if pos < 0:
            return None
        key = tokens[pos]
        if key.startswith("[") and key.endswith("]"):
            try:
                return int(key[1:-1])
            except ValueError:
                return None
        return key
