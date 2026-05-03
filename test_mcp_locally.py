"""
Pulse MCP Client Tester — Manually verify the MCP server.

This script demonstrates how an AI Client (like Claude) communicates
with your Pulse MCP server. It starts the server, asks for its tools,
and executes a test search.

Usage:
    python test_mcp_locally.py
"""

import asyncio
import os
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def run_mcp_test():
    print("\n--- Pulse MCP Server: Local Action Test ---")

    # 1. Define how to start the server
    # We use the same command Claude Desktop would use
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "pulse.mcp_server"],
        env=os.environ.copy()
    )

    print("[*] Connecting to Pulse MCP Server...")
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize the session
                await session.initialize()
                print("[+] Connection Established!")

                # 2. List available tools
                print("\n[*] Querying available tools...")
                tools_result = await session.list_tools()
                tools = tools_result.tools
                
                print(f"[+] Found {len(tools)} tools:")
                for tool in tools:
                    print(f"    - {tool.name}: {tool.description[:60]}...")

                # 3. Test a specific tool (search_web)
                print("\n[*] Testing 'search_web' tool via MCP protocol...")
                search_query = "What is the capital of France?"
                print(f"[*] Calling tool with query: '{search_query}'")
                
                result = await session.call_tool("search_web", arguments={"query": search_query})
                
                print("\n[+] MCP Server Response:")
                # result.content is a list of content blocks
                for block in result.content:
                    if hasattr(block, 'text'):
                        # Print the first 300 chars of the search results
                        print("-" * 30)
                        print(block.text[:400] + "...")
                        print("-" * 30)

                print("\n[SUCCESS] MCP Server is fully operational and tools are responsive!")

    except Exception as e:
        print(f"\n[ERROR] MCP Test failed.")
        print(f"Details: {str(e)}")
        print("\nNote: Make sure your dependencies are installed (`pip install mcp`).")

if __name__ == "__main__":
    asyncio.run(run_mcp_test())
