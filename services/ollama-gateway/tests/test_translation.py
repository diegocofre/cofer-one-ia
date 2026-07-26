# SPDX-License-Identifier: Apache-2.0
import base64

from app.translation import accumulate_tool_call, finalize_tool_calls, ollama_generate_to_openai_chat, ollama_to_openai_chat, openai_message_to_ollama, openai_tool_calls_to_ollama


def test_chat_translation_maps_options_and_tools():
    result = ollama_to_openai_chat({"model": "coder", "messages": [{"role": "user", "content": "hello"}], "stream": False, "options": {"temperature": 0.2, "num_predict": 200, "top_p": 0.9}, "tools": [{"type": "function", "function": {"name": "read", "parameters": {}}}]})
    assert result["model"] == "coder"
    assert result["temperature"] == 0.2
    assert result["max_tokens"] == 200
    assert result["top_p"] == 0.9
    assert result["tools"][0]["function"]["name"] == "read"
    assert "stream_options" not in result


def test_generate_translation_includes_system_message():
    result = ollama_generate_to_openai_chat({"model": "x", "system": "system", "prompt": "hello", "stream": True})
    assert result["messages"] == [{"role": "system", "content": "system"}, {"role": "user", "content": "hello"}]
    assert result["stream_options"]["include_usage"] is True


def test_ollama_tool_history_is_converted_to_openai_shape():
    result = ollama_to_openai_chat({"model": "coder", "stream": False, "messages": [{"role": "user", "content": "read x"}, {"role": "assistant", "content": "", "tool_calls": [{"type": "function", "function": {"name": "read", "arguments": {"path": "x"}}}]}, {"role": "tool", "tool_name": "read", "content": "contents"}]})
    assistant = result["messages"][1]
    tool = result["messages"][2]
    assert assistant["tool_calls"][0]["function"]["arguments"] == '{"path":"x"}'
    assert assistant["tool_calls"][0]["id"] == tool["tool_call_id"]
    assert tool["name"] == "read"


def test_openai_tool_calls_are_converted_back_to_ollama_objects():
    calls = openai_tool_calls_to_ollama([{"id": "call_1", "type": "function", "function": {"name": "read", "arguments": '{"path":"x"}'}}])
    assert calls == [{"type": "function", "function": {"index": 0, "name": "read", "arguments": {"path": "x"}}}]


def test_openai_message_maps_reasoning_and_tools():
    result = openai_message_to_ollama({"role": "assistant", "content": "done", "reasoning_content": "internal trace", "tool_calls": [{"id": "c", "type": "function", "function": {"name": "read", "arguments": "{}"}}]})
    assert result["thinking"] == "internal trace"
    assert result["tool_calls"][0]["function"]["arguments"] == {}


def test_vision_image_is_converted_to_openai_data_url():
    png = base64.b64encode(b"\x89PNG\r\n\x1a\nexample").decode()
    result = ollama_to_openai_chat({"model": "vision", "stream": False, "messages": [{"role": "user", "content": "inspect", "images": [png]}]})
    parts = result["messages"][0]["content"]
    assert parts[0] == {"type": "text", "text": "inspect"}
    assert parts[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_streamed_tool_calls_are_reassembled():
    acc = {}
    accumulate_tool_call(acc, {"index": 0, "id": "call_1", "function": {"name": "read", "arguments": '{"p"'}})
    accumulate_tool_call(acc, {"index": 0, "function": {"arguments": ':"x"}'}})
    calls = finalize_tool_calls(acc)
    assert calls[0]["id"] == "call_1"
    assert calls[0]["function"]["name"] == "read"
    assert calls[0]["function"]["arguments"] == '{"p":"x"}'


def test_structured_output_reasoning_and_num_ctx_are_preserved():
    schema = {"type": "object", "properties": {"answer": {"type": "string"}}}
    result = ollama_to_openai_chat({
        "model": "coder",
        "messages": [{"role": "user", "content": "hello"}],
        "stream": False,
        "format": schema,
        "think": "high",
        "options": {"num_ctx": 65536, "top_k": 40},
    })
    assert result["response_format"]["type"] == "json_schema"
    assert result["response_format"]["json_schema"]["schema"] == schema
    assert result["reasoning_effort"] == "high"
    assert result["num_ctx"] == 65536
    assert result["top_k"] == 40
