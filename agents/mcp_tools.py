"""
MCP (Model Context Protocol) Tools for ASTRA
Enables agentic capabilities - AI thinks and acts autonomously.

MCP provides:
- Tool definitions for the LLM
- Automatic tool selection and execution
- Context management for multi-step tasks
"""
import json
import os
import subprocess
import webbrowser
from pathlib import Path
from typing import Any, Callable
from dataclasses import dataclass


@dataclass
class MCPTool:
    """Definition of an MCP tool."""
    name: str
    description: str
    parameters: dict
    handler: Callable


class MCPToolkit:
    """
    MCP-compatible toolkit for ASTRA.
    Provides tools that the LLM can call autonomously.
    """
    
    def __init__(self, tts=None, llm=None):
        self.tts = tts
        self.llm = llm
        self.tools: dict[str, MCPTool] = {}
        self._register_builtin_tools()
    
    def _register_builtin_tools(self):
        """Register all built-in tools."""
        
        # File system tools
        self.register(MCPTool(
            name="read_file",
            description="Read contents of a file",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Full path to the file"}
                },
                "required": ["path"]
            },
            handler=self._read_file
        ))
        
        self.register(MCPTool(
            name="write_file",
            description="Write content to a file",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Full path to the file"},
                    "content": {"type": "string", "description": "Content to write"}
                },
                "required": ["path", "content"]
            },
            handler=self._write_file
        ))
        
        self.register(MCPTool(
            name="list_directory",
            description="List files and folders in a directory",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path"}
                },
                "required": ["path"]
            },
            handler=self._list_directory
        ))
        
        # Web tools
        self.register(MCPTool(
            name="web_search",
            description="Search the web using DuckDuckGo",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"]
            },
            handler=self._web_search
        ))
        
        self.register(MCPTool(
            name="open_url",
            description="Open a URL in the default browser",
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to open"}
                },
                "required": ["url"]
            },
            handler=self._open_url
        ))
        
        # System tools
        self.register(MCPTool(
            name="run_command",
            description="Run a shell command and return output",
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command to run"}
                },
                "required": ["command"]
            },
            handler=self._run_command
        ))
        
        self.register(MCPTool(
            name="get_system_info",
            description="Get system information (CPU, RAM, disk usage)",
            parameters={"type": "object", "properties": {}},
            handler=self._get_system_info
        ))
        
        # Research tools
        self.register(MCPTool(
            name="wikipedia_search",
            description="Search Wikipedia for information",
            parameters={
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Topic to search"}
                },
                "required": ["topic"]
            },
            handler=self._wikipedia_search
        ))
        
        self.register(MCPTool(
            name="think",
            description="Internal reasoning step - think through a problem",
            parameters={
                "type": "object",
                "properties": {
                    "thought": {"type": "string", "description": "Your reasoning"}
                },
                "required": ["thought"]
            },
            handler=self._think
        ))
    
    def register(self, tool: MCPTool):
        """Register a tool."""
        self.tools[tool.name] = tool
    
    def get_tools_schema(self) -> list:
        """Get OpenAI-compatible tools schema for LLM."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                }
            }
            for tool in self.tools.values()
        ]
    
    def execute(self, tool_name: str, arguments: dict) -> dict:
        """Execute a tool and return result."""
        if tool_name not in self.tools:
            return {"error": f"Unknown tool: {tool_name}"}
        
        tool = self.tools[tool_name]
        try:
            result = tool.handler(arguments)
            return {"success": True, "result": result}
        except Exception as e:
            return {"error": str(e)}
    
    def agentic_loop(self, task: str, max_steps: int = 10) -> str:
        """
        Run agentic loop - AI thinks and acts until task is complete.
        This is the core of MCP-style autonomous operation.
        """
        if not self.llm:
            return "No LLM available for agentic execution."
        
        messages = [
            {
                "role": "system",
                "content": (
                    "You are ASTRA, an autonomous AI assistant. You can use tools to complete tasks. "
                    "Think step by step. Use the 'think' tool to reason through problems. "
                    "Call tools as needed. When the task is complete, respond with TASK_COMPLETE: followed by your final answer."
                )
            },
            {"role": "user", "content": task}
        ]
        
        tools_schema = self.get_tools_schema()
        
        for step in range(max_steps):
            # Call LLM with tools
            response = self._call_llm_with_tools(messages, tools_schema)
            
            if "TASK_COMPLETE:" in response.get("content", ""):
                # Task completed
                final = response["content"].split("TASK_COMPLETE:")[1].strip()
                return final
            
            # Check for tool calls
            tool_calls = response.get("tool_calls", [])
            if not tool_calls:
                # No tool calls, treat as final response
                return response.get("content", "I couldn't complete the task.")
            
            # Execute tool calls
            messages.append(response)
            
            for tc in tool_calls:
                tool_name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    args = {}
                
                result = self.execute(tool_name, args)
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "name": tool_name,
                    "content": json.dumps(result),
                })
        
        return "Task exceeded maximum steps. Partial progress made."
    
    def _call_llm_with_tools(self, messages: list, tools: list) -> dict:
        """Call LLM with tool definitions."""
        # For Groq
        if self.llm.use_groq:
            import urllib.request
            key = os.environ.get("GROQ_API_KEY", "")
            payload = json.dumps({
                "model": "llama-3.3-70b-versatile",
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",
                "max_tokens": 500,
            }).encode()
            req = urllib.request.Request(
                "https://api.groq.com/openai/v1/chat/completions",
                data=payload,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                }
            )
            resp = urllib.request.urlopen(req, timeout=30)
            data = json.loads(resp.read())
            return data["choices"][0]["message"]
        
        # For Ollama (limited tool support)
        # Fall back to simple completion
        return {"content": self.llm.simple_query(messages[-1]["content"])}
    
    # ============== Tool Handlers ==============
    
    def _read_file(self, args: dict) -> str:
        path = Path(args["path"])
        if not path.exists():
            return f"File not found: {path}"
        return path.read_text(encoding="utf-8", errors="replace")[:5000]
    
    def _write_file(self, args: dict) -> str:
        path = Path(args["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(args["content"], encoding="utf-8")
        return f"Written to {path}"
    
    def _list_directory(self, args: dict) -> str:
        path = Path(args["path"])
        if not path.exists():
            return f"Directory not found: {path}"
        items = list(path.iterdir())[:50]
        return "\n".join(f"{'[DIR] ' if i.is_dir() else ''}{i.name}" for i in items)
    
    def _web_search(self, args: dict) -> str:
        import urllib.request
        import urllib.parse
        import re
        
        query = args["query"]
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers={"User-Agent": "ASTRA/2.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        html = resp.read().decode("utf-8", errors="replace")
        
        # Extract snippets
        snippets = re.findall(r'class="result__snippet"[^>]*>([^<]+)', html)
        return "\n".join(snippets[:5]) if snippets else "No results found."
    
    def _open_url(self, args: dict) -> str:
        url = args["url"]
        if not url.startswith("http"):
            url = "https://" + url
        webbrowser.open(url)
        return f"Opened {url}"
    
    def _run_command(self, args: dict) -> str:
        cmd = args["command"]
        # Safety: block dangerous commands
        blocked = ["rm -rf", "del /f", "format", "shutdown", "restart"]
        if any(b in cmd.lower() for b in blocked):
            return "Command blocked for safety."
        
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=30
            )
            output = result.stdout or result.stderr or "No output"
            return output[:2000]
        except subprocess.TimeoutExpired:
            return "Command timed out."
        except Exception as e:
            return f"Error: {e}"
    
    def _get_system_info(self, args: dict) -> str:
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=1)
            ram = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            return (
                f"CPU: {cpu}%\n"
                f"RAM: {ram.percent}% ({ram.used // (1024**3)}GB / {ram.total // (1024**3)}GB)\n"
                f"Disk: {disk.percent}% ({disk.used // (1024**3)}GB / {disk.total // (1024**3)}GB)"
            )
        except ImportError:
            return "psutil not available"
    
    def _wikipedia_search(self, args: dict) -> str:
        import urllib.request
        import urllib.parse
        
        topic = args["topic"]
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(topic)}"
        req = urllib.request.Request(url, headers={"User-Agent": "ASTRA/2.0"})
        try:
            resp = urllib.request.urlopen(req, timeout=10)
            data = json.loads(resp.read())
            return data.get("extract", "No Wikipedia article found.")
        except Exception:
            return f"Could not find Wikipedia article for: {topic}"
    
    def _think(self, args: dict) -> str:
        """Internal reasoning step - logged but not executed."""
        thought = args.get("thought", "")
        print(f"[MCP Think] {thought}")
        return f"Thought recorded: {thought[:100]}..."
