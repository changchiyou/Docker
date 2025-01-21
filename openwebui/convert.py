import os
import ast
import json
import time
import re

USER_ID = "29cdb3f9-ffa8-4978-9f0d-784a2796a858"

class PythonScriptConverter:
    def __init__(self, directory='.'):
        self.base_directory = os.path.abspath(directory)
        self.tools_directory = os.path.join(self.base_directory, 'workspace', 'tools')
        self.functions_directory = os.path.join(self.base_directory, 'workspace', 'functions')

    def convert_script(self, script_name, mode):
        with open(script_name, 'r', encoding='utf-8') as file:
            content = file.read()

        json_filename = f"{script_name[:-3]}.json"
        previous_result = self.load_previous_json(json_filename)

        if previous_result and previous_result[0]['content'] == content:
            return

        tree = ast.parse(content)

        manifest = self.extract_manifest(tree, content)
        if not manifest:
            return None
        if 'title' not in manifest or 'description' not in manifest:
            raise ValueError('`manifest` must contain both \'title\' and \'description\'')

        result = {
            "id": manifest['title'].replace(' ', '_').lower(),
            "user_id": USER_ID,
            "name": manifest['title'],
            "content": content,
            "meta": {
                "description": manifest['description'],
                "manifest": manifest,
            },
            "updated_at": int(time.time()),
            "created_at": previous_result[0]['created_at'] if previous_result else int(time.time())
        }

        match mode:
            case "tools":
                tools_class = self.extract_class(tree, "Tools")

                if not tools_class:
                    return None

                methods = self.extract_methods(tools_class)
                specs = self.create_specs(methods)

                result["specs"] = specs
                return result
            case "functions":
                result["is_active"] = True
                result["is_global"] = True
                return result

    def extract_class(self, tree, nodename):
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == nodename:
                return node
        return None

    def extract_methods(self, tools_class):
        methods = []
        for node in tools_class.body:
            if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name != '__init__':
                methods.append(node)
        return methods

    def create_specs(self, methods):
        specs = []
        for method in methods:
            # Extract the full docstring
            docstring = ast.get_docstring(method)
            # Get only the first line of the docstring
            if docstring:
                docstring = ' '.join([line for line in docstring.splitlines() if line and line.strip()[0] != ":"])

            spec = {
                "name": method.name,
                "description": docstring or f"Description for {method.name}",
                "parameters": self.extract_parameters(method)
            }
            specs.append(spec)
        return specs

    def extract_parameters(self, method):
        params = {
            "type": "object",
            "properties": {},
            "required": []
        }
        
        # Extract docstring and find parameters
        docstring = ast.get_docstring(method)
        param_pattern = re.compile(r":param (\w+): (.+)")
        
        if docstring:
            for match in param_pattern.findall(docstring):
                param_name, param_desc = match
                params["properties"][param_name] = {
                    "type": "str",  # Assuming all parameters are strings for simplicity
                    "description": param_desc
                }
                params["required"].append(param_name)

        return params

    def extract_manifest(self, tree, content):
        manifest = {}
        try:
            # Look for the triple-quoted string containing the manifest
            manifest_node = next(
                node for node in tree.body if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
            )
            manifest_text = manifest_node.value.value # type: ignore
            for line in manifest_text.strip().split("\n"):
                key, value = line.split(":", 1)
                manifest[key.strip()] = value.strip()
            return manifest
        except Exception as e:
            print(f"Error extracting manifest from {content[:30]}...: {e}")
            return None

    def process_directory(self):
        # Process .py files in workspace/tools
        self.process_files_in_directory(self.tools_directory, "tools")
        
        # Process .py files in workspace/functions
        self.process_files_in_directory(self.functions_directory, "functions")

    def process_files_in_directory(self, directory, mode):
        for filename in os.listdir(directory):
            if filename.endswith('.py'):
                script_path = os.path.join(directory, filename)
                result = self.convert_script(script_path, mode)
                if result:
                    json_filename = f"{directory}/{os.path.splitext(filename)[0]}.json"
                    with open(json_filename, 'w', encoding='utf-8') as json_file:
                        json.dump([result], json_file, indent=2, ensure_ascii=False)
                    print(f"Converted {script_path.replace(self.base_directory, '')} to {json_filename.replace(self.base_directory, '')}")

    def load_previous_json(self, filename):
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                    return data
                except json.JSONDecodeError:
                    pass
        return None


if __name__ == "__main__":
    converter = PythonScriptConverter()
    converter.process_directory()
