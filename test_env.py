import sys
import ollama
import pydantic

print(f"✅ Python Executable Path : {sys.executable}")
print(f"✅ Python Version         : {sys.version.split()[0]}")
print(f"✅ Pydantic Version       : {pydantic.__version__}")
print("🚀 Environment setup successfully configured!")