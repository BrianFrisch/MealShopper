import os
import ast
import re

def analyze_py(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        tree = ast.parse(content, filename=file_path)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = node.lineno
                end = getattr(node, "end_lineno", start)
                count = end - start + 1
                if count >= 35:
                    print(f"[PY] {file_path} :: {node.name} (Lines {start}-{end}, Count: {count})")
    except Exception as e:
        print(f"Error py {file_path}: {e}")

def analyze_cs(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line.startswith("//") and not line.startswith("*") and not line.startswith("/*"):
                if re.search(r"\b(public|private|protected|internal|static|async)\b", line) and "(" in line and not any(k in line for k in ["class ", "interface ", "record ", "namespace ", "struct ", "enum "]):
                    m = re.search(r"([A-Za-z0-9_]+)\s*\([^\)]*\)", line)
                    if m and m.group(1) not in ["if", "for", "foreach", "while", "switch", "catch", "using", "lock"]:
                        method_name = m.group(1)
                        start_line = i + 1
                        brace_count = 0
                        found_open = False
                        curr = i
                        while curr < len(lines):
                            brace_count += lines[curr].count("{")
                            if brace_count > 0:
                                found_open = True
                            brace_count -= lines[curr].count("}")
                            if found_open and brace_count == 0:
                                end_line = curr + 1
                                count = end_line - start_line + 1
                                if count >= 30:
                                    print(f"[CS] {file_path} :: {method_name} (Lines {start_line}-{end_line}, Count: {count})")
                                i = curr
                                break
                            curr += 1
            i += 1
    except Exception as e:
        print(f"Error cs {file_path}: {e}")

for root, dirs, files in os.walk("."):
    dirs[:] = [d for d in dirs if d not in ["bin", "obj", ".venv", "venv", "site-packages", ".pytest_cache", "__pycache__", ".git"]]
    norm_root = root.replace("\\", "/")
    if not (norm_root.startswith("./apps") or norm_root.startswith("./libs")):
        continue
    for f in files:
        full = os.path.join(root, f)
        if f.endswith(".py"):
            analyze_py(full)
        elif f.endswith(".cs"):
            analyze_cs(full)
