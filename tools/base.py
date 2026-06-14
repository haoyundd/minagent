class Tool:
    name = ''
    description = ''
    parameters = {}

    def get_schema(self):
        return {
            'type': 'function',
            'function': {
                'name': self.name,
                'description': self.description,
                'parameters': self.parameters,
            }
        }

    def execute(self, **kwargs):
        raise NotImplementedError


class ToolRegistry:
    def __init__(self):
        self._tools = {}

    def register(self, tool):
        self._tools[tool.name] = tool

    def get(self, name):
        return self._tools.get(name)

    def get_all_schemas(self):
        return [tool.get_schema() for tool in self._tools.values()]

    def list_names(self):
        return list(self._tools.keys())
