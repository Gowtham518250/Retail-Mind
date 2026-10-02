# conftest.py - Blocks conflicting langsmith pytest plugin (pydantic v1 incompatibility)
import sys
import types

# Stub out langsmith before it tries to load pydantic v1 schemas
_stub = types.ModuleType('langsmith')
_stub.pytest_plugin = None
sys.modules.setdefault('langsmith', _stub)
sys.modules.setdefault('langsmith.utils', types.ModuleType('langsmith.utils'))
sys.modules.setdefault('langsmith.schemas', types.ModuleType('langsmith.schemas'))
