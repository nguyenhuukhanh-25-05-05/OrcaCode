import os
import json
import shutil
import tempfile
from pathlib import Path
import pytest

from core.services.blueprint_service import BlueprintService

@pytest.fixture
def temp_project_for_blueprint():
    """Fixture to set up a dummy project for AST and symbol parsing tests."""
    temp_dir = tempfile.mkdtemp()
    project_path = Path(temp_dir)

    # 1. Create a dummy Python file with classes and functions
    py_code = """
class Calculator:
    \"\"\"A simple calculator class.\"\"\"
    def add(self, a, b):
        \"\"\"Add two numbers.\"\"\"
        return a + b
        
    def subtract(self, a, b):
        return a - b

def greet_user(name):
    \"\"\"Greet the user by name.\"\"\"
    print(f"Hello, {name}!")
"""
    (project_path / "calc.py").write_text(py_code, encoding="utf-8")

    # 2. Create a dummy JS file
    js_code = """
class UserService {
    login(username, password) {
        return true;
    }
}
function formatName(name) {
    return name.toUpperCase();
}
"""
    (project_path / "user.js").write_text(js_code, encoding="utf-8")

    yield project_path

    shutil.rmtree(temp_dir)


def test_blueprint_generation_and_retrieval(temp_project_for_blueprint):
    svc = BlueprintService(str(temp_project_for_blueprint))
    
    # Verify build_blueprint parses correctly
    proj_map = svc.build_blueprint()
    
    # 1. Check JSON map existence
    assert svc.map_path.exists()
    assert svc.blueprint_path.exists()
    
    # 2. Verify parsed symbols from calc.py
    assert "calc.py" in proj_map
    calc_symbols = proj_map["calc.py"]
    
    # Assert Calculator class parsed
    classes = calc_symbols["classes"]
    assert len(classes) == 1
    assert classes[0]["name"] == "Calculator"
    assert classes[0]["doc"] == "A simple calculator class."
    
    # Assert Calculator methods
    methods = classes[0]["methods"]
    assert len(methods) == 2
    assert methods[0]["name"] == "add"
    assert methods[0]["args"] == ["self", "a", "b"]
    assert methods[0]["doc"] == "Add two numbers."
    assert methods[1]["name"] == "subtract"
    assert methods[1]["args"] == ["self", "a", "b"]
    
    # Assert functions in calc.py
    functions = calc_symbols["functions"]
    assert len(functions) == 1
    assert functions[0]["name"] == "greet_user"
    assert functions[0]["args"] == ["name"]
    assert functions[0]["doc"] == "Greet the user by name."

    # 3. Verify parsed symbols from user.js
    assert "user.js" in proj_map
    js_symbols = proj_map["user.js"]
    assert len(js_symbols["classes"]) == 1
    assert js_symbols["classes"][0]["name"] == "UserService"
    assert len(js_symbols["functions"]) == 1
    assert js_symbols["functions"][0]["name"] == "formatName"

    # 4. Verify RAG retrieval logic
    # Default query (no matched files) returns overview summary
    overview = svc.get_relevant_blueprint("general query")
    assert "## Auxiliary Code Symbols Memory" in overview
    assert "calc.py" in overview
    assert "user.js" in overview
    
    # Query matching specific file returns detailed classes/functions listing
    focused = svc.get_relevant_blueprint("How does the calc.py work?")
    assert "### File: `calc.py` symbols" in focused
    assert "class Calculator" in focused
    assert "def add(self, a, b)" in focused
